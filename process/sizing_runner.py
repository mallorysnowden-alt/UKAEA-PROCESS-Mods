"""Entry point for TokamakSizeOptimizatIonTool with validation cases.

Run with:
    python3 -m process.sizing_runner
"""

import numpy as np

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
    print(f"  B_t         = {inputs.b_t:8.3f} T  ({inputs.sc_type}, fraction={inputs.b_t_fraction:.2f})")
    print(f"  n_e         = {result.n_e_m3:8.2e} m^-3")
    print(f"  I_p         = {result.i_p_ma:8.2f} MA")
    print(f"  beta_N      = {result.beta_n:8.3f}      (limit: {inputs.beta_n_max})")
    print(f"  H_required  = {result.h_required:8.3f}      (limit: {inputs.h_max})")
    print(f"  f_Greenwald = {result.f_gw:8.3f}      (limit: {inputs.f_gw_max})")
    print(f"  NWL         = {result.wall_load_mw_m2:8.3f} MW/m^2  (limit: {inputs.p_nw_max})")
    print(f"  P_sep/R     = {result.p_sep_r_mw_m:8.2f} MW/m    (limit: {inputs.p_sep_r_max})")
    r_inboard = result.r_major_m * (1.0 - 1.0 / inputs.aspect)
    ib_req = result.delta_tf_m * inputs.tf_build_margin + inputs.tf_build_buffer
    print(f"  delta_TF    = {result.delta_tf_m:8.3f} m       (x{inputs.tf_build_margin} + {inputs.tf_build_buffer}m buffer)")
    print(f"  Inboard     = {ib_req:8.2f} m  / {r_inboard:.2f} m available")
    print(f"  V_plasma    = {result.vol_plasma_m3:8.1f} m^3")
    print(f"  Binding     = {result.binding_constraint}")

    # ---- Validation ----
    pct_diff = (result.r_major_m - r_ref) / r_ref * 100
    status = "[PASS]" if abs(pct_diff) <= 15 else "[OUTSIDE +/-15% BAND]"
    print(f"\n  Deviation from {ref_name}: {pct_diff:+.1f}%  {status}  (driver: {result.binding_constraint})")

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
    """EU-DEMO: Nb3Sn superconductor, solid ceramic (HCPB) blanket."""

    inputs = SizingInputs(
        p_net_mw=500.0,
        q_eng=3.0,

        eta_thermal=0.33,
        eta_wall_plug=0.40,
        eta_absorption=0.80,
        f_aux_recirc=0.80,

        blanket_type="HCPB",

        aspect=3.1,
        kappa=1.65,
        triang=0.33,

        sc_type="Nb3Sn",
        b_t_fraction=0.77,
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
    print(f"  B_t = {inputs.b_t:.1f} T (Nb3Sn, {inputs.b_t_fraction:.0%} of max)")
    print(f"  Blanket: HCPB (M={inputs.m_blanket}, NWL<={inputs.p_nw_max})")
    print("=" * 70)

    result = TokamakSizeOptimizatIonTool(inputs)
    print_result(result, inputs, "EU-DEMO", 9.1)


def run_arc_validation():
    """ARC: HTS REBCO superconductor, FLiBe blanket."""

    inputs = SizingInputs(
        p_net_mw=190.0,
        q_eng=3.0,

        eta_thermal=0.40,
        eta_wall_plug=0.50,
        eta_absorption=0.90,
        f_aux_recirc=0.50,

        blanket_type="FLiBe",

        aspect=3.0,
        kappa=1.84,
        triang=0.33,

        sc_type="REBCO",
        b_t_fraction=0.93,
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
    print(f"  B_t = {inputs.b_t:.1f} T (REBCO, {inputs.b_t_fraction:.0%} of max)")
    print(f"  Blanket: FLiBe (M={inputs.m_blanket}, NWL<={inputs.p_nw_max})")
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

        blanket_type="HCPB",
        m_blanket=1.15,

        aspect=1.9,
        kappa=2.5,
        triang=0.40,

        sc_type="Nb3Sn",
        b_t_fraction=0.68,
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
    print(f"  B_t = {inputs.b_t:.2f} T (Nb3Sn, {inputs.b_t_fraction:.0%} of max)")
    print(f"  A = {inputs.aspect}  Blanket: HCPB (M={inputs.m_blanket} override)")
    print("=" * 70)

    result = TokamakSizeOptimizatIonTool(inputs)
    print_result(result, inputs, "STR480", 4.8)


def run_st_sweep():
    """Sweep P_net for spherical tokamak with REBCO at full B_t."""

    print("=" * 70)
    print("  TokamakSizeOptimizatIonTool -- ST SWEEP (REBCO, A=1.9)")
    print("=" * 70)
    print(f"\n  {'P_net':>6}  {'R_min':>6}  {'R_floor':>7}  {'B_t':>5}  {'delta_TF':>8}  {'Inb.req':>7}  {'Inb.avl':>7}  {'Binding'}")
    print(f"  {'(MW)':>6}  {'(m)':>6}  {'(m)':>7}  {'(T)':>5}  {'(m)':>8}  {'(m)':>7}  {'(m)':>7}  {''}")
    print(f"  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*5}  {'-'*8}  {'-'*7}  {'-'*7}  {'-'*15}")

    for p_net in [50, 100, 150, 200, 250]:
        inputs = SizingInputs(
            p_net_mw=p_net,
            q_eng=1.70,

            eta_thermal=0.40,
            eta_wall_plug=0.40,
            eta_absorption=0.90,
            f_aux_recirc=0.50,

            blanket_type="FLiBe",

            aspect=1.9,
            kappa=2.5,
            triang=0.40,

            sc_type="REBCO",
            b_t_fraction=1.0,
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

        result = TokamakSizeOptimizatIonTool(inputs)
        r_inboard = result.r_major_m * (1.0 - 1.0 / inputs.aspect)
        inb_req = result.delta_tf_m * inputs.tf_build_margin + inputs.tf_build_buffer
        mu0 = 4.0 * np.pi * 1e-7
        k_tf = inputs.b_peak_t**2 / (2.0 * mu0 * inputs.f_tf_struc * inputs.sigma_tf_mpa * 1e6)
        denom = (1.0 - 1.0 / inputs.aspect) * (1.0 - inputs.tf_build_margin * k_tf / (1.0 + k_tf))
        r_floor = inputs.tf_build_buffer / denom
        print(f"  {p_net:6.0f}  {result.r_major_m:6.2f}  {r_floor:7.2f}  {inputs.b_t:5.2f}  {result.delta_tf_m:8.3f}  {inb_req:7.2f}  {r_inboard:7.2f}  {result.binding_constraint}")

    print()


if __name__ == "__main__":
    run_demo_validation()
    print("\n")
    run_arc_validation()
    print("\n")
    run_str480_validation()
    print("\n")
    run_st_sweep()
