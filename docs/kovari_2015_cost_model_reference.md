# Kovari 2015 Cost Model Reference

## Core Methodology: ITER-Referenced Power Law Scaling

Every cost item uses the same formula:

```
s_cost[i] = cost_factor[i] × s_cref[i] × (s_k[i] / s_kref[i])^costexp
```

| Term | Meaning |
|------|---------|
| `s_cref[i]` | ITER reference cost (2014$) |
| `s_k[i]` | Design parameter (computed from physics/engineering) |
| `s_kref[i]` | ITER reference value for that parameter |
| `costexp` | Scaling exponent (default 0.8) |
| `cost_factor[i]` | User multiplier (default 1.0) |

## Cost Categories (s_cost array, 0-indexed)

| Index | Category | Scaling Parameter(s) |
|-------|----------|---------------------|
| 0-8 | **Buildings** | Cryostat volume, NB power, cryopower, PF coil radius, TF current, stored energy, thermal power |
| 9-12 | **Land** | Cryostat footprint area, TF coil size |
| 13-20 | **TF Coils** | Coil length, turn length, Cu mass, SC mass |
| 21-26 | **FWBS** | Li enrichment SWU, pebble masses, FW area, steel+shield mass |
| 27-30 | **Remote Handling** | Armor/FW/blanket total mass |
| 31-33 | **Vacuum Vessel + LN2** | VV outer radius², cryopower |
| 34 | **Balance of Plant** | Gross electric power |
| 35-60 | **Remaining Subsystems** | CS/PF coil parameters, VV mass, separatrix power, fusion power, HCD power, cryostat dimensions, etc. |

Each category subtotal is stored at the last index (e.g., s_cost[8] = total buildings, s_cost[26] = total FWBS).

## Key Physics/Engineering Inputs

The model doesn't do any physics itself. It consumes outputs from other PROCESS modules:

- **Geometry**: cryostat dimensions, VV radius, TF coil lengths, FW area
- **Masses**: TF Cu/SC, blanket pebbles, steel, VV, armor
- **Powers**: fusion, thermal, gross/net electric, HCD injected, NB wall-plug, separatrix
- **Magnetics**: TF current, stored energy, PF coil I×T×R sum, cryopower
- **Availability**: `cpfact` (capacity factor from pulse timing)

## Key Outputs

| Variable | Units | Description |
|----------|-------|-------------|
| `s_cost[0-60]` | $ | Individual item costs (displayed as M$ in output via /1e6) |
| `total_costs` | $ | Sum of 8 category subtotals |
| `concost` | M$ | `total_costs / 1e6` — used as optimizer figure of merit |
| `coe` | $/MWh | Levelized cost of electricity |
| `maintenance` | $ | Annual maintenance (legacy formula) |
| `mean_electric_output` | MW | Net power × effective availability |
| `annual_electric_output` | MWh | Mean output × 8766 hours |

## Modifications Added On Top of Original Kovari Model

The original Kovari model computed FOAK costs in 2014$ with a simple LCOE. Our modifications add:

1. **NOAK learning** (Wright's law per category, applied to s_cost after calc_* methods)
2. **Inflation** (2014$ → 2026$ at 1.37×)
3. **CRF-based LCOE** with OPEX, replacement costs, and availability reduction from downtime

All three are applied as post-processing multipliers on the freshly-computed s_cost array each evaluation, keeping idempotency intact.

---

## Scaling Exponent by Cost Item

The defaults are `costexp = 0.8` and `costexp_pebbles = 0.6`. Every item:

| Index | Item | Exponent | Notes |
|-------|------|----------|-------|
| 0 | Admin buildings | **1.0** (linear) | Fixed: `cref` only, no k/kref ratio |
| 1 | Tokamak complex | **1.0** (linear) | `k/kref` ratio but no exponent applied |
| 2 | NB buildings | **1.0** (linear) | All buildings use linear scaling |
| 3 | Cryoplant buildings | **1.0** (linear) | |
| 4 | PF winding building | **1.0** (linear) | |
| 5 | Magnet PS buildings | **1.0** (linear) | |
| 6 | Magnet discharge buildings | **1.0** (linear) | |
| 7 | Heat removal buildings | **1.0** (linear) | |
| 9 | Land purchasing | **costexp** (0.8) | Applied only to the "key buildings" 42 ha portion; 138 ha buffer is fixed |
| 10 | Land improvement | **costexp** (0.8) | |
| 11 | Road improvements | **costexp** (0.8) | |
| 13 | TF insertion/welding | **costexp** (0.8) | |
| 15 | TF winding | **costexp** (0.8) | |
| 16 | Cu strand | **costexp** (0.8) | |
| 17 | Nb3Sn SC strand | **costexp** (0.8) | |
| 18 | SC testing | **none** (fixed) | No scaling parameter — flat $4M |
| 19 | Cabling/jacketing | **costexp** (0.8) | |
| 21 | Li enrichment | **costexp** (0.8) | |
| 22 | Li2O pebbles | **costexp_pebbles** (0.6) | |
| 23 | TiBe pebbles | **costexp_pebbles** (0.6) | |
| 24 | FW W coating | **costexp** (0.8) | |
| 25 | Blanket/shield mfg | **costexp** (0.8) | |
| 27 | RH moveable equipment | **costexp** (0.8) | |
| 28 | RH fixed equipment | **costexp** (0.8) | |
| 31 | Vacuum vessel | **costexp** (0.8) | |
| 32 | LN2 plant | **costexp** (0.8) | |
| 34 | Energy conversion (BOP) | **costexp** (0.8) | |
| 35 | CS and PF coils | **costexp** (0.8) | |
| 36 | VV in-wall shielding | **costexp** (0.8) | |
| 37 | Divertor | **costexp** (0.8) | |
| 40 | NB RH equipment | **costexp** (0.8) | |
| 42 | VV pressure suppression | **costexp** (0.8) | |
| 43 | Cryostat | **costexp** (0.8) | |
| 44 | Heat removal system | **costexp** (0.8) | |
| 45 | Thermal shields | **costexp** (0.8) | |
| 46 | Pellet injection | **costexp** (0.8) | |
| 47 | Gas injection | **costexp** (0.8) | |
| 48 | Vacuum pumping | **costexp** (0.8) | |
| 49 | Tritium plant | **costexp** (0.8) | |
| 50 | Cryoplant | **costexp** (0.8) | |
| 51 | Electrical power supply | **costexp** (0.8) | |
| 52 | NB H&CD system | **costexp** (0.8) | |
| 53 | Diagnostics | **none** (fixed) | Flat $640M, no scaling |
| 54 | Radiological protection | **costexp** (0.8) | |
| 55 | Access control/security | **costexp** (0.8) | |
| 56 | Assembly | **1.0** (linear) | Explicitly: ratio with no exponent |
| 57 | Control & communication | **costexp** (0.8) | |
| 58 | Additional project expenditure | **none** (fixed) | Flat $1,624M |
| 59 | Logistics | **costexp** (0.8) | |

Summary: Most items use `costexp` (default 0.8). Buildings are linear (exponent 1). Pebbles use `costexp_pebbles` (0.6). Three items are fixed costs with no scaling at all (SC testing $4M, diagnostics $640M, additional project expenditure $1,624M). Assembly scales linearly with total reactor component costs.

---

## Applicability: Is This Tokamak-Only?

**Practically yes**, though not structurally locked to tokamaks. The ITER-specific dependencies are:

- **All 60+ reference costs** (`s_cref`) are ITER contract values in 2014$
- **All reference parameters** (`s_kref`) are ITER values (18 TF coils × 34.1m, 18,712 m³ cryostat, 500 MW fusion, etc.)
- **Scaling parameters** (`s_k`) use tokamak-specific variables: TF coils, PF coils, central solenoid, divertor separatrix power, cryostat geometry

For a stellarator or other concept, you'd need to replace most `s_kref` values, adjust the scaling parameters (no central solenoid, different coil geometry), and potentially add new cost items. The power-law-with-ITER-reference methodology could still work, but you'd essentially be rewriting the cost database.

---

## Land Cost Details

Land cost is **not** just the cryostat footprint. There are three components:

**s_cost[9] — Land purchasing**: Uses a two-part formula:
```
cost = price_per_ha × (42 ha × (cryostat_area / 638)^0.8 + 138 ha)
```
- The 42 ha "key buildings" area scales with your cryostat footprint (638 m² is ITER's)
- The 138 ha "buffer land" is **fixed** regardless of plant size
- Land price: $318,000/ha (2014$)
- So for a larger-than-ITER machine, only the inner 42 ha portion grows; the 138 ha safety buffer stays constant

**s_cost[10] — Land improvement/clearing**: $214M ITER reference, scaled by cryostat footprint area with exponent 0.8

**s_cost[11] — Road improvements**: $150M ITER reference, scaled by **TF coil longest dimension** (height or width + 2× inboard thickness), with exponent 0.8 — the idea being that larger coils require wider transport corridors

So land uses the cryostat footprint as a **proxy for plant size**, not as the literal land area. The ITER site is 180 ha total for a 638 m² cryostat footprint — the scaling captures how a larger reactor drives a proportionally larger site.
