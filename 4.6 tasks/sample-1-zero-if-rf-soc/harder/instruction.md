# Complete SKY130 zero-IF RF-to-SerDes SoC reconstruction, HARDER

## Objective

Infer and synthesize the complete flattened transistor-level 1.8 V zero-IF RF-to-SerDes SoC described by the starter interfaces. It must provide two receive channels, one selectable feedback receive channel, two transmit channels, three internally generated quadrature RF synthesizers, four 5 Gb/s serial lanes, and the required bias, control, clock, conversion, memory, calibration, pad, and housekeeping functions.

Operating conditions are SKY130A TT, 27 C, 1.8 V, a 162.5 MHz differential RF reference, approximately 2.6 GHz RF operation, 100 ohm differential transmit loads, 50 ohm receive sources, 50 MHz per-I/Q receive filtering, and 100 MHz per-I/Q transmit reconstruction filtering.

Measured objectives are 2.60075994e+09 Hz carrier frequency, -0.69550408 dBm transmit power, 5.00723295e+09 bit/s per serial lane, 51826240 Hz receive cutoff, 99834290 Hz transmit cutoff, 5.23269052 % EVM, -29.7591674 dB lower adjacent leakage, and -29.7938765 dB upper adjacent leakage. Lower EVM and more negative leakage are acceptable.

No transistor topology, device count, component value, sizing, internal connectivity, or reference-derived tuning hint is provided at this tier. Infer every implementation choice. HARDER grades all private criteria equally. Full credit extends through 1 percent adverse error and falls linearly to zero at 10 percent.


## Submission contract

Work directly in `/app/candidate.cir` and leave a complete reproducible circuit there. The starter contains all 70 required subcircuit signatures. Implement every signature and the complete `zero_if_rf_soc` entry point. Each definition must be internally flat. The complete SoC must contain the physical circuitry for all channels and support functions; it may not call the other candidate definitions.

The final DUT may contain only positive-valued R, L, and C elements plus physical SKY130 transistors. An X instance is legal only when it calls `sky130_fd_pr__nfet_01v8` or `sky130_fd_pr__pfet_01v8`, each of which is one physical transistor. Direct M or Q instances are legal only with an exact model present in the pinned bundle. Do not define model cards or include files in the final DUT.

Rejectable shortcuts include E, F, G, H, B, S, W, A, T, K, arbitrary D devices, controlled or behavioral sources, ideal switches or transformers, digital primitives, Verilog-A or AMS, lookup tables, S-parameters, vendor macros, predefined functional blocks, and candidate-defined hierarchical X calls. Independent sources may be used only in scratch testbenches. They are forbidden in the final DUT.

The public SKY130A TT model bundle is mounted at `/pdk`. It is version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. Scratch testbenches may include `/pdk/sky130_tt.inc`. A normal wrapper instance looks like `XMN d g s b sky130_fd_pr__nfet_01v8 l=0.15 w=1.26 nf=1`. The final candidate must not contain the include statement because the private verifier supplies the trusted model bundle.

Use 1.8 V devices and remain within the 1.8 V supply domain. Do not inject a source into an internal node, pad supply current, add disconnected decorative devices, alias a probe around the real output, or hard-code a waveform or target. The verifier rejects missing blocks, untouched required ports, insufficient physical implementation, unflattened hierarchy, simulation failure, and any forbidden construct before numerical scoring.

You may create any scratch netlists and run NGspice 46 while designing. Save only the circuit core, all required `.subckt` definitions, and a final `.end` in `/app/candidate.cir`.
