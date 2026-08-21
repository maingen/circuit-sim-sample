# Complete SKY130 WiMAX RF transceiver reconstruction, HARDER

## Objective

Infer, synthesize, and implement the complete transistor-level RF transceiver required for a 3.5 GHz WiMAX base station. The artifact must contain every constituent circuit and a flattened simultaneous end-to-end system. A paper summary, block diagram, behavioral approximation, representative path, partial channel, or idealized subsystem is invalid.

## Required functions and interface

Implement two-stage upconversion from a 10 MHz differential TX input to the 3499 to 3531 MHz band, and two-stage downconversion from the 3399 to 3431 MHz band to a 10 MHz differential RX output. Provide all required gain control, low-noise gain, power gain, RF and IF selectivity, duplexing, biasing, detection, control, oscillator, synthesis, divider, loop, clock-slicing, and LO-distribution functions as physical circuits.

The complete flattened system file is `/app/submission/dut/wimax_transceiver_flat.spice`. Its external nodes are `bbtxp`, `bbtxm`, `rxoutp`, `rxoutm`, `antenna`, `ref_tx`, `ref_rx`, `ref_if`, `div_reset`, `pfd_reset`, `vdd1`, `vdd5`, and `0`. The starter's interface contract defines required standalone artifacts and named measurement nodes. Preserve it exactly.

The system uses a 10 MHz low IF, a 475 MHz first IF, approximately 465 MHz IF conversion, RF LO functions near 3.040 GHz and 2.940 GHz, divide ratios of 64 for the RF synthesis and 32 for IF synthesis, and 3.5 MHz channel bandwidth. All internal LO, clock, bias, gain, power-control, and reference-support functions must be transistor-level. Only true external reference clocks, resets, supplies, RF/baseband inputs, and loads may come from independent testbench sources.

## Legal DUT contract

Use only the pinned public SKY130 subset at `/opt/sky130/sky130_tt_1v8.spice`, commit `f62031a1be9aefe902d6d54cddd6f59b57627436`, TT at 27 C. Use `.option scale=1e-6`, a 1.8 V core, and a 6.5 V PA domain. The verifier uses NGspice 46.

Each DUT file must be a flattened circuit-only fragment. Legal elements are R, L, C and physical SKY130 transistor instances. X is legal only for one allow-listed SKY130 wrapper that resolves directly to one transistor. No candidate-defined hierarchy is permitted.

DUT files must not contain V, I, E, F, G, H, B, S, W, A, T, K, arbitrary D, sources, model cards, includes, libraries, analyses, measurements, Verilog-A/AMS, digital primitives, controlled or behavioral sources, switches, ideal transformers, S-parameters, lookup tables, op-amps, functional subcircuits, vendor macros, or end directives. Testbench sources may exist only in local work decks.

## Measured objectives

At the pinned conditions, the fresh recreated SKY130 ground truth has loaded system frequencies of approximately 3.03150645 GHz, 2.93559022 GHz, and 464.990840 MHz. It produces approximately 22.7866 dBm at the 50 ohm antenna load and 3.23862 mV RMS at the simultaneous differential RX output. The standalone LNA measures approximately 10.0471 dB gain and 3.87642 dB noise figure. The complete RX conversion-gain convention gives -38.4746 dB.

The private objective set also covers all individual functions, currents, filter responses, frequency conversion, oscillator startup, division, loop settling, spectral products, stress, complete TX, complete RX, and simultaneous operation. It uses the actual recreated SKY130 results when they differ from the paper. No topology, component count, device sizing, internal connectivity, passive values, or reference-derived tuning guidance is provided at this tier.

## Submission and grading

Replace every placeholder under `/app/submission/dut/`. Preserve `/app/submission/manifest.json` and the fixed interfaces. Save work decks, logs, and extracted evidence under `/app/submission/work/`.

Every numerical criterion has equal weight. Full credit extends through 1 percent adverse relative error and falls linearly to zero at 10 percent. Missing, failed, or non-finite measurements score zero. Static and adversarial review rejects missing functions or modes, partial paths, hierarchy, external injection at internal nodes, unsafe stress, disconnected decoration, probe bypasses, hard-coded outputs, target-specific dummy branches, fixture manipulation, and any non-SKY130 or forbidden device. Any mandatory violation makes the final grade zero.
