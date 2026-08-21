# Complete SKY130 MedRadio receiver reconstruction, MID difficulty

## Objective

Build a complete transistor-level 1 V MedRadio receiver in the open-source SKY130 PDK. The receiver accepts a 401 MHz to 406 MHz RF signal, converts it to a 750 kHz low intermediate frequency, filters the complex I/Q signal, limits the output, reports RSSI, and generates its own quadrature LO through a fractional-N synthesizer.

This is an implementation task. Submit executable flattened NGspice circuits for the full system and every required block. A block diagram, prose design, behavioral approximation, partial channel, or externally generated internal function is not a submission.

## Operating conditions and external interface

Use the SKY130 TT models at 27 degrees Celsius, a 1.0 V supply, and random seed 1. The full flattened circuit must use these externally visible nodes:

`vdd`, `0`, `rfin`, `vo`, `rssi`, `reset`, `ref`, `fb`, `vctrl`, `iop`, `ion`, `qop`, `qon`, `rfout`, `loi_p`, `loi_n`, `loq_p`, and `loq_n`.

The private tests provide only the 1 V supply, reset, true RF input, external block-test clocks or references, external block-test LO stimuli, passive loads, and deterministic startup initial conditions. The integrated circuit must generate its own bias, crystal reference, PFD signals, charge-pump control, divider clocks, fractional control, and quadrature LO.

## Required flattened artifacts

Write the following files under `/app`:

- `candidate.cir` contains the complete integrated receiver.
- `blocks/bias.cir` contains the constant-gm bias circuit.
- `blocks/lna.cir` contains the bias circuit and complementary current-reuse LNA.
- `blocks/mixer.cir` contains the folded I/Q mixer pair and required bias circuitry.
- `blocks/cbpf.cir` contains the bias circuit and eighth-order complex bandpass filter.
- `blocks/tuning.cir` contains the relaxation oscillator, replica filter, averaging node, and its transistor bias.
- `blocks/limiter.cir` contains the bias circuit, IF buffer, five limiting stages, offset-cancellation branches, and RSSI detector.
- `blocks/crystal.cir` contains the transistor crystal oscillator.
- `blocks/pfd_cp.cir` contains the PFD and 20 microampere charge pump.
- `blocks/por.cir` contains the transistor power-on-reset circuit.
- `blocks/prescaler.cir` contains both divide-by-8 and divide-by-9 modes.
- `blocks/counter.cir` contains the five-bit programmable counter.
- `blocks/swallow.cir` contains the three-bit swallow counter.
- `blocks/mash.cir` contains both ten-bit accumulator stages and their delay logic.
- `blocks/qvco.cir` contains the complete quadrature VCO.
- `blocks/synth.cir` contains the complete synthesizer, including every support block and the QVCO.
- `blocks/receiver.cir` contains the complete analog RF-to-limiter signal chain for an independent external-LO test.

Every element line in a block file must appear unchanged in its integrated parent. The bias, LNA, mixer, complex filter, and limiter files must be exact subsets of `blocks/receiver.cir`. The crystal, PFD and charge pump, POR, prescaler, counters, MASH, and QVCO files must be exact subsets of `blocks/synth.cir`. The receiver, synthesizer, and tuning files must be exact subsets of `candidate.cir`.

## Flattened block node contracts

The block files have no `.subckt` wrapper. Connect their physical elements directly to these test nodes:

- `bias.cir`: `vdd`, `0`, `vbn`, `vbp`.
- `lna.cir`: `rfin`, `rfout`, `vdd`, `0`, `vbn`, `vbp`.
- `mixer.cir`: `rfout`, `loi_p`, `loi_n`, `loq_p`, `loq_n`, `ip`, `in`, `qp`, `qn`, `vdd`, `0`, `vbn`, `vbp`.
- `cbpf.cir`: `ip`, `in`, `qp`, `qn`, `iop`, `ion`, `qop`, `qon`, `vdd`, `0`, `vbn`, `vbp`.
- `tuning.cir`: `tuneclk`, `tune`, `tune_n1` through `tune_n5`, `vdd`, `0`, `vbn`, `vbp`.
- `limiter.cir`: `iop`, `ion`, internal buffer outputs `bp`, `bn`, `vo`, `rssi`, `vdd`, `0`, `vbn`, `vbp`.
- `crystal.cir`: `ref`, `xtal_xin`, `xtal_xout`, `vdd`, `0`.
- `pfd_cp.cir`: `ref`, `fb`, `reset`, `up`, `dn`, `vctrl`, `vdd`, `0`.
- `por.cir`: `reset`, `vdd`, `0`.
- `prescaler.cir`: `clk`, `mode`, `reset`, `out`, `q0` through `q3`, `vdd`, `0`.
- `counter.cir`: `clk`, `reset`, `p0` through `p4`, `terminal`, `q0` through `q4`, `vdd`, `0`.
- `swallow.cir`: `clk`, `reset`, `s0` through `s2`, `terminal`, `q0` through `q2`, `vdd`, `0`.
- `mash.cir`: `clk`, `reset`, `f0` through `f9`, `y`, `vdd`, `0`.
- `qvco.cir`: `loi_p`, `loi_n`, `loq_p`, `loq_n`, `vctrl`, `vdd`, `0`.
- `synth.cir`: `loi_p`, `loi_n`, `loq_p`, `loq_n`, `vctrl`, `ref`, `fb`, `up`, `dn`, `reset`, `vdd`, `0`.
- `receiver.cir`: `rfin`, the four LO nodes, `vo`, `rssi`, the four complex-filter outputs, `rfout`, `vdd`, `0`.

Every listed functional node must be a genuine physical terminal in that flattened artifact. The grader removes the reference X instance and inserts your corresponding file directly into a private testbench.

## Flattening and device rules

Each file must include `/opt/pdk/sky130_tt.inc` exactly once. Candidate files may contain only physical R, L, C, M, Q, and approved single-transistor X instances. The approved X wrappers are:

- `sky130_fd_pr__nfet_01v8`
- `sky130_fd_pr__pfet_01v8`
- `sky130_fd_pr__nfet_01v8_lvt`
- `sky130_fd_pr__nfet_03v3_nvt`

An X instance is illegal if it resolves to anything other than one of those trusted physical transistor wrappers. Do not define `.subckt` blocks. Do not use independent sources, behavioral sources, dependent sources, switches, arbitrary diodes, transmission lines, mutual inductors, lookup tables, S-parameters, Verilog-A, digital primitives, model cards, or alternate includes inside a DUT file. Testbench sources belong only to the private or disclosed tests.

Name every physical instance with a block tag immediately after the device prefix. Examples are `XLNA_001`, `RCBPF_014`, and `XQVCO_027`. The allowed tags are `BIAS`, `LNA`, `MIX`, `CBPF`, `TUNE`, `LIM`, `XTAL`, `PFD`, `CP`, `DIV`, `COUNT`, `MASH`, `POR`, and `QVCO`.

Expose deterministic startup nodes `tune_n1` through `tune_n5` and `xtal_xin` and `xtal_xout` in the corresponding block files and in the integrated circuit. End every file with `.end`.

## Architecture guidance

Use a complementary shared-source current-reuse LNA with an off-chip gate inductor near 375 nH, an 8 nH and 20 pF source arm, native NMOS input devices, PMOS reuse devices, resistive loads, and capacitive drain combining. The RF mixer is a complementary transconductor followed by PMOS commutating switches and differential RC loads.

Build the complex filter from four transistor Gm-C biquads. A nominal state capacitor near 1.6 pF and a passive polyphase section near 100 kilohms and 2.122 pF are useful SKY130 starting points. Implement cross-coupled I/Q paths with physical transconductors. The filter-tuning circuit should use a transistor relaxation oscillator near the low-IF frequency, a physical replica biquad, and passive averaging.

Use an AC-coupled IF buffer followed by five transistor differential limiting stages. Include two slow passive offset-cancellation paths and a transistor envelope detector whose gates do not suppress limiter gain.

The synthesizer requires a transistor Pierce-style 5 MHz crystal oscillator, transistor PFD, 20 microampere charge pump, passive loop filter, transistor power-on reset, dual-modulus 8/9 prescaler, five-bit programmable counter, three-bit swallow counter, two ten-bit accumulator stages, and a quadrature LC oscillator. Reasonable starting values for the loop filter are 32 kilohms, 1 nF, and 20 pF. Reasonable QVCO starting values are 218 nH per external tank inductor and roughly 650 fF fixed tank capacitance. The VCO must respond to `vctrl` and drive all four LO nodes.

## Essential verified objectives

The private grader uses the actual NGspice 46 reconstruction results, not the paper's measurements. Important nominal objectives are:

- LNA gain at 403 MHz is 12.0617 dB and S11 is -14.7939 dB.
- Complex-filter gain at 750 kHz is 8.74714 dB. Desired-sideband gain is 14.7677 dB, image gain is -47.3313 dB, and image rejection is 62.0990 dB.
- The filter-tuning oscillator runs at 757.973 kHz.
- The limiter produces 1.00037 V peak-to-peak and an RSSI average near 0.3859 V.
- The transistor crystal reference runs at 5.065045 MHz.
- At a 403 MHz input, the prescaler outputs 50.37479 MHz in divide-by-8 mode and 44.77759 MHz in divide-by-9 mode.
- The MASH modulus-bit density for F=614 is 0.599117.
- The QVCO runs at 402.8264 MHz, produces 2.18528 V differential peak-to-peak, has about 1.4207 degrees quadrature error, and tunes at 35.411 MHz/V.
- During the reset-held complete-hierarchy startup test, the internal LO is 402.0948 MHz, its differential swing is 47.0698 mV, and `rfout` is 14.8907 mV peak-to-peak.

MID scoring gives essential criteria twice the weight of nonessential criteria. It gives full credit through 25 percent adverse normalized error and zero credit at 50 percent. Every criterion is still reported.

## Submission integrity

The verifier rejects forbidden elements, user hierarchy, alternate models, internal ideal sources, missing artifacts, missing major blocks, disconnected or decorative blocks, mismatched block subsets, unsafe device use, target-specific dummy branches, hard-coded output, current padding, and any attempt to access or alter private grading files. Work directly in `/app`, preserve useful working files, and finish with all required flattened circuits saved at their exact paths.
