# TokamakSizeOptimizatIonTool — Changelog

All changes relative to the `main` branch.

---

## Add SC_PARAMS database, TF coil model, and inboard build constraint

### New: Superconductor parameters database (`SC_PARAMS`)

A lookup table maps `sc_type` to peak field, stress allowable, and TF fraction of the inboard radial stack:

| `sc_type` | B_peak (T) | σ_TF (MPa) | tf_frac | Description |
|---|---|---|---|---|
| `"NbTi"` | 8.0 | 660 | 0.30 | LTS, most shielding needed at 4K |
| `"Nb3Sn"` | 12.0 | 660 | 0.33 | LTS, thick cryo+neutron shielding at 4K |
| `"REBCO"` | 20.0 | 900 | 0.50 | HTS, thin cryo shielding at 20–30K |

`tf_frac` reflects that LTS coils require proportionally more cryogenic and neutron shielding in the inboard stack than HTS, so the TF coil occupies a smaller fraction.

### New: B_t derived from superconductor choice

`b_t` is now auto-derived from `sc_type`, `b_t_fraction`, and aspect ratio via the stress-driven TF coil model:

```
k = B_peak² / (2μ₀ × f_struc × σ)
B_t_max = B_peak × (1 - 1/A) / (1 + k)
B_t = b_t_fraction × B_t_max
```

Users select a superconductor and operating fraction rather than specifying B_t directly. Explicit `b_t` override is still supported.

### New: TF coil thickness and inboard build constraint

`compute_tf_coil_thickness` computes the stress-driven radial thickness: `Δ_TF = k × R_inboard / (1 + k)`.

The full inboard build requirement is:

```
IB_required = Δ_TF / tf_frac + tf_build_buffer
```

where `tf_build_buffer = 0.8m` represents non-TF inboard components (VV, thermal shield, insulation, gaps). A post-check after the T_i sweep enforces `IB_required ≤ R_inboard`, computing an analytical R_floor when violated:

```
R_floor = tf_build_buffer / [(1 - 1/A) × (1 - k / (tf_frac × (1 + k)))]
```

### New: `delta_tf_m` output field

Added to `PointResult` and `SizingResult` for reporting the stress-driven TF coil thickness at the operating point.

### New: ST power sweep (`run_st_sweep`)

Sweeps P_net from 50–250 MW for a spherical tokamak (REBCO, A=1.9, full B_t) with R_floor column. Demonstrates `inboard_build` binding at low power where physics R_min drops below the build floor.

### Changed: `SizingInputs` fields

| Field | Before | After |
|---|---|---|
| `b_t` | `float = 5.3` (direct input) | `float = None` (auto from SC + geometry) |
| `sc_type` | — | `str = "Nb3Sn"` (new) |
| `b_t_fraction` | — | `float = 1.0` (new) |
| `sigma_tf_mpa` | — | `float = None` (auto from SC) |
| `b_peak_t` | — | `float = None` (auto from SC) |
| `f_tf_struc` | — | `float = 0.5` (new) |
| `tf_build_margin` | — | `float = None` (auto = 1/tf_frac from SC) |
| `tf_build_buffer` | — | `float = 0.8` (new) |

### Changed: Validation cases use `sc_type` + `b_t_fraction`

All three validation cases now specify superconductor type and operating fraction instead of explicit B_t:

| Case | sc_type | b_t_fraction | Derived B_t |
|---|---|---|---|
| EU-DEMO | Nb3Sn | 0.77 | 5.3 T |
| ARC | REBCO | 0.93 | 9.2 T |
| STR480 | Nb3Sn | 0.68 | 3.3 T |

### Files modified

- `process/sizing.py` — Added `SC_PARAMS`, SC resolution in `__post_init__`, `compute_tf_coil_thickness`, inboard build post-check, `delta_tf_m` field
- `process/sizing_runner.py` — Updated validation cases to use `sc_type`/`b_t_fraction`; added inboard build display; added `run_st_sweep`

### Validation summary

| Design | Reference R (m) | Computed R (m) | Deviation | Binding Constraint |
|---|---|---|---|---|
| EU-DEMO | 9.1 | 8.25 | -9.4% | confinement |
| ARC | 3.3 | 3.54 | +7.3% | p_sep_r |
| STR480 | 4.8 | 5.46 | +13.7% | confinement |

All within the ±15% acceptance band.

---

## `f5c0b4c7` — Add blanket_type lookup and default-ON engineering constraints

### New: Blanket type database (`BLANKET_PARAMS`)

A lookup table maps `blanket_type` to default values for blanket energy multiplication (`m_blanket`) and maximum neutron wall load (`p_nw_max`):

| `blanket_type` | Description | `m_blanket` | `p_nw_max` (MW/m²) |
|---|---|---|---|
| `"HCPB"` | He-cooled pebble bed (EU-DEMO) | 1.14 | 2.0 |
| `"WCLL"` | Water-cooled lithium lead | 1.18 | 2.5 |
| `"DCLL"` | Dual-coolant lithium lead | 1.22 | 4.0 |
| `"FLiBe"` | Molten salt (ARC-type) | 1.20 | 10.0 |
| `"LiPb"` | Self-cooled liquid metal | 1.28 | 5.0 |

Users select a blanket concept via `blanket_type="HCPB"` (default). The `m_blanket` and `p_nw_max` values are resolved automatically in `__post_init__`. Either value can be overridden explicitly:

```python
SizingInputs(p_net_mw=500, q_eng=3.0, blanket_type="FLiBe", m_blanket=1.25)
# Uses FLiBe's NWL limit (10.0) but overrides M to 1.25
```

### New: Aspect-ratio-dependent P_sep/R limit

`p_sep_r_max` is now set automatically based on aspect ratio when not explicitly provided:

- **Conventional tokamak** (A >= 2.5): 40 MW/m
- **Spherical tokamak** (A < 2.5): 60 MW/m

This reflects the higher divertor heat exhaust capability of ST configurations (Super-X, snowflake geometries).

### Changed: `SizingInputs` fields

| Field | Before | After |
|---|---|---|
| `m_blanket` | `float = 1.14` (direct input) | `float = None` (resolved from `blanket_type`) |
| `p_nw_max` | `float = None` (disabled) | `float = None` (resolved from `blanket_type`) |
| `p_sep_r_max` | `float = None` (disabled) | `float = None` (resolved from aspect ratio) |
| `blanket_type` | — | `str = "HCPB"` (new) |

### Files modified

- `process/sizing.py` — Added `BLANKET_PARAMS`, `blanket_type` field, `__post_init__` resolution logic
- `process/sizing_runner.py` — Updated validation cases to use `blanket_type`; display NWL and P_sep/R limits

---

## `b34a24ce` — Add engineering constraints, ARC and STR480 validation cases

### New: Engineering constraints in sizing model

Two engineering constraints added to `check_feasibility`, checked before physics limits:

1. **Neutron wall load** — `NWL = P_neutron / A_FW <= p_nw_max`
2. **P_sep/R** — `P_loss × (1 - f_rad) / R <= p_sep_r_max`

New helper function `compute_first_wall_area(R, a, kappa)` computes the approximate FW surface area used for NWL.

An analytical **R_floor** is computed before the T_i sweep to avoid wasting bisection iterations below physically meaningful radii:

- From NWL: `R_floor >= sqrt(P_neutron × A / (4π² × p_nw_max × κ_factor))`
- From P_sep/R: `R_floor >= P_sep / p_sep_r_max`

### New: `wall_load_mw_m2` and `p_sep_r_mw_m` output fields

Added to both `PointResult` and `SizingResult` dataclasses so engineering metrics are always reported.

### New: ARC validation case

- **ARC**: HTS REBCO superconductor, B_t = 9.2 T, FLiBe blanket (M = 1.20)
- Parameters: P_net = 190 MW, Q_eng = 3.0, A = 3.0, κ = 1.84, q95_min = 7.2, β_N_max = 2.59, H_max = 1.8, f_GW_max = 0.67
- Result: R = 3.54 m vs 3.3 m reference (+7.3%) **[PASS]**

### New: STR480 validation case (spherical tokamak)

- **STR480**: Spherical tokamak from SARAS/PROCESS benchmarking study
- Source: "Benchmarking of spherical tokamak power plant design in PROCESS and SARAS", Fusion Engineering and Design (2025), doi:10.1016/j.fusengdes.2025.114951
- Parameters from Table 1: A = 1.9, B_t = 3.30 T, κ = 2.5, δ = 0.40, q95_min = 8.8, β_N_max = 3.5, H_max = 1.3
- P_net = 245 MW and Q_eng = 1.70 derived to reproduce P_fus = 1268 MW from paper
- Result: R = 5.44 m vs 4.8 m reference (+13.4%) **[PASS]**

### Changed: Reverted from layer-by-layer build model to fixed-B_t

The layer-by-layer inboard build model (FW, blanket, shield, TF coil with self-consistent B_t derivation) caused >100% divergence for compact machines (ARC went from +2% to +108%). Reverted to the original fixed-B_t approach where `b_t` is a direct user input.

### Changed: `sizing_runner.py` refactored

`print_result` extracted as a reusable function accepting `SizingResult`, `SizingInputs`, reference name, and reference radius. Supports multiple validation cases in a single run.

### Files modified

- `process/sizing.py` — Reverted build model; added engineering constraints, R_floor, wall_load/p_sep_r fields
- `process/sizing_runner.py` — Refactored print_result; added ARC and STR480 cases

---

## `2161c18e` — Rename to TokamakSizeOptimizatIonTool and add README documentation

### Changed: Function rename

`outside_in_sizing` renamed to `TokamakSizeOptimizatIonTool` throughout `sizing.py`, `sizing_runner.py`, and module docstrings.

### New: README documentation

Added comprehensive section to `README.md`:

- Quick start instructions (`python3 -m process.sizing_runner`)
- Full API usage example with annotated `SizingInputs`
- Input parameters reference table (all 17 parameters with descriptions and typical values)
- Output fields reference table

### Files modified

- `process/sizing.py` — Function and docstring rename
- `process/sizing_runner.py` — Function call rename
- `README.md` — Added TokamakSizeOptimizatIonTool section

---

## `3d98d613` — Add outside-in reactor sizing module

### New: `process/sizing.py`

Core sizing module implementing the outside-in approach:

1. **Top-down power balance** — Given P_net and Q_eng, analytically derive P_fusion, P_HCD, P_alpha, P_neutron, Q_plasma
2. **Ion temperature sweep** — Sweep T_i over user-defined range (default 8–30 keV)
3. **Minimum-radius bisection** — For each T_i, find smallest R satisfying:
   - Greenwald density limit (n_e/n_GW <= f_gw_max)
   - Troyon beta limit (β_N <= β_N_max)
   - Kink stability (q95 >= q95_min, using IPDG89 scaling)
   - Energy confinement (H_required <= H_max, using IPB98(y,2) scaling)
4. **Optimum selection** — T_i yielding smallest R_min is the optimal operating point

Reuses existing PROCESS physics: Bosch-Hale reactivity, IPB98(y,2) confinement time, Sauter plasma geometry.

Dataclasses: `SizingInputs`, `PowerBalanceResult`, `PointResult`, `SizingResult`.

### New: `process/sizing_runner.py`

Entry point for running validation cases (`python3 -m process.sizing_runner`).

Initial validation: EU-DEMO 2018 baseline (P_net = 500 MW, Q_eng = 3.0, Nb3Sn at 5.3 T).
Result: R = 8.32 m vs 9.1 m reference (-8.6%) **[PASS]**

### Files added

- `process/sizing.py`
- `process/sizing_runner.py`

---

## Validation Summary

| Design | Reference R (m) | Computed R (m) | Deviation | Binding Constraint |
|---|---|---|---|---|
| EU-DEMO | 9.1 | 8.25 | -9.4% | confinement |
| ARC | 3.3 | 3.54 | +7.3% | p_sep_r |
| STR480 | 4.8 | 5.46 | +13.7% | confinement |

All within the ±15% acceptance band.
