# Complete SKY130 WiMAX RF transceiver reconstruction, MID

## Objective

Implement the complete dual-conversion RF transceiver for a 3.5 GHz WiMAX base station as executable transistor-level NGspice circuits. Deliver every constituent circuit and a flattened simultaneous end-to-end system. A block diagram, paper summary, behavioral approximation, representative channel, or partial signal path is not a submission.

## External system interface

The complete flattened system is `submission/dut/wimax_transceiver_flat.spice`. Its fixed external nodes are:

- Supplies and ground: `vdd1`, `vdd5`, and `0`.
- Differential TX baseband input: `bbtxp`, `bbtxm`.
- Shared RF antenna node: `antenna`.
- Differential RX output: `rxoutp`, `rxoutm`.
- External synthesizer references: `ref_tx`, `ref_rx`, `ref_if`.
- External reset inputs: `div_reset`, `pfd_reset`.

The required named internal probe nodes and every standalone block interface are defined in `/app/submission/interface_contract.json`. Preserve those names and the exact block map in `/app/submission/manifest.json`.

## Required architecture and signal flow

Implement all 38 required flattened DUT files. The transmitter must contain an input VGA, a 10 MHz to 475 MHz mixer, two separate 475 MHz IF filters with an intervening VGA, a 475 MHz to RF mixer, RF filter, RF driver, PA, and duplexer path. The receiver must contain the duplexer/RF filter path, LNA, a 3.415 GHz to 475 MHz mixer, 475 MHz filter and VGA, a 475 MHz to 10 MHz mixer, 10 MHz filter, and output VGA.

Implement three complete internal PLL signal chains with transistor-level VCOs, LO slicers and buffers, CMOS phase-frequency detectors, transistor charge pumps, passive loop filters, and transistor divider logic. Implement the bias reference, gain DAC, detector, and control logic. The full system must use its internal PLL outputs and internal bias/control circuitry. Do not inject an ideal LO, internal bias, internal control waveform, or regulator output from a source.

Use these frequency relationships:

- TX: 10 MHz plus 465 MHz gives 475 MHz; 475 MHz plus about 3.040 GHz gives the 3.515 GHz channel center.
- RX: 3.415 GHz minus about 2.940 GHz gives 475 MHz; 475 MHz minus 465 MHz gives 10 MHz.
- Divide the RF LOs by 64 and the 465 MHz LO by 32.
- The RF bands are 3499 to 3531 MHz for TX and 3399 to 3431 MHz for RX. The channel bandwidth is 3.5 MHz.

## Implementation guidance

A defensible process migration uses double-balanced NMOS Gilbert mixers, resistively loaded differential VGAs, an inductively degenerated cascode LNA, lossy RLC equivalents for the unavailable SAW filters, cross-coupled differential LC VCOs with SKY130 MOS capacitors, static CMOS divider/PFD logic, MOS charge pumps, and transistor LO buffers. A power stage built from parallel 10.5 V extended-drain NFETs is appropriate for the 6.5 V PA domain.

Useful starting guidance from the calibrated migration is:

- 465 MHz tanks can start near 20 nH and 5.26 pF per side.
- 3 GHz tanks can start near 2 nH and 1.0 to 1.15 pF per side.
- The loop filter can start near 20 kohm, 200 pF, and a smaller 20 pF fast capacitor.
- The RF PA can use tuned 20 nH feeds, about 3.6 nH output matching inductance, about 450 fF shunt capacitance, and several parallel extended-drain devices.
- Keep thin-oxide terminals within their rating. Use the 10.5 V extended-drain devices and stacked protection where the 6.5 V PA domain or RF swing requires it.

These values are engineering starting points, not permission to copy a hidden circuit. Bias, stabilize, size, and verify your own implementation.

## Pinned implementation contract

The agent image contains the pinned public SKY130 subset at `/opt/sky130/sky130_tt_1v8.spice`, from `google/skywater-pdk-libs-sky130_fd_pr` commit `f62031a1be9aefe902d6d54cddd6f59b57627436`. Use TT at 27 C, `.option scale=1e-6`, 1.8 V for the core, and 6.5 V only for the PA supply. The private verifier uses NGspice 46.

Each DUT file must be a flattened circuit-only fragment. Legal elements are physical R, L, C and SKY130 physical transistors. X instances are legal only when they resolve directly to one of the allow-listed single-transistor SKY130 wrappers. No candidate-defined `.subckt` is permitted. Do not place `.include`, `.lib`, `.model`, `.subckt`, `.ends`, `.end`, analyses, measurements, or sources in DUT files.

The DUT must not contain V, I, E, F, G, H, B, S, W, A, T, K, or D elements. Do not use Verilog-A/AMS, digital primitives, dependent or behavioral sources, switches, ideal transformers, S-parameters, lookup tables, predefined op-amps, vendor macros, or functional X blocks. Independent V/I sources may appear only in your local testbenches under `/app/submission/work/`.

## Operating conditions and essential calibrated objectives

At the pinned conditions, a successful reconstruction should reproduce these fresh NGspice reference behaviors:

- Loaded simultaneous-system LOs near 3.03150645 GHz, 2.93559022 GHz, and 464.990840 MHz.
- Standalone LNA gain near 10.0471 dB and noise figure near 3.87642 dB at 3.415 GHz.
- Standalone PA output of at least 22.0894 dBm into 50 ohms.
- Complete TX-core output of at least 22.8456 dBm.
- Complete-system antenna output of at least 22.7866 dBm.
- Complete RX conversion gain of at least -38.4746 dB under the disclosed 1 mV peak input convention.
- Simultaneous-system RX differential output of at least 3.23862 mV RMS.
- The calibrated PA is nonlinear: its fresh two-tone reference is -5.49334 dBc IMD3 and 12.0505 dBm worst IMD3 spur. The private numerical target uses these actual values, not the paper's unreproduced claims.

The private verifier also tests block currents, filter centers, startup, divider ratios, control voltages, settling, spectral products, device stress, and full-system operation. Phase noise, OCXO stability, board-level converter power, and P1dB are source-limited review items rather than hidden numerical targets.

## Submission and verification

Work in `/app/submission`. Replace every placeholder and keep all working decks, simulator logs, extracted results, and design notes under `/app/submission/work/`. The final artifact must contain the complete changed `manifest.json`, all 38 populated flattened DUT files, and reproducible local evidence.

The private verifier recursively lints every DUT file, loads only the pinned SKY130 models, runs block and integrated NGspice tests, reports every criterion, and assigns zero for missing, failed, or non-finite measurements. It also rejects missing blocks, illegal hierarchy, internal ideal sources, non-SKY130 devices, unsafe stress, disconnected decorative devices, probe bypasses, hard-coded outputs, fixture manipulation, and partial signal paths.

At MID, full numerical credit extends through 25 percent adverse relative error and falls linearly to zero at 50 percent. Essential measurements have twice the weight of nonessential measurements. Any mandatory eligibility violation makes the final grade zero.
