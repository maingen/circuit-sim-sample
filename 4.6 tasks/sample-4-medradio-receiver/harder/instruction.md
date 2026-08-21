# Complete SKY130 MedRadio receiver reconstruction, HARDER difficulty

## Objective

Infer, synthesize, and implement a complete flattened transistor-level MedRadio receiver in the open-source SKY130 PDK. The system receives 401 MHz to 406 MHz RF, produces a 750 kHz complex low IF, rejects the image, limits the wanted signal, reports RSSI, and generates its own quadrature LO and fractional channel control.

No implementation topology, device count, transistor sizing, passive tuning guidance, or internal connectivity is provided at this difficulty. You must derive every physical circuit from the required functions, interface, legal devices, operating conditions, and measured objectives.

## Operating conditions and public interface

Use the pinned SKY130 TT models at 27 degrees Celsius with a 1.0 V supply and seed 1. The integrated circuit must expose `vdd`, `0`, `rfin`, `vo`, `rssi`, `reset`, `ref`, `fb`, `vctrl`, `iop`, `ion`, `qop`, `qon`, `rfout`, `loi_p`, `loi_n`, `loq_p`, and `loq_n`.

Private tests provide only external power, reset, true RF input, block-level reference or clock input, block-level LO input, passive loads, and startup initial conditions. No testbench source replaces an integrated internal bias, oscillator, LO, reference, loop signal, divider, filter control, gain stage, or data-conversion function.

## Required flattened artifacts

Write `candidate.cir` and the following flattened files under `/app/blocks`: `bias.cir`, `lna.cir`, `mixer.cir`, `cbpf.cir`, `tuning.cir`, `limiter.cir`, `crystal.cir`, `pfd_cp.cir`, `por.cir`, `prescaler.cir`, `counter.cir`, `swallow.cir`, `mash.cir`, `qvco.cir`, `synth.cir`, and `receiver.cir`.

Together they must implement physical bias generation, RF gain and matching, quadrature frequency conversion, eighth-order complex filtering, filter calibration activity, IF buffering, five-stage limiting, offset cancellation, RSSI, a 5 MHz-class crystal reference, phase and frequency comparison, charge pumping and passive loop filtering, power-on reset, dual-modulus prescaling, programmable and swallow counting, two ten-bit fractional accumulator stages, quadrature oscillation, a complete synthesizer, a complete analog receiver, and the integrated end-to-end system.

Every element line in a block artifact must appear unchanged in its integrated parent. The private verifier checks the subset relationship and rejects decorative block files that differ from the circuit used by the full system.

## Flattened block test interfaces

The private fixtures insert each artifact directly, without a `.subckt` wrapper. Use these physical node contracts:

- `bias.cir`: `vdd`, `0`, `vbn`, `vbp`.
- `lna.cir`: `rfin`, `rfout`, `vdd`, `0`, `vbn`, `vbp`.
- `mixer.cir`: `rfout`, all four LO nodes, `ip`, `in`, `qp`, `qn`, `vdd`, `0`, `vbn`, `vbp`.
- `cbpf.cir`: `ip`, `in`, `qp`, `qn`, `iop`, `ion`, `qop`, `qon`, `vdd`, `0`, `vbn`, `vbp`.
- `tuning.cir`: `tuneclk`, `tune`, `tune_n1` through `tune_n5`, `vdd`, `0`, `vbn`, `vbp`.
- `limiter.cir`: `iop`, `ion`, `bp`, `bn`, `vo`, `rssi`, `vdd`, `0`, `vbn`, `vbp`.
- `crystal.cir`: `ref`, `xtal_xin`, `xtal_xout`, `vdd`, `0`.
- `pfd_cp.cir`: `ref`, `fb`, `reset`, `up`, `dn`, `vctrl`, `vdd`, `0`.
- `por.cir`: `reset`, `vdd`, `0`.
- `prescaler.cir`: `clk`, `mode`, `reset`, `out`, `q0` through `q3`, `vdd`, `0`.
- `counter.cir`: `clk`, `reset`, `p0` through `p4`, `terminal`, `q0` through `q4`, `vdd`, `0`.
- `swallow.cir`: `clk`, `reset`, `s0` through `s2`, `terminal`, `q0` through `q2`, `vdd`, `0`.
- `mash.cir`: `clk`, `reset`, `f0` through `f9`, `y`, `vdd`, `0`.
- `qvco.cir`: `loi_p`, `loi_n`, `loq_p`, `loq_n`, `vctrl`, `vdd`, `0`.
- `synth.cir`: all four LO nodes, `vctrl`, `ref`, `fb`, `up`, `dn`, `reset`, `vdd`, `0`.
- `receiver.cir`: `rfin`, all four LO nodes, `vo`, `rssi`, `iop`, `ion`, `qop`, `qon`, `rfout`, `vdd`, `0`.

Each named node must participate in the genuine circuit. Probe aliases and dummy branches are invalid.

## Primitive and PDK contract

Each file must include `/opt/pdk/sky130_tt.inc` exactly once and end with `.end`. Legal DUT primitives are physical R, L, C, M, Q, and X instances that resolve directly to one trusted SKY130 transistor wrapper. The only approved wrappers are `sky130_fd_pr__nfet_01v8`, `sky130_fd_pr__pfet_01v8`, `sky130_fd_pr__nfet_01v8_lvt`, and `sky130_fd_pr__nfet_03v3_nvt`.

Candidate-defined hierarchy is forbidden. Do not use independent DUT sources, controlled or behavioral sources, ideal switches, arbitrary diodes, transmission lines, coupled inductors, digital primitives, Verilog-A, S-parameters, lookup tables, unapproved models, vendor macros, or alternate includes.

Tag every physical element name with its functional area immediately after the element prefix. The allowed tags are `BIAS`, `LNA`, `MIX`, `CBPF`, `TUNE`, `LIM`, `XTAL`, `PFD`, `CP`, `DIV`, `COUNT`, `MASH`, `POR`, and `QVCO`. Expose deterministic startup nodes `tune_n1` through `tune_n5`, `xtal_xin`, and `xtal_xout`.

## Measured objectives

The private targets come from a fresh NGspice 46 replay of the reference implementation. Central nominal objectives include:

- 12.0617 dB LNA gain and -14.7939 dB S11 at 403 MHz.
- 8.74714 dB complex-filter gain and 62.0990 dB image rejection at 750 kHz.
- 757.973 kHz filter-tuning activity.
- 1.00037 V peak-to-peak limiter swing and about 0.3859 V RSSI average.
- 5.065045 MHz crystal-reference frequency.
- 50.37479 MHz and 44.77759 MHz prescaler outputs in divide-by-8 and divide-by-9 modes at a 403 MHz input.
- 0.599117 fractional modulus-bit density for F=614.
- 402.8264 MHz QVCO center frequency, 2.18528 V differential peak-to-peak swing, 1.4207 degrees quadrature error, and 35.411 MHz/V tuning sensitivity.
- 402.0948 MHz internal LO frequency during the reset-held complete-hierarchy startup test.

The verifier also grades undisclosed operating points, stopband response, power, startup, multi-mode digital behavior, and integrated activity. It records but does not numerically reward the reference results that require an external ideal LO, full conversion-noise analysis, oscillator phase-noise analysis, long PLL lock, unpublished automatic trim law, or unpublished signed MASH mapping.

HARDER scoring grades every numerical criterion equally. It gives full credit through 1 percent adverse normalized error and zero credit at 10 percent. Missing, failed, or non-finite measurements receive zero.

## Mandatory integrity gates

Any parse or required-simulation failure, forbidden element, non-SKY130 transistor, illegal X instance, user hierarchy, internal ideal source, missing major block, missing channel or mode, disconnected or decorative circuitry, output bypass, hard-coded output, target-specific dummy branch, supply-current padding, unsafe device use, private-file access, or grader manipulation makes the final grade zero. The private review also perturbs RF amplitude, LO conditions, supply, loads, clocks, and modes to detect fixture-specific behavior.
