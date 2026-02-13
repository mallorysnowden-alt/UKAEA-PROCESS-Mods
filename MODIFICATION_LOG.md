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

## Validation

PROCESS finds a feasible solution with complete output (1.09 MB MFILE.DAT, 177 KB OUT.DAT)
using the modified `large_tokamak_IN.DAT`. Key results:

| Parameter | Value |
|-----------|-------|
| rmajor | 6.69 m |
| p_fusion_total_mw | 1,672 MW |
| coe | 6,019 m$/kWh |
| capcost | 9,741 M$ |
| f_t_plant_available | 0.80 |
| Net electric power | ~400 MW |

Cost basis: NOAK (fkind=1.0), LSA=4 (most conservative safety assurance level).
