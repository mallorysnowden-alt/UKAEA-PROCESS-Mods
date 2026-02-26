"""TokamakSizeOptimizatIonTool — Outside-in reactor sizing module.

Given P_net and Q_eng as fixed inputs, derives P_fusion from a top-down power
balance, then sweeps ion temperature to find the minimum feasible major radius
satisfying physics constraints (Greenwald density, Troyon beta, kink stability,
and energy confinement) and engineering constraints (neutron wall load,
divertor heat exhaust P_sep/R).

Usage:
    from process.sizing import SizingInputs, TokamakSizeOptimizatIonTool
    result = TokamakSizeOptimizatIonTool(SizingInputs(p_net_mw=500, q_eng=3.0))
"""

from dataclasses import dataclass, field
import numpy as np

from process import constants
from process.confinement_time import iter_ipb98y2_confinement_time
from process.fusion_reactions import (
    BoschHaleConstants,
    REACTION_CONSTANTS_DT,
    REACTION_CONSTANTS_DHE3,
    REACTION_CONSTANTS_DD1,
    REACTION_CONSTANTS_DD2,
    bosch_hale_reactivity,
)
from process.plasma_geometry import PlasmaGeom


# ---------------------------------------------------------------------------
# Blanket parameters database
# ---------------------------------------------------------------------------

BLANKET_PARAMS = {
    #                  m_blanket  p_nw_max [MW/m^2]
    "HCPB":  {"m": 1.14, "nwl": 2.0},   # He-cooled pebble bed (EU-DEMO)
    "WCLL":  {"m": 1.18, "nwl": 2.5},   # Water-cooled lithium lead
    "DCLL":  {"m": 1.22, "nwl": 4.0},   # Dual-coolant lithium lead
    "FLiBe": {"m": 1.20, "nwl": 10.0},  # Molten salt (ARC-type)
    "LiPb":  {"m": 1.28, "nwl": 5.0},   # Self-cooled liquid metal
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SizingInputs:
    """All fixed inputs for the outside-in sizing."""

    # Power targets
    p_net_mw: float  # Net electric power (MW)
    q_eng: float  # Engineering gain = P_gross / P_recirc

    # Efficiencies
    eta_thermal: float = 0.40  # Thermal-to-electric conversion
    eta_wall_plug: float = 0.50  # HCD wall-plug efficiency
    eta_absorption: float = 0.90  # Plasma heating absorption efficiency
    f_aux_recirc: float = 0.50  # Fraction of P_recirc NOT going to HCD

    # Blanket — blanket_type sets defaults for m_blanket and p_nw_max
    blanket_type: str = "HCPB"
    m_blanket: float = None  # Override blanket energy multiplication
    p_nw_max: float = None   # Override max neutron wall load [MW/m^2]

    # Geometry
    aspect: float = 3.1
    kappa: float = 1.65
    triang: float = 0.33

    # Technology
    b_t: float = 5.3  # Toroidal field on axis (T)
    fuel_type: str = "DT"  # "DT" or "DHe3"

    # Physics limits
    q95_min: float = 3.0
    beta_n_max: float = 2.8
    h_max: float = 1.3
    f_gw_max: float = 1.0

    # Engineering limits
    p_sep_r_max: float = None  # Max P_sep/R [MW/m] (auto: 40 conv, 60 ST)

    # Temperature sweep
    t_i_range_kev: tuple = (8.0, 30.0)
    t_i_steps: int = 50

    # Profile factor for volume-averaged fusion power
    profile_factor: float = 2.0

    # Radiation fraction
    f_rad: float = 0.0

    # Fuel dilution
    f_fuel_dilution: float = 1.0

    def __post_init__(self):
        if self.blanket_type not in BLANKET_PARAMS:
            raise ValueError(
                f"Unknown blanket_type '{self.blanket_type}'. "
                f"Choose from: {list(BLANKET_PARAMS.keys())}"
            )
        bp = BLANKET_PARAMS[self.blanket_type]
        if self.m_blanket is None:
            self.m_blanket = bp["m"]
        if self.p_nw_max is None:
            self.p_nw_max = bp["nwl"]
        if self.p_sep_r_max is None:
            self.p_sep_r_max = 60.0 if self.aspect < 2.5 else 40.0


@dataclass
class PowerBalanceResult:
    """Results of the top-down power balance (Step 0)."""

    p_gross_mw: float
    p_recirc_mw: float
    p_thermal_mw: float
    p_fusion_mw: float
    p_hcd_injected_mw: float
    q_plasma: float
    p_loss_mw: float
    p_alpha_mw: float
    p_neutron_mw: float


@dataclass
class PointResult:
    """Physics results at a single (T_i, R) operating point."""

    t_i_kev: float
    r_major_m: float
    a_minor_m: float
    vol_plasma_m3: float
    n_e_m3: float
    i_p_ma: float
    beta_n: float
    h_required: float
    f_gw: float
    tau_e_required_s: float
    tau_e_nominal_s: float
    w_thermal_mj: float
    wall_load_mw_m2: float
    p_sep_r_mw_m: float
    feasible: bool
    binding_constraint: str


@dataclass
class SizingResult:
    """Full output of the sizing module."""

    r_major_m: float
    t_i_optimal_kev: float
    p_fusion_mw: float
    p_gross_mw: float
    p_recirc_mw: float
    p_thermal_mw: float
    p_hcd_injected_mw: float
    q_plasma: float
    n_e_m3: float
    i_p_ma: float
    beta_n: float
    h_required: float
    f_gw: float
    binding_constraint: str
    vol_plasma_m3: float
    wall_load_mw_m2: float
    p_sep_r_mw_m: float

    # Full sweep
    power_balance: PowerBalanceResult = None
    sweep_results: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fuel-type parameters
# ---------------------------------------------------------------------------

def get_fuel_params(fuel_type: str) -> dict:
    """Return fuel-dependent parameters."""
    if fuel_type == "DT":
        return {
            "constants": BoschHaleConstants(**REACTION_CONSTANTS_DT),
            "e_fusion_j": constants.D_T_ENERGY,
            "f_alpha": 1.0 - constants.DT_NEUTRON_ENERGY_FRACTION,
            "f_neutron": constants.DT_NEUTRON_ENERGY_FRACTION,
            "f_fuel": 1.0,
            "m_fuel_amu": 2.5,
        }
    elif fuel_type == "DHe3":
        return {
            "constants": BoschHaleConstants(**REACTION_CONSTANTS_DHE3),
            "e_fusion_j": constants.D_HELIUM_ENERGY,
            "f_alpha": 1.0 - constants.DHELIUM_PROTON_ENERGY_FRACTION,
            "f_neutron": 0.0,
            "f_fuel": 1.0,
            "m_fuel_amu": 2.5,
        }
    else:
        raise ValueError(f"Unsupported fuel type: {fuel_type}. Use 'DT' or 'DHe3'.")


# ---------------------------------------------------------------------------
# Core physics functions
# ---------------------------------------------------------------------------

def bosch_hale_scalar(t_i_kev: float, bh_constants: BoschHaleConstants) -> float:
    """Compute <sigma_v> for a single temperature using Bosch-Hale."""
    t_arr = np.array([t_i_kev])
    sv = bosch_hale_reactivity(t_arr, bh_constants)
    return float(sv[0])


def compute_plasma_current(
    r: float, a: float, b_t: float, kappa: float, kappa95: float,
    triang: float, triang95: float, q95: float,
) -> float:
    """Compute plasma current I_p [A] from safety factor and geometry."""
    eps = a / r
    fq = (
        0.5
        * (1.17 - 0.65 * eps)
        / ((1.0 - eps * eps) ** 2)
        * (1.0 + kappa95**2 * (1.0 + 2.0 * triang95**2 - 1.2 * triang95**3))
    )
    return (2.0 * np.pi / constants.RMU0) * a**2 / (r * q95) * fq * b_t


def compute_greenwald_density(i_p_a: float, a: float) -> float:
    """Greenwald density limit [m^-3]."""
    return 1.0e14 * i_p_a / (np.pi * a**2)


def compute_first_wall_area(r: float, a: float, kappa: float) -> float:
    """Approximate first wall surface area [m^2]."""
    return 4.0 * np.pi**2 * r * a * np.sqrt((1.0 + kappa**2) / 2.0)


# ---------------------------------------------------------------------------
# Top-down power balance
# ---------------------------------------------------------------------------

def top_down_power_balance(inp: SizingInputs) -> PowerBalanceResult:
    """Step 0: Derive all power quantities from P_net and Q_eng."""
    p_gross = inp.p_net_mw * inp.q_eng / (inp.q_eng - 1.0)
    p_recirc = p_gross - inp.p_net_mw
    p_thermal = p_gross / inp.eta_thermal

    fuel = get_fuel_params(inp.fuel_type)
    f_alpha = fuel["f_alpha"]
    f_neutron = fuel["f_neutron"]

    p_hcd_electric = (1.0 - inp.f_aux_recirc) * p_recirc
    p_hcd_injected = p_hcd_electric * inp.eta_wall_plug * inp.eta_absorption

    denom = f_neutron * inp.m_blanket + f_alpha
    p_fusion = (p_thermal - p_hcd_injected) / denom

    p_alpha = f_alpha * p_fusion
    p_neutron = f_neutron * p_fusion
    q_plasma = p_fusion / p_hcd_injected if p_hcd_injected > 0 else float("inf")
    p_loss = p_alpha + p_hcd_injected

    return PowerBalanceResult(
        p_gross_mw=p_gross, p_recirc_mw=p_recirc, p_thermal_mw=p_thermal,
        p_fusion_mw=p_fusion, p_hcd_injected_mw=p_hcd_injected,
        q_plasma=q_plasma, p_loss_mw=p_loss,
        p_alpha_mw=p_alpha, p_neutron_mw=p_neutron,
    )


# ---------------------------------------------------------------------------
# Feasibility check at a single (R, T_i) point
# ---------------------------------------------------------------------------

def check_feasibility(
    r: float,
    t_i_kev: float,
    sigmav: float,
    pb: PowerBalanceResult,
    inp: SizingInputs,
    fuel: dict,
) -> PointResult:
    """Evaluate all constraints at a given (R, T_i) operating point.

    Checks (in order):
      1. Neutron wall load  — p_nw <= p_nw_max
      2. P_sep/R            — P_sep/R <= p_sep_r_max
      3. Greenwald density   — n_e/n_GW <= f_gw_max
      4. Troyon beta         — beta_N <= beta_N_max
      5. Energy confinement  — H_req <= H_max
    """
    a = r / inp.aspect
    _, _, _, vol = PlasmaGeom.sauter_geometry(a, r, inp.kappa, inp.triang, 0.0)

    # Engineering metrics (always computed for output)
    a_fw = compute_first_wall_area(r, a, inp.kappa)
    wall_load = pb.p_neutron_mw / a_fw
    p_sep_r = pb.p_loss_mw * (1.0 - inp.f_rad) / r

    def _fail(binding, n_e=0.0, i_p_ma=0.0, beta_n=0.0, h_req=0.0,
              f_gw=0.0, tau_req=0.0, tau_nom=0.0, w_mj=0.0):
        return PointResult(
            t_i_kev=t_i_kev, r_major_m=r, a_minor_m=a, vol_plasma_m3=vol,
            n_e_m3=n_e, i_p_ma=i_p_ma, beta_n=beta_n, h_required=h_req,
            f_gw=f_gw, tau_e_required_s=tau_req, tau_e_nominal_s=tau_nom,
            w_thermal_mj=w_mj, wall_load_mw_m2=wall_load,
            p_sep_r_mw_m=p_sep_r, feasible=False,
            binding_constraint=binding,
        )

    # CHECK 1: Neutron wall load (optional)
    if inp.p_nw_max is not None and wall_load > inp.p_nw_max:
        return _fail("wall_load")

    # CHECK 2: P_sep/R (optional)
    if inp.p_sep_r_max is not None and p_sep_r > inp.p_sep_r_max:
        return _fail("p_sep_r")

    # Density from fusion power
    f_fuel = fuel["f_fuel"] * inp.f_fuel_dilution
    e_fus = fuel["e_fusion_j"]
    ne_sq = 4.0 * pb.p_fusion_mw * 1.0e6 / (
        f_fuel**2 * sigmav * e_fus * vol * inp.profile_factor
    )
    if ne_sq <= 0:
        return _fail("density_negative", h_req=999.0, f_gw=999.0)
    n_e = np.sqrt(ne_sq)

    kappa95 = inp.kappa * 0.95
    triang95 = inp.triang * 0.95

    i_p = compute_plasma_current(
        r, a, inp.b_t, inp.kappa, kappa95, inp.triang, triang95, inp.q95_min,
    )
    i_p_ma = i_p / 1.0e6

    # CHECK 3: Greenwald density limit
    n_gw = compute_greenwald_density(i_p, a)
    f_gw = n_e / n_gw
    if f_gw > inp.f_gw_max:
        return _fail("greenwald", n_e=n_e, i_p_ma=i_p_ma, f_gw=f_gw)

    # Stored energy
    t_e_kev = t_i_kev
    w_thermal_j = 1.5 * vol * n_e * (t_e_kev + t_i_kev) * constants.KILOELECTRON_VOLT
    w_thermal_mj = w_thermal_j / 1.0e6

    # CHECK 4: Beta limit (Troyon)
    avg_pressure = (2.0 / 3.0) * w_thermal_j / vol
    beta = 2.0 * constants.RMU0 * avg_pressure / inp.b_t**2
    beta_n = 100.0 * beta * a * inp.b_t / i_p_ma
    if beta_n > inp.beta_n_max:
        return _fail("beta", n_e=n_e, i_p_ma=i_p_ma, beta_n=beta_n,
                      f_gw=f_gw, w_mj=w_thermal_mj)

    # CHECK 5: Energy confinement (H-factor)
    p_transport_mw = max(pb.p_loss_mw * (1.0 - inp.f_rad), 1.0e-3)
    tau_required = w_thermal_j / (p_transport_mw * 1.0e6)
    kappa_ipb = vol / (2.0 * np.pi * r * np.pi * a**2)
    dnla19 = n_e * 1.0e-19

    tau_nominal = iter_ipb98y2_confinement_time(
        pcur=i_p_ma,
        b_plasma_toroidal_on_axis=inp.b_t,
        dnla19=dnla19,
        p_plasma_loss_mw=p_transport_mw,
        rmajor=r,
        kappa_ipb=kappa_ipb,
        aspect=inp.aspect,
        afuel=fuel["m_fuel_amu"],
    )

    h_required = tau_required / tau_nominal if tau_nominal > 0 else 999.0
    feasible = h_required <= inp.h_max
    binding = "confinement" if not feasible else "none"

    return PointResult(
        t_i_kev=t_i_kev, r_major_m=r, a_minor_m=a, vol_plasma_m3=vol,
        n_e_m3=n_e, i_p_ma=i_p_ma, beta_n=beta_n, h_required=h_required,
        f_gw=f_gw, tau_e_required_s=tau_required, tau_e_nominal_s=tau_nominal,
        w_thermal_mj=w_thermal_mj, wall_load_mw_m2=wall_load,
        p_sep_r_mw_m=p_sep_r, feasible=feasible,
        binding_constraint=binding,
    )


# ---------------------------------------------------------------------------
# Minimum radius search (bisection)
# ---------------------------------------------------------------------------

def find_minimum_radius(
    t_i_kev: float,
    sigmav: float,
    pb: PowerBalanceResult,
    inp: SizingInputs,
    fuel: dict,
    r_low: float = 2.0,
    r_high: float = 20.0,
    tol: float = 0.01,
    max_iter: int = 60,
) -> tuple[PointResult | None, str]:
    """Bisect on R to find the smallest feasible major radius."""
    point_high = check_feasibility(r_high, t_i_kev, sigmav, pb, inp, fuel)
    if not point_high.feasible:
        return None, point_high.binding_constraint

    best_point = point_high

    for _ in range(max_iter):
        if r_high - r_low < tol:
            break
        r_mid = (r_low + r_high) / 2.0
        point = check_feasibility(r_mid, t_i_kev, sigmav, pb, inp, fuel)
        if point.feasible:
            r_high = r_mid
            best_point = point
        else:
            r_low = r_mid

    r_check = max(r_low - tol, 0.1)
    point_just_below = check_feasibility(r_check, t_i_kev, sigmav, pb, inp, fuel)
    binding = point_just_below.binding_constraint if not point_just_below.feasible else "none"

    return best_point, binding


# ---------------------------------------------------------------------------
# Main sizing routine
# ---------------------------------------------------------------------------

def TokamakSizeOptimizatIonTool(inp: SizingInputs) -> SizingResult:
    """Run the full outside-in sizing: power balance -> T_i sweep -> R_min search."""
    pb = top_down_power_balance(inp)
    fuel = get_fuel_params(inp.fuel_type)

    # Engineering floor on R (avoids wasting bisection iterations)
    r_floor = 2.0
    if inp.p_nw_max is not None and inp.p_nw_max > 0:
        kappa_fac = np.sqrt((1.0 + inp.kappa**2) / 2.0)
        r_wl = np.sqrt(pb.p_neutron_mw * inp.aspect
                        / (4.0 * np.pi**2 * inp.p_nw_max * kappa_fac))
        r_floor = max(r_floor, r_wl)
    if inp.p_sep_r_max is not None and inp.p_sep_r_max > 0:
        p_sep = pb.p_loss_mw * (1.0 - inp.f_rad)
        r_floor = max(r_floor, p_sep / inp.p_sep_r_max)

    t_i_values = np.linspace(
        inp.t_i_range_kev[0], inp.t_i_range_kev[1], inp.t_i_steps,
    )

    sweep_results = []
    best_r = float("inf")
    best_point = None
    best_binding = "none"

    for t_i in t_i_values:
        sigmav = bosch_hale_scalar(t_i, fuel["constants"])
        if sigmav <= 0:
            sweep_results.append((t_i, float("inf"), "no_reactivity"))
            continue

        point, binding = find_minimum_radius(
            t_i, sigmav, pb, inp, fuel, r_low=r_floor,
        )

        if point is not None:
            sweep_results.append((t_i, point.r_major_m, binding))
            if point.r_major_m < best_r:
                best_r = point.r_major_m
                best_point = point
                best_binding = binding
        else:
            sweep_results.append((t_i, float("inf"), binding))

    if best_point is None:
        raise RuntimeError(
            "No feasible operating point found in the T_i sweep range. "
            "Try relaxing constraints or increasing the T_i range."
        )

    return SizingResult(
        r_major_m=best_point.r_major_m,
        t_i_optimal_kev=best_point.t_i_kev,
        p_fusion_mw=pb.p_fusion_mw,
        p_gross_mw=pb.p_gross_mw,
        p_recirc_mw=pb.p_recirc_mw,
        p_thermal_mw=pb.p_thermal_mw,
        p_hcd_injected_mw=pb.p_hcd_injected_mw,
        q_plasma=pb.q_plasma,
        n_e_m3=best_point.n_e_m3,
        i_p_ma=best_point.i_p_ma,
        beta_n=best_point.beta_n,
        h_required=best_point.h_required,
        f_gw=best_point.f_gw,
        binding_constraint=best_binding,
        vol_plasma_m3=best_point.vol_plasma_m3,
        wall_load_mw_m2=best_point.wall_load_mw_m2,
        p_sep_r_mw_m=best_point.p_sep_r_mw_m,
        power_balance=pb,
        sweep_results=sweep_results,
    )
