"""Entry point for outside-in reactor sizing with EU-DEMO validation.

Run with:
    python3 -m process.sizing_runner
"""

from process.sizing import SizingInputs, outside_in_sizing


def run_demo_validation():
    """Run sizing with EU-DEMO-like parameters and compare to known R ≈ 9.1 m."""

    inputs = SizingInputs(
        # EU-DEMO targets
        p_net_mw=500.0,
        q_eng=3.0,                # DEMO Q_eng ~3 (large recirc: cryo, pumps, tritium)

        # Efficiencies
        eta_thermal=0.33,         # He-cooled HCPB Rankine cycle (~33%)
        eta_wall_plug=0.40,       # ECRH wall-plug efficiency
        eta_absorption=0.80,      # Plasma absorption (ECRH)
        f_aux_recirc=0.80,        # ~80% of recirc to non-HCD loads (cryo, pumps, tritium)

        # Blanket
        m_blanket=1.14,           # HCPB energy multiplication

        # EU-DEMO geometry
        aspect=3.1,
        kappa=1.65,
        triang=0.33,

        # Nb3Sn superconductor → 5.3 T on axis (12.3 T at coil)
        b_t=5.3,
        fuel_type="DT",

        # Physics limits (DEMO design targets)
        q95_min=3.0,
        beta_n_max=2.8,
        h_max=1.1,               # Conservative DEMO H-factor target
        f_gw_max=1.2,            # DEMO allows modest Greenwald overshoot

        # Sweep range
        t_i_range_kev=(8.0, 30.0),
        t_i_steps=50,

        # Profile peaking factor
        profile_factor=2.0,

        # Radiation and dilution
        f_rad=0.50,              # ~50% of heating power radiated (impurity seeding)
        f_fuel_dilution=0.85,    # ~15% He ash + impurity dilution
    )

    print("=" * 70)
    print("  OUTSIDE-IN REACTOR SIZING — EU-DEMO VALIDATION")
    print("=" * 70)

    result = outside_in_sizing(inputs)

    # ---- Power Balance Summary ----
    pb = result.power_balance
    print("\n--- Step 0: Top-Down Power Balance ---")
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
    print("\n--- Optimal Operating Point ---")
    print(f"  R_major     = {result.r_major_m:8.2f} m    (EU-DEMO ref: 9.1 m)")
    print(f"  T_i         = {result.t_i_optimal_kev:8.1f} keV  (EU-DEMO ref: ~13-15 keV)")
    print(f"  n_e         = {result.n_e_m3:8.2e} m^-3")
    print(f"  I_p         = {result.i_p_ma:8.2f} MA")
    print(f"  beta_N      = {result.beta_n:8.3f}      (limit: {inputs.beta_n_max})")
    print(f"  H_required  = {result.h_required:8.3f}      (limit: {inputs.h_max})")
    print(f"  f_Greenwald = {result.f_gw:8.3f}      (limit: {inputs.f_gw_max})")
    print(f"  V_plasma    = {result.vol_plasma_m3:8.1f} m^3")
    print(f"  Binding     = {result.binding_constraint}")

    # ---- Validation ----
    r_demo = 9.1
    pct_diff = (result.r_major_m - r_demo) / r_demo * 100
    print(f"\n  Deviation from EU-DEMO: {pct_diff:+.1f}%", end="")
    if abs(pct_diff) <= 15:
        print("  [PASS]")
    else:
        print("  [OUTSIDE ±15% BAND]")

    # ---- T_i Sweep Summary ----
    print("\n--- T_i Sweep: R_min vs Ion Temperature ---")
    print(f"  {'T_i (keV)':>10}  {'R_min (m)':>10}  {'Binding Constraint'}")
    print(f"  {'-'*10}  {'-'*10}  {'-'*20}")
    for t_i, r_min, binding in result.sweep_results:
        r_str = f"{r_min:10.2f}" if r_min < 100 else "      inf"
        marker = " <-- optimal" if abs(t_i - result.t_i_optimal_kev) < 0.01 else ""
        print(f"  {t_i:10.1f}  {r_str}  {binding}{marker}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_demo_validation()
