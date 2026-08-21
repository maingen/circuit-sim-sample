# Complete SKY130 zero-IF RF-to-SerDes SoC reconstruction, HARD

## Objective

Synthesize the complete 1.8 V zero-IF RF-to-SerDes SoC represented by the 70 starter interfaces. The required system contains two RX paths, one four-input feedback RX path, two eight-bit TX paths, three internally generated quadrature RF local oscillators with feedback control, four 5 Gb/s SerDes lanes, and transistor-level bias, clock, SPI, memory, calibration, GPIO, and housekeeping support.

The RX function must provide RF input conditioning, gain control, quadrature zero-IF conversion, approximately 50 MHz per-I/Q baseband filtering, variable gain, conversion, and digital decimation. The TX function must accept eight-bit I/Q data, interpolate and calibrate it, convert it to analog, reconstruct approximately 100 MHz per-I/Q baseband, upconvert it near 2.6 GHz, and drive a 100 ohm differential load. Each RF synthesizer must derive its internal LO from a 162.5 MHz differential reference with divide by 16 feedback. Do not use an external LO inside the complete SoC.

Fundamental verified objectives are a 2.60075994e+09 Hz transmit carrier, -0.69550408 dBm output into 100 ohm differential, 5.00723295e+09 bit/s per SerDes lane, 51826240 Hz RX cutoff, and 99834290 Hz TX cutoff. The spectral reference migration reproduces 5.23269052 % EVM and -29.7591674 dB lower and -29.7938765 dB upper adjacent leakage. Lower EVM and more negative leakage are acceptable.

Choose the transistor topology, sizing, bias distribution, stabilization, passive values, digital implementation, and internal connectivity. No reference netlist or hidden fixture is available. HARD grades every listed private criterion equally. Full credit extends through 5 percent adverse error and falls linearly to zero at 25 percent.


## Submission contract

Work directly in `/app/candidate.cir` and leave a complete reproducible circuit there. The starter contains all 70 required subcircuit signatures. Implement every signature and the complete `zero_if_rf_soc` entry point. Each definition must be internally flat. The complete SoC must contain the physical circuitry for all channels and support functions; it may not call the other candidate definitions.

The final DUT may contain only positive-valued R, L, and C elements plus physical SKY130 transistors. An X instance is legal only when it calls `sky130_fd_pr__nfet_01v8` or `sky130_fd_pr__pfet_01v8`, each of which is one physical transistor. Direct M or Q instances are legal only with an exact model present in the pinned bundle. Do not define model cards or include files in the final DUT.

Rejectable shortcuts include E, F, G, H, B, S, W, A, T, K, arbitrary D devices, controlled or behavioral sources, ideal switches or transformers, digital primitives, Verilog-A or AMS, lookup tables, S-parameters, vendor macros, predefined functional blocks, and candidate-defined hierarchical X calls. Independent sources may be used only in scratch testbenches. They are forbidden in the final DUT.

The public SKY130A TT model bundle is mounted at `/pdk`. It is version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. Scratch testbenches may include `/pdk/sky130_tt.inc`. A normal wrapper instance looks like `XMN d g s b sky130_fd_pr__nfet_01v8 l=0.15 w=1.26 nf=1`. The final candidate must not contain the include statement because the private verifier supplies the trusted model bundle.

Use 1.8 V devices and remain within the 1.8 V supply domain. Do not inject a source into an internal node, pad supply current, add disconnected decorative devices, alias a probe around the real output, or hard-code a waveform or target. The verifier rejects missing blocks, untouched required ports, insufficient physical implementation, unflattened hierarchy, simulation failure, and any forbidden construct before numerical scoring.

You may create any scratch netlists and run NGspice 46 while designing. Save only the circuit core, all required `.subckt` definitions, and a final `.end` in `/app/candidate.cir`.
