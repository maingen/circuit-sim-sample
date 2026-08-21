# Complete SKY130 WiMAX RF transceiver reconstruction, HARD

## Objective

Synthesize and implement a complete transistor-level dual-conversion RF transceiver for a 3.5 GHz WiMAX base station. Deliver every required constituent circuit and a flattened simultaneous end-to-end system. Partial channels, representative paths, behavioral stand-ins, and block-diagram submissions are invalid.

## External interface and required functions

The complete system file is `/app/submission/dut/wimax_transceiver_flat.spice`. Its external nodes are `bbtxp`, `bbtxm`, `rxoutp`, `rxoutm`, `antenna`, `ref_tx`, `ref_rx`, `ref_if`, `div_reset`, `pfd_reset`, `vdd1`, `vdd5`, and `0`. Preserve the required named probe nodes, standalone block files, and block interfaces in `/app/submission/interface_contract.json` and `/app/submission/manifest.json`.

The TX path must provide input gain control, two frequency conversions, two separate first-IF filters, an intervening IF gain stage, RF filtering, driver gain, power amplification, and duplexer delivery. The RX path must provide duplexer/RF filtering, low-noise amplification, two frequency conversions, first-IF filtering and gain, low-IF filtering, and output gain.

Implement three complete internal frequency synthesizers, including transistor-level oscillators, phase/frequency comparison, charge pumping, division, loop control, slicing, and LO distribution. Implement transistor-level bias, detector, gain-control, power-control, and control-logic support. The complete system must use these internal circuits. Only true external references and resets may be driven by the testbench.

The signal plan is 10 MHz to 475 MHz to a 3499 to 3531 MHz TX band, and a 3399 to 3431 MHz RX band to 475 MHz to 10 MHz. Use an approximately 465 MHz shared IF LO, an approximately 3.040 GHz TX RF LO, and an approximately 2.940 GHz RX RF LO. RF synthesizers divide by 64 and the IF synthesizer divides by 32. The channel bandwidth is 3.5 MHz.

## Pinned implementation contract

Use the local public SKY130 model wrapper `/opt/sky130/sky130_tt_1v8.spice`, sourced from commit `f62031a1be9aefe902d6d54cddd6f59b57627436`. Use TT at 27 C, `.option scale=1e-6`, a 1.8 V core, and a 6.5 V PA supply. NGspice 46 is the authority.

Every DUT file must be flattened. Legal devices are physical R, L, C and SKY130 transistors. An X instance is legal only when it is one allow-listed wrapper for one physical SKY130 transistor. Candidate-defined subcircuits and functional X instances are forbidden. DUT files may not contain sources, includes, libraries, model cards, analyses, measurements, or end directives.

Rejectable elements include V, I, E, F, G, H, B, S, W, A, T, K, arbitrary D, Verilog-A/AMS, digital primitives, dependent or behavioral sources, ideal switches or transformers, S-parameters, lookup tables, predefined op-amps, and vendor macros. Independent sources belong only in local testbenches under `/app/submission/work/`.

## Fundamental calibrated objectives

Fresh NGspice ground truth at the pinned conditions has simultaneous loaded LOs near 3.03150645 GHz, 2.93559022 GHz, and 464.990840 MHz. The complete system delivers about 22.7866 dBm to the 50 ohm antenna load and about 3.23862 mV RMS differential RX output. The standalone LNA has about 10.0471 dB gain and 3.87642 dB noise figure. The complete RX conversion-gain convention yields -38.4746 dB.

The grader uses the recreated SKY130 circuit's actual behavior. It does not replace the ground truth with the paper's unreproduced 95 dB gain or -52 dBc IMD claim. You must synthesize, bias, stabilize, size, and tune all topology and component choices yourself.

## Submission and grading

Replace every placeholder in `/app/submission`, keep reproducible work and logs under `/app/submission/work/`, and deliver all 38 populated flattened DUT files. The private verifier runs block-level and integrated NGspice analyses and audits completeness, connectivity, model provenance, stress, source placement, and anti-shortcut behavior.

Every numerical criterion has equal weight. Full credit extends through 5 percent adverse relative error and falls linearly to zero at 25 percent. Missing, failed, or non-finite measurements score zero. Any mandatory eligibility violation makes the final grade zero.
