[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8335291.svg)](https://doi.org/10.5281/zenodo.8335291) [![codecov](https://codecov.io/gh/ukaea/process/graph/badge.svg?token=F94XDNUIX0)](https://codecov.io/gh/ukaea/process)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ukaea/PROCESS/HEAD?urlpath=%2Fdoc%2Ftree%2Fexamples%2F)
# PROCESS

**Here are the [PROCESS docs](https://ukaea.github.io/PROCESS/).**

PROCESS is the reactor systems code at the [UK Atomic Energy Authority](https://www.ukaea.org/). More information on PROCESS can be found on the PROCESS [webpage](https://www.ukaea.org/service/process/).

PROCESS was originally a Fortran code, but is now a pure-Python command line program. PROCESS is still undergoing a significant restructure and, as such, **PROCESS version 3 is unstable and does not guarantee backward compatibility**. PROCESS version 4 will be the first major version to enforce backward-compatible API changes and will be released following a refactor of the data structure. 



![Blender_and_output](./documentation/images/README_image.PNG)
<center>Overview of some outputs for a DEMO-like reactor.</center>


## Getting Started
Please see the [installation guide](https://ukaea.github.io/PROCESS/installation/installation/) and the [usage guide](https://ukaea.github.io/PROCESS/usage/running-process/). Once installed, take a look at the [examples page](https://ukaea.github.io/PROCESS/usage/examples/) for examples of how PROCESS can be run, and its results visualised.

If you wish to run the examples before installing, you can click on the `binder` badge at the top of the README, or
can click [here](https://mybinder.org/v2/gh/ukaea/PROCESS/HEAD?urlpath=%2Fdoc%2Ftree%2Fexamples%2F). Once loaded, you will be able to run the PROCESS examples in your web browser.

---

## TokamakSizeOptimizatIonTool

A standalone **outside-in reactor sizing tool** that determines the minimum feasible major radius for a tokamak given net electric power and engineering gain targets.

### How It Works

Unlike PROCESS's standard inside-out solver (which varies 15+ free variables simultaneously), this tool uses an inverted approach:

1. **Top-down power balance** — Given P_net and Q_eng, derive P_fusion, P_HCD, and Q_plasma analytically.
2. **Ion temperature sweep** — Sweep T_i over a user-defined range (default 8–30 keV).
3. **Minimum-radius search** — For each T_i, use bisection to find the smallest major radius R that satisfies all physics constraints:
   - **Greenwald density limit** (n_e / n_GW ≤ f_gw_max)
   - **Troyon beta limit** (beta_N ≤ beta_N_max)
   - **Kink stability** (q95 ≥ q95_min)
   - **Confinement** (H_required ≤ H_max, using IPB98(y,2) scaling)
4. **Select optimum** — The T_i that yields the smallest R_min is the optimal operating point.

### Quick Start

```bash
# From the PROCESS root directory (after installing PROCESS):
python3 -m process.sizing_runner
```

This runs an EU-DEMO validation case (P_net = 500 MW, Q_eng = 3.0, Nb3Sn at 5.3 T) and prints the power balance, optimal operating point, and full T_i sweep table. Expected output: R ≈ 8.3 m (within ~9% of EU-DEMO's 9.1 m).

### Using in Your Own Script

```python
from process.sizing import SizingInputs, TokamakSizeOptimizatIonTool

inputs = SizingInputs(
    # Required: power targets
    p_net_mw=500.0,          # Net electric power [MW]
    q_eng=3.0,               # Engineering gain P_gross/P_recirc

    # Efficiencies
    eta_thermal=0.33,        # Thermal-to-electric conversion
    eta_wall_plug=0.40,      # HCD wall-plug efficiency
    eta_absorption=0.80,     # Plasma absorption fraction
    f_aux_recirc=0.80,       # Fraction of recirculating power to non-HCD loads

    # Blanket
    m_blanket=1.14,          # Blanket energy multiplication factor

    # Geometry (fixed by concept selection)
    aspect=3.1,              # Aspect ratio R/a
    kappa=1.65,              # Elongation
    triang=0.33,             # Triangularity

    # Magnetic field (fixed by superconductor choice)
    b_t=5.3,                 # Toroidal field on axis [T]
    fuel_type="DT",          # Fuel: "DT", "DHe3", or "DD"

    # Physics limits
    q95_min=3.0,             # Minimum safety factor
    beta_n_max=2.8,          # Maximum normalised beta
    h_max=1.1,               # Maximum H-factor (IPB98y2)
    f_gw_max=1.2,            # Maximum Greenwald fraction

    # Temperature sweep
    t_i_range_kev=(8.0, 30.0),  # Ion temperature range [keV]
    t_i_steps=50,               # Number of sweep points

    # Profile and loss physics
    profile_factor=2.0,      # Density profile peaking factor
    f_rad=0.50,              # Radiated power fraction
    f_fuel_dilution=0.85,    # Fuel dilution (He ash + impurities)
)

result = TokamakSizeOptimizatIonTool(inputs)

# Key outputs
print(f"R_major   = {result.r_major_m:.2f} m")
print(f"T_i       = {result.t_i_optimal_kev:.1f} keV")
print(f"P_fusion  = {result.power_balance.p_fusion_mw:.0f} MW")
print(f"I_p       = {result.i_p_ma:.2f} MA")
print(f"beta_N    = {result.beta_n:.3f}")
print(f"H_req     = {result.h_required:.3f}")
print(f"f_GW      = {result.f_gw:.3f}")
print(f"Binding   = {result.binding_constraint}")

# Full sweep data: list of (T_i, R_min, binding_constraint)
for t_i, r_min, binding in result.sweep_results:
    print(f"  T_i={t_i:.1f} keV  R_min={r_min:.2f} m  [{binding}]")
```

### Input Parameters Reference

| Parameter | Description | Typical DEMO Value |
|-----------|-------------|-------------------|
| `p_net_mw` | Net electric power target [MW] | 500 |
| `q_eng` | Engineering gain (P_gross / P_recirc) | 3.0 |
| `eta_thermal` | Thermal-to-electric efficiency | 0.33 (He-cooled) |
| `eta_wall_plug` | HCD wall-plug efficiency | 0.40 (ECRH) |
| `eta_absorption` | Plasma absorption fraction | 0.80 |
| `f_aux_recirc` | Non-HCD fraction of recirculating power | 0.80 |
| `m_blanket` | Blanket energy multiplication | 1.14 (HCPB) |
| `aspect` | Aspect ratio R/a | 3.1 |
| `kappa` | Plasma elongation | 1.65 |
| `triang` | Plasma triangularity | 0.33 |
| `b_t` | Toroidal field on axis [T] | 5.3 (Nb3Sn) |
| `fuel_type` | Fuel cycle: `"DT"`, `"DHe3"`, or `"DD"` | `"DT"` |
| `q95_min` | Minimum edge safety factor | 3.0 |
| `beta_n_max` | Maximum normalised beta | 2.8 |
| `h_max` | Maximum H-factor (IPB98y2) | 1.1 |
| `f_gw_max` | Maximum Greenwald density fraction | 1.2 |
| `t_i_range_kev` | Ion temperature sweep range [keV] | (8, 30) |
| `t_i_steps` | Number of temperature sweep points | 50 |
| `profile_factor` | Density profile peaking factor | 2.0 |
| `f_rad` | Radiated power fraction | 0.50 |
| `f_fuel_dilution` | Fuel dilution factor (1.0 = no dilution) | 0.85 |

### Output Fields

The `SizingResult` object contains:

| Field | Description |
|-------|-------------|
| `r_major_m` | Optimal major radius [m] |
| `t_i_optimal_kev` | Optimal ion temperature [keV] |
| `n_e_m3` | Electron density [m^-3] |
| `i_p_ma` | Plasma current [MA] |
| `beta_n` | Normalised beta at operating point |
| `h_required` | Required H-factor (IPB98y2) |
| `f_gw` | Greenwald fraction at operating point |
| `vol_plasma_m3` | Plasma volume [m^3] |
| `binding_constraint` | Which constraint sets R_min |
| `power_balance` | `PowerBalanceResult` with P_fusion, P_gross, P_recirc, Q_plasma, etc. |
| `sweep_results` | List of `(T_i, R_min, binding)` tuples from the full sweep |

---


## Documentation
To read about how the code works and the modules in it see the [documentation](https://ukaea.github.io/PROCESS/).

## Tracking and Testing
Process uses a mixture of tracking and testing to ensure code reliability. Tests are run on each branch and ensure the output of key functions are correct. Tracking, on the other hand, shows graphs of changes to variables over time, and what commit caused the change.

* Our tracker can be found here: https://ukaea.github.io/PROCESS/tracking.html
* Documentation on testing can be found here: https://ukaea.github.io/PROCESS/development/testing/

## Development
Please see the [CONTRIBUTING.md](https://github.com/ukaea/PROCESS/blob/main/CONTRIBUTING.md) for guidance on how to contribute to PROCESS. Further information is found in the development section of the [documentation](https://ukaea.github.io/PROCESS/development/git-usage/).

## Publications
A list of publications using PROCESS is given [here](https://ukaea.github.io/PROCESS/publications), including two papers outlining the physics and engineering models in PROCESS.

## Citing PROCESS
If you use PROCESS in your work, please cite it using the "Cite this repository" link in the "About" section of the repository. This will cite the latest version of PROCESS, if you are using a different release please find the appropriate DOI on [PROCESS' Zenodo page](https://doi.org/10.5281/zenodo.8335291). To ensure reproducible research, we recommend you run an [official release of PROCESS](https://github.com/ukaea/PROCESS/releases) by checking out the appropriate git tag.

## Contacts
[James Morris](mailto:james.morris2@ukaea.uk)

[Jonathan Maddock](mailto:jonathan.maddock@ukaea.uk)

[Michael Kovari](mailto:michael.kovari@ukaea.uk)

[Stuart Muldrew](mailto:stuart.muldrew@ukifs.uk)
