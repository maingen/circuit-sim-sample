# Complete SKY130 MedRadio receiver reconstruction, HARD difficulty

## Objective

Synthesize and implement a complete transistor-level 1 V MedRadio receiver in SKY130. It must receive the 401 MHz to 406 MHz band, generate its own quadrature LO through a fractional-N synthesizer, convert the wanted channel to a 750 kHz low IF, perform complex image rejection, limit the output, and report RSSI.

Submit executable flattened NGspice circuits for the integrated system and every constituent circuit. Partial paths, idealized internal functions, behavioral approximations, and prose submissions are invalid.

## Operating conditions and interface

Use the pinned public SKY130 TT models at 27 degrees Celsius, a 1.0 V supply, and seed 1. The complete circuit must expose `vdd`, `0`, `rfin`, `vo`, `rssi`, `reset`, `ref`, `fb`, `vctrl`, `iop`, `ion`, `qop`, `qon`, `rfout`, `loi_p`, `loi_n`, `loq_p`, and `loq_n`.

The private tests supply only real external power, reset, RF, block-test reference or clock inputs, block-test LO inputs, passive loads, and startup initial conditions. All integrated bias, reference, LO, loop control, division, fractional control, filtering, gain, limiting, and detection functions must be physical transistor circuits.

## Required files and block inventory

Create `candidate.cir` plus these files under `/app/blocks`: `bias.cir`, `lna.cir`, `mixer.cir`, `cbpf.cir`, `tuning.cir`, `limiter.cir`, `crystal.cir`, `pfd_cp.cir`, `por.cir`, `prescaler.cir`, `counter.cir`, `swallow.cir`, `mash.cir`, `qvco.cir`, `synth.cir`, and `receiver.cir`.

The architecture must contain a constant-gm bias, complementary current-reuse LNA, folded I/Q mixers, eighth-order Gm-C complex bandpass filter, filter-tuning oscillator and replica, IF buffer, five limiting stages, two slow offset-cancellation paths, RSSI detector, transistor crystal oscillator, PFD, charge pump, passive loop filter, power-on reset, 8/9 prescaler, five-bit programmable counter, three-bit swallow counter, two ten-bit accumulator stages, QVCO, complete synthesizer, complete analog receiver path, and complete integrated system.

Each block file must be an exact flattened element-line subset of its parent. RF and IF blocks are subsets of `receiver.cir`; synthesizer support blocks are subsets of `synth.cir`; receiver, synthesizer, and tuning are subsets of `candidate.cir`.

## Flattened block node contracts

Because each private fixture inserts a block file directly, use these physical test nodes without `.subckt` wrappers:

- Bias: `vdd`, `0`, `vbn`, `vbp`.
- LNA: `rfin`, `rfout`, `vdd`, `0`, `vbn`, `vbp`.
- I/Q mixer pair: `rfout`, `loi_p`, `loi_n`, `loq_p`, `loq_n`, `ip`, `in`, `qp`, `qn`, `vdd`, `0`, `vbn`, `vbp`.
- Complex filter: `ip`, `in`, `qp`, `qn`, `iop`, `ion`, `qop`, `qon`, `vdd`, `0`, `vbn`, `vbp`.
- Tuning: `tuneclk`, `tune`, `tune_n1` through `tune_n5`, `vdd`, `0`, `vbn`, `vbp`.
- IF buffer, limiter, and RSSI: `iop`, `ion`, `bp`, `bn`, `vo`, `rssi`, `vdd`, `0`, `vbn`, `vbp`.
- Crystal: `ref`, `xtal_xin`, `xtal_xout`, `vdd`, `0`.
- PFD and charge pump: `ref`, `fb`, `reset`, `up`, `dn`, `vctrl`, `vdd`, `0`.
- POR: `reset`, `vdd`, `0`.
- Prescaler: `clk`, `mode`, `reset`, `out`, `q0` through `q3`, `vdd`, `0`.
- Programmable counter: `clk`, `reset`, `p0` through `p4`, `terminal`, `q0` through `q4`, `vdd`, `0`.
- Swallow counter: `clk`, `reset`, `s0` through `s2`, `terminal`, `q0` through `q2`, `vdd`, `0`.
- MASH: `clk`, `reset`, `f0` through `f9`, `y`, `vdd`, `0`.
- QVCO: `loi_p`, `loi_n`, `loq_p`, `loq_n`, `vctrl`, `vdd`, `0`.
- Synthesizer: the four LO nodes, `vctrl`, `ref`, `fb`, `up`, `dn`, `reset`, `vdd`, `0`.
- Receiver: `rfin`, the four LO nodes, `vo`, `rssi`, `iop`, `ion`, `qop`, `qon`, `rfout`, `vdd`, `0`.

Every listed node must connect to the real physical implementation, not a probe alias or dummy branch.

## Legal physical implementation

Include `/opt/pdk/sky130_tt.inc` exactly once per file. Legal DUT elements are R, L, C, M, Q, and X instances that resolve directly to one of these single-transistor wrappers: `sky130_fd_pr__nfet_01v8`, `sky130_fd_pr__pfet_01v8`, `sky130_fd_pr__nfet_01v8_lvt`, or `sky130_fd_pr__nfet_03v3_nvt`.

Do not use candidate-defined `.subckt` hierarchy, independent sources, behavioral or controlled sources, ideal switches, arbitrary diodes, digital primitives, transmission lines, coupled inductors, model cards, Verilog-A, S-parameters, lookup tables, vendor macros, or any include other than the trusted PDK shim.

Tag each element name with one of `BIAS`, `LNA`, `MIX`, `CBPF`, `TUNE`, `LIM`, `XTAL`, `PFD`, `CP`, `DIV`, `COUNT`, `MASH`, `POR`, or `QVCO` immediately after its device prefix. Expose startup nodes `tune_n1` through `tune_n5`, `xtal_xin`, and `xtal_xout`. End every file with `.end`.

## Signal plan and fundamental verified targets

The intended RF center is about 403 MHz and the wanted low IF is 750 kHz. The transistor crystal reference is near 5 MHz. The dual-modulus prescaler must work in both modes at the actual LO rate. The QVCO must provide four true quadrature phases and respond monotonically to `vctrl`.

The actual reference replay produced these fundamental nominal results:

- The LNA has 12.0617 dB gain and -14.7939 dB S11 at 403 MHz.
- The complex filter has 8.74714 dB gain and 62.0990 dB image rejection at 750 kHz.
- The limiter output is 1.00037 V peak-to-peak.
- The crystal oscillator runs at 5.065045 MHz.
- Divide-by-8 and divide-by-9 outputs at 403 MHz are 50.37479 MHz and 44.77759 MHz.
- The QVCO runs at 402.8264 MHz and has 35.411 MHz/V tuning sensitivity.
- The complete reset-held startup test produces a 402.0948 MHz internal LO.

You must choose the detailed topology, internal connectivity, bias levels, device dimensions, passive values, stabilization, startup method, and control implementation.

HARD scoring grades all 44 numerical criteria equally. It gives full credit through 5 percent adverse normalized error and zero credit at 25 percent. Missing or non-finite measurements receive zero.

## Integrity rules

The verifier recursively checks includes, X resolution, flattening, device tags, block inclusion, physical connectivity, major-block coverage, and simulations. Any forbidden primitive, internal ideal source, missing block, decorative or disconnected implementation, output bypass, target-specific dummy branch, supply-current padding, unsafe device use, reference access, or grader manipulation makes the final grade zero.
