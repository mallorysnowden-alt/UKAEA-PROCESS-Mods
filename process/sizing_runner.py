"""Entry point for TokamakSizeOptimizatIonTool with validation cases.

Run with:
    python3 -m process.sizing_runner
"""

from process.sizing import SizingInputs, SizingResult, TokamakSizeOptimizatIonTool


def print_result(result: SizingResult, inputs: SizingInputs, ref_name: str, r_ref: float):
    """Print power balance and operating point for a sizing result."""

    pb = result.power_balance

    # ---- Power Balance ----
    print("\n--- Top-Down Power Balance ---")
    print(f"  P_net          = {inputs.p_net_mw:8.1f} MW  (input)")
    print(f"  Q_eng          = {inputs.q_eng:8.2f}      (input)")
    print(f"  P_gross        = {pb.p_gross_mw:8.1f} MW")
    print(f"  P_recirc       = {pb.p_recirc_mw:8.1f} MW")
    print(f"  P_thermal      = {pb.p_thermal_mw:8.1f} MW")
    print(f"  P_fusion       = {pb.p_fusion_mw:8.1f} MW")
    print(f"  P_HCD_injected = {pb.p_hcd_injected_mw:8.1f} MW")
    print(f"  Q_plasma       = {pb.q_plasma:8.1f}")
    print(f"  P_loss (sep)   = {pb.p_loss_mw:8.1f} MW")
    print(f"  P_alpha        = {pb.p_alpha_mw:8.1f} MW")
    print(f"  P_neutron      = {pb.p_neutron_mw:8.1f} MW")

    # ---- Optimal Point ----
    print(f"\n--- Optimal Operating Point ---")
    print(f"  R_major     = {result.r_major_m:8.2f} m    ({ref_name} ref: {r_ref} m)")
    print(f"  T_i         = {result.t_i_optimal_kev:8.1f} keV")
    print(f"  B_t         = {inputs.b_t:8.3f} T  (input)")
    print(f"  n_e         = {result.n_e_m3:8.2e} m^-3")
    print(f"  I_p         = {result.i_p_ma:8.2f} MA")
    print(f"  beta_N      = {result.beta_n:8.3f}      (limit: {inputs.beta_n_max})")
    print(f"  H_required  = {result.h_required:8.3f}      (limit: {inputs.h_max})")
    print(f"  f_Greenwald = {result.f_gw:8.3f}      (limit: {inputs.f_gw_max})")
    print(f"  NWL         = {result.wall_load_mw_m2:8.3f} MW/m^2")
    print(f"  P_sep/R     = {result.p_sep_r_mw_m:8.2f} MW/m")
    print(f"  V_plasma    = {result.vol_plasma_m3:8.1f} m^3")
    print(f"  Binding     = {result.binding_constraint}")

    # ---- Validation ----
    pct_diff = (result.r_major_m - r_ref) / r_ref * 100
    print(f"\n  Deviation from {ref_name}: {pct_diff:+.1f}%", end="")
    if abs(pct_diff) <= 15:
        print("  [PASS]")
    else:
        print("  [OUTSIDE +/-15% BAND]")

    # ---- T_i Sweep ----
    print(f"\n--- T_i Sweep: R_min vs Ion Temperature ---")
    print(f"  {'T_i (keV)':>10}  {'R_min (m)':>10}  {'Binding Constraint'}")
    print(f"  {'-'*10}  {'-'*10}  {'-'*20}")
    for t_i, r_min, binding in result.sweep_results:
        r_str = f"{r_min:10.2f}" if r_min < 100 else "      inf"
        marker = " <-- optimal" if abs(t_i - result.t_i_optimal_kev) < 0.01 else ""
        print(f"  {t_i:10.1f}  {r_str}  {binding}{marker}")

    print()


def run_demo_validation():
    """EU-DEMO: Nb3Sn superconductor (5.3 T), solid ceramic (HCPB) blanket."""

    inputs = SizingInputs(
        p_net_mw=500.0,
        q_eng=3.0,

        eta_thermal=0.33,
        eta_wall_plug=0.40,
        eta_absorption=0.80,
        f_aux_recirc=0.80,

        m_blanket=1.14,

        aspect=3.1,
        kappa=1.65,
        triang=0.33,

        b_t=5.3,
        fuel_type="DT",

        q95_min=3.0,
        beta_n_max=2.8,
        h_max=1.1,
        f_gw_max=1.2,

        t_i_range_kev=(8.0, 30.0),
        t_i_steps=50,

        profile_factor=2.0,
        f_rad=0.50,
        f_fuel_dilution=0.85,
    )

    print("=" * 70)
    print("  TokamakSizeOptimizatIonTool -- EU-DEMO VALIDATION")
    print("  B_t = 5.3 T (Nb3Sn)  Blanket M = 1.14 (HCPB)")
    print("=" * 70)

    result = TokamakSizeOptimizatIonTool(inputs)
    print_result(result, inputs, "EU-DEMO", 9.1)


def run_arc_validation():
    """ARC: HTS REBCO superconductor (9.2 T), FLiBe blanket."""

    inputs = SizingInputs(
        p_net_mw=190.0,
        q_eng=3.0,

        eta_thermal=0.40,
        eta_wall_plug=0.50,
        eta_absorption=0.90,
        f_aux_recirc=0.50,

        m_blanket=1.20,

        aspect=3.0,
        kappa=1.84,
        triang=0.33,

        b_t=9.2,
        fuel_type="DT",

        q95_min=7.2,
        beta_n_max=2.59,
        h_max=1.8,
        f_gw_max=0.67,

        t_i_range_kev=(10.0, 30.0),
        t_i_steps=50,

        profile_factor=2.0,
        f_rad=0.0,
        f_fuel_dilution=1.0,
    )

    print("=" * 70)
    print("  TokamakSizeOptimizatIonTool -- ARC VALIDATION")
    print("  B_t = 9.2 T (HTS REBCO)  Blanket M = 1.20 (FLiBe)")
    print("=" * 70)

    result = TokamakSizeOptimizatIonTool(inputs)
    print_result(result, inputs, "ARC", 3.3)


def run_str480_validation():
    """STR480: Spherical tokamak reactor from SARAS/PROCESS benchmarking.

    Parameters from Table 1 of:
      "Benchmarking of spherical tokamak power plant design in PROCESS and SARAS"
      Fusion Engineering and Design (2025), doi:10.1016/j.fusengdes.2025.114951

    P_net and Q_eng derived to reproduce P_fus = 1268 MW from paper.
    """

    inputs = SizingInputs(
        p_net_mw=245.0,
        q_eng=1.70,

        eta_thermal=0.40,
        eta_wall_plug=0.40,
        eta_absorption=0.90,
        f_aux_recirc=0.50,

        m_blanket=1.15,

        aspect=1.9,
        kappa=2.5,
        triang=0.40,

        b_t=3.30,
        fuel_type="DT",

        q95_min=8.8,
        beta_n_max=3.5,
        h_max=1.3,
        f_gw_max=1.0,

        t_i_range_kev=(8.0, 30.0),
        t_i_steps=50,

        profile_factor=2.0,
        f_rad=0.11,
        f_fuel_dilution=0.85,
    )

    print("=" * 70)
    print("  TokamakSizeOptimizatIonTool -- STR480 VALIDATION")
    print("  B_t = 3.30 T (HTS)  A = 1.9  SARAS benchmarking study")
    print("=" * 70)

    result = TokamakSizeOptimizatIonTool(inputs)
    print_result(result, inputs, "STR480", 4.8)


if __name__ == "__main__":
    run_demo_validation()
    print("\n")
    run_arc_validation()
    print("\n")
    run_str480_validation()
