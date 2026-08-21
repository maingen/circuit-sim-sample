# IHP SG13G2 25-Gbaud differential TIA

Create `/app/candidate.cir`, a flat Ngspice circuit for a complete 3.3 V differential optical-receiver front end. The circuit must contain two input TIA branches with DC-overload cancellation, two gain-controlled RF stages, a differential output buffer, a peak detector, an AGC amplifier, and manual/automatic gain selection.

Use the installed IHP Open PDK SG13G2 models. The supported active-device subcircuits are `npn13G2`, `npn13G2v`, `sg13_hv_nmos`, and `sg13_hv_pmos`; use their documented terminal order and legal dimensions. Passive elements may be resistors, capacitors, or inductors. Do not replace an active block with a behavioral source, controlled source, built-in transistor model, or op-amp macromodel.

The submission must be a single flat circuit ending in `.end`. Do not add `.include`, `.lib`, analysis, measurement, control, file-access, parameter, function, or save directives. The verifier supplies the PDK corners, sources, and analyses. Independent sources may only represent the external supply/control/input fixtures; the verifier removes those before simulation.

## Public interface

These node names are the circuit's external or block-test interface and must be present:

- Name the supply and control nodes `vcc`, `mc`, `mgc`, and `oa`.
- Name the photodiode inputs and receiver outputs `inp`, `inn`, `finalp`, and `finaln`.
- Name the gain-control loop nodes `gc` and `agc`.
- Name the output-buffer test nodes `bufinp`, `bufinn`, `outp`, and `outn`.
- Name the peak-detector test nodes `pkdinp`, `pkdinn`, `detp`, and `detn`.

All other node names and every element name are your choice. Internal connectivity and simulated behavior are graded; internal spelling is not.

## Operating conditions and targets

Unless a test says otherwise, the fixture uses `vcc = 3.300 V`, `mc = 0 V`, `mgc = 1.400 V`, `oa = 1.200 V`, the typical HBT corner, and the typical high-voltage MOS corner. The values below are from the supplied Path 3 SG13G2 reference simulated with Ngspice 46. Central targets receive full credit within 5% normalized error; limits are one-sided.

At zero input current, the circuit must meet these targets:

- The input common-mode target is `0.7594 V`.
- The input mismatch must not exceed `1.000 mV`.
- The final-output common-mode target is `2.781 V`.
- The final differential offset must not exceed `1.000 mV`.
- The total 3.3 V supply-power target is `0.2149 W`.

For AC analysis, the fixture applies equal-magnitude, opposite-polarity AC currents at `inp` and `inn` and sweeps 1 MHz to 100 GHz. Across `mgc = 1.250, 1.300, 1.350, 1.400 V`, the gain must increase monotonically. The circuit must also meet these targets:

- The 10 MHz transimpedance target at `mgc = 1.250 V` is `72.20 dB-ohm`.
- The 10 MHz transimpedance target at `mgc = 1.400 V` is `73.94 dB-ohm`.
- The gain-control span target is `1.732 dB`.
- The 33 GHz transimpedance target at maximum gain is `71.69 dB-ohm`.
- The minimum 3 dB bandwidth over all four gain settings must be at least `33.54 GHz`.
- The group-delay target near 10 GHz at maximum gain is `27.62 ps`.

For the DC-overload test, the fixture injects `500.0 uA` into `inp` and `375.0 uA` into `inn`. The larger input voltage must be no more than `0.8042 V`, input mismatch no more than `7.967 mV`, and final differential offset no more than `1.000 mV`.

The output-buffer test directly drives `bufinp` and `bufinn` at a `2.235 V` common mode with a 1 GHz differential sine and places 100 ohms differentially across `outp` and `outn`:

- A `445.0 mVpp` input must produce `596.7 mVpp` output with no more than `0.5043%` THD.
- A `735.0 mVpp` input must produce `927.4 mVpp` output.

The peak-detector test directly drives `pkdinp` and `pkdinn` at a `2.092 V` common mode and 33.5 GHz. Its average absolute differential output must increase strictly for `50.00, 200.0, 400.0, 550.0 mVpp` inputs. The endpoint targets are `25.50 mV` at 50 mVpp and `526.9 mV` at 550 mVpp.

The AGC amplifier target is `15.03 V/V`. In manual mode (`mc = 0 V`), `gc` targets `1.250 V` and `1.400 V` for the corresponding `mgc` values. In automatic mode (`mc = 3.3 V`), an applied `agc = 1.300 V` must produce `gc = 1.300 V`.

For the 25-Gbaud PAM4 transient, the fixture uses a 40 ps UI and opposite-polarity input currents whose differential levels are `-200.0, -66.67, +66.67, +200.0 uA`. Target a final differential output of `1.020 Vpp`, a minimum sampled vertical eye opening of at least `143.6 mV`, and three positive adjacent eye openings.

## Modeling scope

This is a nominal pre-layout SG13G2 simulation. The PDK devices make transistor sizing and voltage stress meaningful, but the task does not include extracted interconnect, package/photodiode parasitics, mismatch, Monte Carlo, or PVT sweeps. Do not claim that it validates silicon BER, worst-case CMRR, or the paper's `12.2 pA/sqrt(Hz)` input-referred-noise result.
