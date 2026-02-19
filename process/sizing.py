"""Outside-in reactor sizing module.

Given P_net and Q_eng as fixed inputs, derives P_fusion from a top-down power
balance, then sweeps ion temperature to find the minimum feasible major radius
satisfying physics constraints (Greenwald density, Troyon beta, kink stability,
and energy confinement).
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

    # Blanket
    m_blanket: float = 1.14  # Blanket energy multiplication factor

    # Geometry
    aspect: float = 3.1
    kappa: float = 1.65
    triang: float = 0.33

    # Technology
    b_t: float = 5.3  # Toroidal field on axis (T)
    fuel_type: str = "DT"  # "DT", "DD", "DHe3"

    # Physics limits
    q95_min: float = 3.0
    beta_n_max: float = 2.8
    h_max: float = 1.3
    f_gw_max: float = 1.0

    # Temperature sweep
    t_i_range_kev: tuple = (8.0, 30.0)
    t_i_steps: int = 50

    # Profile factor for volume-averaged fusion power
    # Accounts for peaked profiles: <n^2 σv> / (<n>^2 <σv>)
    profile_factor: float = 2.0

    # Radiation fraction: fraction of P_loss that is radiated
    # Reduces the "transport loss" power used in confinement scaling
    # Typical: 0.4-0.6 for DEMO with impurity seeding
    f_rad: float = 0.0

    # Fuel dilution: effective fuel ion fraction relative to n_e
    # Accounts for He ash, impurities (Z_eff > 1)
    # Typical: 0.82-0.90 for DEMO
    f_fuel_dilution: float = 1.0


@dataclass
class PowerBalanceResult:
    """Results of the top-down power balance (Step 0)."""

    p_gross_mw: float
    p_recirc_mw: float
    p_thermal_mw: float
    p_fusion_mw: float
    p_hcd_injected_mw: float
    q_plasma: float
    p_loss_mw: float  # Power crossing separatrix (steady state)
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
    feasible: bool
    binding_constraint: str  # "none", "greenwald", "beta", "confinement", "density_negative"


@dataclass
class SizingResult:
    """Full output of the sizing module."""

    # Optimal operating point
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
            "e_fusion_j": constants.D_T_ENERGY,  # ~17.6 MeV in J
            "f_alpha": 1.0 - constants.DT_NEUTRON_ENERGY_FRACTION,  # ~0.2013
            "f_neutron": constants.DT_NEUTRON_ENERGY_FRACTION,  # ~0.7987
            "f_fuel": 1.0,  # fuel ion fraction of electron density (n_fuel / n_e)
            "m_fuel_amu": 2.5,  # average fuel mass
        }
    elif fuel_type == "DHe3":
        return {
            "constants": BoschHaleConstants(**REACTION_CONSTANTS_DHE3),
            "e_fusion_j": constants.D_HELIUM_ENERGY,
            "f_alpha": 1.0 - constants.DHELIUM_PROTON_ENERGY_FRACTION,
            "f_neutron": 0.0,  # No neutrons in primary reaction
            "f_fuel": 1.0,
            "m_fuel_amu": 2.5,
        }
    else:
        raise ValueError(f"Unsupported fuel type: {fuel_type}. Use 'DT' or 'DHe3'.")


# ---------------------------------------------------------------------------
# Core physics functions
# ---------------------------------------------------------------------------

def bosch_hale_scalar(t_i_kev: float, bh_constants: BoschHaleConstants) -> float:
    """Compute <σv> for a single temperature using Bosch-Hale.

    Wraps the array-based bosch_hale_reactivity for scalar use.
    """
    t_arr = np.array([t_i_kev])
    sv = bosch_hale_reactivity(t_arr, bh_constants)
    return float(sv[0])


def compute_plasma_current(
    r: float, a: float, b_t: float, kappa: float, kappa95: float,
    triang: float, triang95: float, q95: float,
) -> float:
    """Compute plasma current I_p [A] from safety factor and geometry.

    Uses the IPDG89 scaling (i_plasma_current=4) without global state.
    """
    eps = a / r
    # IPDG89 fq coefficient
    fq = (
        0.5
        * (1.17 - 0.65 * eps)
        / ((1.0 - eps * eps) ** 2)
        * (1.0 + kappa95**2 * (1.0 + 2.0 * triang95**2 - 1.2 * triang95**3))
    )
    i_p = (2.0 * np.pi / constants.RMU0) * a**2 / (r * q95) * fq * b_t
    return i_p


def compute_greenwald_density(i_p_a: float, a: float) -> float:
    """Greenwald density limit [m^-3]. I_p in Amps, a in metres.

    n_GW = I_p[MA] / (π a²) × 10²⁰  =  I_p[A] / (π a²) × 10¹⁴
    """
    return 1.0e14 * i_p_a / (np.pi * a**2)


# ---------------------------------------------------------------------------
# Top-down power balance
# ---------------------------------------------------------------------------

def top_down_power_balance(inp: SizingInputs) -> PowerBalanceResult:
    """Step 0: Derive all power quantities from P_net and Q_eng."""
    p_gross = inp.p_net_mw * inp.q_eng / (inp.q_eng - 1.0)
    p_recirc = p_gross - inp.p_net_mw

    # Thermal power entering the conversion cycle
    p_thermal = p_gross / inp.eta_thermal

    # Fusion power: thermal = neutron * M_blanket + alpha + HCD_absorbed
    # P_thermal = f_n * P_fus * M_blanket + f_a * P_fus + P_hcd_injected
    # We solve for P_fusion given the efficiency chain:
    fuel = get_fuel_params(inp.fuel_type)
    f_alpha = fuel["f_alpha"]
    f_neutron = fuel["f_neutron"]

    # HCD injected power
    p_hcd_electric = (1.0 - inp.f_aux_recirc) * p_recirc
    p_hcd_injected = p_hcd_electric * inp.eta_wall_plug * inp.eta_absorption

    # P_thermal = f_n * P_fus * M + f_a * P_fus + P_hcd_injected
    # P_fus = (P_thermal - P_hcd_injected) / (f_n * M + f_a)
    denom = f_neutron * inp.m_blanket + f_alpha
    p_fusion = (p_thermal - p_hcd_injected) / denom

    p_alpha = f_alpha * p_fusion
    p_neutron = f_neutron * p_fusion
    q_plasma = p_fusion / p_hcd_injected if p_hcd_injected > 0 else float("inf")

    # Steady-state: P_loss = P_heating = P_alpha_deposited + P_hcd_injected
    p_loss = p_alpha + p_hcd_injected

    return PowerBalanceResult(
        p_gross_mw=p_gross,
        p_recirc_mw=p_recirc,
        p_thermal_mw=p_thermal,
        p_fusion_mw=p_fusion,
        p_hcd_injected_mw=p_hcd_injected,
        q_plasma=q_plasma,
        p_loss_mw=p_loss,
        p_alpha_mw=p_alpha,
        p_neutron_mw=p_neutron,
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
    """Evaluate all constraints at a given (R, T_i) operating point."""
    a = r / inp.aspect

    # Sauter geometry (squareness = 0)
    _, _, _, vol = PlasmaGeom.sauter_geometry(a, r, inp.kappa, inp.triang, 0.0)

    # Derive density from fusion power requirement
    # P_fus = (f_fuel * f_dilution * n_e / 2)^2 * <σv> * E_fus * V * profile_factor
    # n_e^2 = 4 * P_fus [W] / ((f_fuel * f_dilution)^2 * sigmav * E_fus * V * profile)
    f_fuel = fuel["f_fuel"] * inp.f_fuel_dilution
    e_fus = fuel["e_fusion_j"]
    pf = inp.profile_factor

    ne_sq = 4.0 * pb.p_fusion_mw * 1.0e6 / (f_fuel**2 * sigmav * e_fus * vol * pf)
    if ne_sq <= 0:
        return PointResult(
            t_i_kev=t_i_kev, r_major_m=r, a_minor_m=a, vol_plasma_m3=vol,
            n_e_m3=0.0, i_p_ma=0.0, beta_n=0.0, h_required=999.0,
            f_gw=999.0, tau_e_required_s=0.0, tau_e_nominal_s=0.0,
            w_thermal_mj=0.0, feasible=False, binding_constraint="density_negative",
        )

    n_e = np.sqrt(ne_sq)

    # Approximate kappa95 and triang95 from separatrix values
    kappa95 = inp.kappa * 0.95
    triang95 = inp.triang * 0.95

    # Plasma current from q95_min
    i_p = compute_plasma_current(
        r, a, inp.b_t, inp.kappa, kappa95, inp.triang, triang95, inp.q95_min,
    )
    i_p_ma = i_p / 1.0e6

    # CHECK 1: Greenwald density limit
    n_gw = compute_greenwald_density(i_p, a)
    f_gw = n_e / n_gw

    if f_gw > inp.f_gw_max:
        return PointResult(
            t_i_kev=t_i_kev, r_major_m=r, a_minor_m=a, vol_plasma_m3=vol,
            n_e_m3=n_e, i_p_ma=i_p_ma, beta_n=0.0, h_required=0.0,
            f_gw=f_gw, tau_e_required_s=0.0, tau_e_nominal_s=0.0,
            w_thermal_mj=0.0, feasible=False, binding_constraint="greenwald",
        )

    # Stored thermal energy
    # W = (3/2) * V * (n_e * T_e + n_i * T_i) * keV_to_J
    # Assume T_e ≈ T_i and n_i ≈ n_e (quasi-neutrality with Z_eff ≈ 1)
    t_e_kev = t_i_kev  # approximate
    w_thermal_j = 1.5 * vol * n_e * (t_e_kev + t_i_kev) * constants.KILOELECTRON_VOLT
    w_thermal_mj = w_thermal_j / 1.0e6

    # CHECK 2: Beta limit (Troyon)
    # β = 2 μ₀ <p> / B² where <p> = (2/3) * W / V
    avg_pressure = (2.0 / 3.0) * w_thermal_j / vol
    beta = 2.0 * constants.RMU0 * avg_pressure / inp.b_t**2
    # β_N = β(%) × a × B_T / I_p(MA) = 100 × β(fraction) × a × B_T / I_p(MA)
    beta_n = 100.0 * beta * a * inp.b_t / i_p_ma

    if beta_n > inp.beta_n_max:
        return PointResult(
            t_i_kev=t_i_kev, r_major_m=r, a_minor_m=a, vol_plasma_m3=vol,
            n_e_m3=n_e, i_p_ma=i_p_ma, beta_n=beta_n, h_required=0.0,
            f_gw=f_gw, tau_e_required_s=0.0, tau_e_nominal_s=0.0,
            w_thermal_mj=w_thermal_mj, feasible=False, binding_constraint="beta",
        )

    # CHECK 3: Energy confinement (H-factor)
    # Transport power = total loss minus radiation (radiation doesn't count as
    # "transport loss" in IPB98y2 — it's subtracted from both W/P and the scaling)
    p_transport_mw = pb.p_loss_mw * (1.0 - inp.f_rad)
    p_transport_mw = max(p_transport_mw, 1.0e-3)  # avoid division by zero
    tau_required = w_thermal_j / (p_transport_mw * 1.0e6)  # seconds

    # IPB98(y,2) with H=1
    # κ_IPB defined from volume: κ_IPB = V / (2πR × πa²)
    kappa_ipb = vol / (2.0 * np.pi * r * np.pi * a**2)
    dnla19 = n_e * 1.0e-19  # line-avg ≈ vol-avg for this approximation

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
        w_thermal_mj=w_thermal_mj, feasible=feasible, binding_constraint=binding,
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
    """Bisect on R to find the smallest feasible major radius.

    Returns (best_point, binding_constraint_at_limit).
    If no feasible R exists in [r_low, r_high], returns (None, reason).
    """
    # First check that r_high is feasible
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
            binding_at_limit = point.binding_constraint

    # Get the binding constraint by checking just below the minimum
    point_just_below = check_feasibility(r_low, t_i_kev, sigmav, pb, inp, fuel)
    binding = point_just_below.binding_constraint if not point_just_below.feasible else "none"

    return best_point, binding


# ---------------------------------------------------------------------------
# Main sizing routine
# ---------------------------------------------------------------------------

def outside_in_sizing(inp: SizingInputs) -> SizingResult:
    """Run the full outside-in sizing: power balance → T_i sweep → R_min search.

    Returns the optimal (T_i, R_min) operating point and the full sweep data.
    """
    # Step 0: Top-down power balance
    pb = top_down_power_balance(inp)
    fuel = get_fuel_params(inp.fuel_type)

    # Step 1 & 2: Sweep T_i, find R_min at each
    t_i_values = np.linspace(inp.t_i_range_kev[0], inp.t_i_range_kev[1], inp.t_i_steps)

    sweep_results = []
    best_r = float("inf")
    best_point = None
    best_binding = "none"

    for t_i in t_i_values:
        sigmav = bosch_hale_scalar(t_i, fuel["constants"])

        if sigmav <= 0:
            sweep_results.append((t_i, float("inf"), "no_reactivity"))
            continue

        point, binding = find_minimum_radius(t_i, sigmav, pb, inp, fuel)

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
            "Try relaxing constraints (h_max, f_gw_max, beta_n_max) or "
            "increasing the T_i range."
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
        power_balance=pb,
        sweep_results=sweep_results,
    )
