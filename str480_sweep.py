"""STR480 power sweep at full B_t — check where inboard build constraint activates."""

import numpy as np
from process.sizing import SizingInputs, TokamakSizeOptimizatIonTool

print("=" * 80)
print("  STR480 Power Sweep — Nb3Sn (100% of max), A=1.9, HCPB (M=1.15)")
print("=" * 80)

header = f"  {'P_net':>6}  {'R_min':>6}  {'R_floor':>7}  {'B_t':>5}  {'dTF':>6}  {'Inb.req':>7}  {'Inb.avl':>7}  {'T_i':>5}  {'H_req':>5}  {'f_GW':>5}  Binding"
units  = f"  {'(MW)':>6}  {'(m)':>6}  {'(m)':>7}  {'(T)':>5}  {'(m)':>6}  {'(m)':>7}  {'(m)':>7}  {'(keV)':>5}  {'':>5}  {'':>5}"
print(f"\n{header}")
print(units)
print(f"  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*5}  {'-'*6}  {'-'*7}  {'-'*7}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*15}")

for p_net in [245, 200, 150, 100, 50]:
    inputs = SizingInputs(
        p_net_mw=p_net,
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
    print(
        f"  {p_net:6.0f}  {result.r_major_m:6.2f}  {r_floor:7.2f}  {inputs.b_t:5.2f}"
        f"  {result.delta_tf_m:6.3f}  {inb_req:7.2f}  {r_inboard:7.2f}"
        f"  {result.t_i_optimal_kev:5.1f}  {result.h_required:5.3f}  {result.f_gw:5.3f}"
        f"  {result.binding_constraint}"
    )

print()
