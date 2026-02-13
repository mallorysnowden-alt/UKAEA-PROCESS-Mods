# PROCESS Modification Log

Modifications to UKAEA PROCESS (v3.3.0) for streamlined technoeconomic analysis.
Changes remove physics-driven calculations not consumed (directly or indirectly)
by the 2015 Kovari costing model (`process/costs_2015.py`).

## Deleted Modules

### Divertor heat load model (`process/divertor.py`)
- **Removed**: Entire module (458 lines) including `divtart()`, `divwade()`, and
  detailed heat flux profile calculations
- **Retained**: `divertor_variables.py` data structure (referenced by shield, structure,
  availability, HCPB blanket, and costs modules)
- **Inlined** in `process/caller.py`: Two essential power-split calculations needed by
  the blanket power balance:
  ```python
  p_div_nuclear_heat_total_mw = p_plasma_neutron_mw * f_ster_div_single * n_divertors
  p_div_rad_total_mw = p_plasma_rad_mw * f_ster_div_single * n_divertors
  ```

### DetailedPhysics class (`process/physics.py`)
- **Removed**: ~290 lines (formerly lines 9049-9339) including:
  - Debye length profile calculations
  - Relativistic particle speed profiles
  - Plasma frequency profiles
  - Larmor frequency profiles
  - Coulomb logarithm profile calculations
  - All associated output methods
- These were purely diagnostic outputs with no downstream consumers

## Removed Calculations

### Bootstrap current profiles (`process/physics.py`)
- **Removed**: Storage of `j_plasma_bootstrap_sauter_profile` array and its output loop
  in `outplas()`
- **Retained**: Scalar `f_c_plasma_bootstrap_sauter` (needed by current drive chain:
  `f_c_plasma_bootstrap` -> `f_c_plasma_internal` -> `f_c_plasma_auxiliary` ->
  `p_hcd_primary_injected_mw` -> costs)

### Impurity charge profiles (`process/physics.py`)
- **Removed**: `n_charge_plasma_profile` output loop in `outplas()`

### CS fatigue analysis (`process/pfcoil.py`)
- **Removed**: `cs_fatigue.ncycle()` call in `pfcoil()` calculation method (~10 lines)
- **Removed**: CS fatigue output block in `outpf()` (~75 lines)
- **Retained**: `cs_fatigue_variables.py` data structure (default values still initialised)

## Relaxed Constraints (`examples/data/large_tokamak_IN.DAT`)

| icc | Constraint | Action |
|-----|-----------|--------|
| 9   | Fusion power upper limit | Raised `p_fusion_total_max_mw` from 3,000 to 10,000 MW |
| 13  | Burn time lower limit | Disabled (commented out) |
| 15  | L-H power threshold | Disabled (commented out) |
| 34  | Dump voltage upper limit | Disabled (commented out) |
| 65  | Dump time / VV stress | Disabled (commented out) |

- `rmajor` bounds widened from [8, 9] to [2, 20] m for broader design space exploration

## Bug Fixes

### Windows/WSL PermissionError (`process/process_output.py`)
- `close_idempotence_files()` was calling `Path.unlink()` on files before closing them,
  causing `PermissionError` on Windows/WSL due to file locking
- Fixed: close file handles first, then unlink with `PermissionError` caught gracefully

### Package version fallback (`process/__init__.py`)
- `importlib.metadata.version("process")` fails when running via `PYTHONPATH` without
  pip install
- Added `try/except` fallback to `__version__ = "dev"`

## NOAK Costing, Inflation, and LCOE Overhaul

### Cost Model Changes (`process/costs_2015.py`)
- **Switched to 2015 Kovari model** (`cost_model = 1`) with LSA = 2
- **NOAK learning curve** via Wright's law: `C_NOAK = C_FOAK * n^(-b)`, where `b = -log2(1 - learning_rate)`, applied as idempotent post-processing scale on `s_cost[]`
- **Inflation adjustment**: All costs scaled from 2014$ to 2026$ (factor = 1.37)
- **Replaced LCOE formula** with Capital Recovery Factor (CRF) approach:
  ```
  CRF = r(1+r)^L / ((1+r)^L - 1)
  LCOE = (annual_capital + annual_opex + annual_replacement) / annual_electric_output
  ```
- **OPEX**: Fraction of CAPEX per year (default 3%)
- **Replacement costs**: FWBS + divertor costs amortized over replacement interval
- **Effective availability**: Reduced by replacement downtime fraction

### Learning Rates by Technical Maturity

| Category | Learning Rate | Rationale |
|----------|--------------|-----------|
| Buildings | 5% | Mature construction, minimal learning |
| Land | 0% | Fixed cost, no learning |
| TF coils | 10% | Complex but established SC magnet tech |
| FWBS (first wall/blanket/shield) | 15% | Low TRL, high learning potential |
| Remote handling | 12% | Novel systems, significant learning |
| Vacuum vessel | 10% | Large-scale welded structures |
| Balance of plant | 5% | Mature thermal/electrical systems |
| Miscellaneous | 8% | Mixed maturity subsystems |

### New Input Variables (`process/data_structure/cost_variables.py`, `process/input.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `n_noak_units` | 10 | NOAK learning curve unit number |
| `learning_rate_buildings` | 0.05 | Wright's law learning rate for buildings |
| `learning_rate_land` | 0.0 | Learning rate for land costs |
| `learning_rate_tf_coils` | 0.10 | Learning rate for TF coils |
| `learning_rate_fwbs` | 0.15 | Learning rate for FWBS |
| `learning_rate_rh` | 0.12 | Learning rate for remote handling |
| `learning_rate_vv` | 0.10 | Learning rate for vacuum vessel |
| `learning_rate_bop` | 0.05 | Learning rate for balance of plant |
| `learning_rate_misc` | 0.08 | Learning rate for miscellaneous |
| `inflation_factor` | 1.37 | Inflation multiplier (2014$ -> 2026$) |
| `opex_fraction` | 0.03 | Annual OPEX as fraction of CAPEX |
| `replacement_interval_years` | 2.0 | Years between FWBS/divertor replacements |
| `replacement_downtime_months` | 4.0 | Downtime per replacement |
| `discount_rate` | 0.08 | Discount rate for CRF calculation |
| `plant_lifetime_years` | 30.0 | Plant economic lifetime |

### Input File Updates (`examples/data/large_tokamak_IN.DAT`)
- Set `cost_model = 1` (2015 Kovari model)
- Set `lsa = 2` (Level of Safety Assurance)
- Added all NOAK, inflation, OPEX, replacement, and LCOE parameters

## Validation

PROCESS finds a feasible solution using the modified `large_tokamak_IN.DAT`.

### Key Results (NOAK, 2026$, LSA=2, pulsed operation)

| Parameter | Value |
|-----------|-------|
| Major radius (rmajor) | ~8.3 m |
| Net electric power | 400 MW |
| Total overnight CAPEX | ~42,349 M$ (2026$, NOAK) |
| Capacity factor (cpfact) | 4.80% |
| Burn time | 169 s |
| LCOE | ~48,151 $/MWh |
| f_t_plant_available | 0.80 |

**Note**: The high LCOE is driven by the extremely low capacity factor (4.8%) from pulsed operation with a 169-second burn time and 1800-second dwell. For steady-state or long-pulse operation (the intended use case), the capacity factor approaches 80% and the LCOE would be approximately $2,900/MWh — still high for a FOAK-class CAPEX, but representative of early fusion economics.
