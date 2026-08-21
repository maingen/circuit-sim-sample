# SKY130 2.4 GHz RF sampling receiver reconstruction, MID

Build a complete transistor-level 2.4 GHz RF sampling receiver in NGspice using the pinned open-source SKY130 PDK. Submit every constituent circuit and the full end-to-end receiver as executable flattened SPICE artifacts. A paper summary, diagram, behavioral model, representative path, or partial channel is not a submission.

## External system interface and conditions

The complete receiver subcircuit is:

```spice
.subckt FULL_RECEIVER ANT LOP LON RESET VDD VSS IOUTP IOUTN QOUTP QOUTN IBIT IBITB QBIT QBITB ADCCLK
```

Use 1.8 V at 27 C. The primary RF input is 2.413 GHz. Drive LOP and LON as complementary 1.072 GHz external differential clock inputs centered at 0.9 V with 0.25 V peak amplitude. RESET is an external startup input. The architecture produces 24 nonoverlapping phase states, decimates by 12, and provides an approximately 89.3 MS/s ADC cadence. The integrated antenna test uses a 50 ohm Thevenin source with 8.934 mV peak, equivalent to about -37 dBm available power. IOUT and QOUT drive four 50 ohm loads referred to 0.55 V.

The timing architecture must also be externally frequency-driven and capable of retiming at the paper's approximately 567.5 MS/s lower sampling mode without replacing any internal block or injecting phase nodes. The frozen reconstruction does not provide a defensible lower-mode numerical performance target, so this is an architecture and completeness check rather than a fabricated metric.

## Required architecture and guidance

Implement and connect all of these functions:

1. A 2.45 GHz RF preselector and tuned LNA.
2. A 24/0.18 um NMOS sampling switch, 1 pF sampling capacitor, and source follower using 50/0.18 um and 200/0.18 um devices.
3. Four time-interleaved 23-tap switched-capacitor FIR paths for I1, I2, Q1, and Q2. The nonzero capacitor sequence is 11, 88, 187, 187, 88, 11, 44, 143, 198, 143, and 44 fF, with 5/0.18 um switching devices and 72 fF differential holds.
4. A differential clock slicer, transistor-level logic, a static 24-state one-hot phase generator, double transmission-gate timing support, and divide-by-12 ADC transfer timing. Do not inject phase signals from the testbench.
5. Four 50 ohm output buffers and transistor-level internal bias generation.
6. Two transistor-level one-bit ADC slices with complementary outputs.

The intended signal flow is antenna, preselector, tuned LNA, sample-and-hold mixer, four FIR paths, I/Q selection, output buffers, and I/Q ADCs. All internal biases, phase clocks, transfer clocks, logic, and conversion decisions must arise from physical devices inside the integrated DUT.

## Verified behavioral objectives

The private NGspice 46 reference replay gives these essential objectives:

- RF front-end peak: 2.450 GHz, 32.3485 dB gain, 77.0 MHz contiguous 3 dB bandwidth.
- Clock path: 1.07194 GHz; ADC cadence: 89.1917 MHz.
- S/H follower gain: -1.05141 dB.
- Lower and upper FIR alias-center rejection: 45.5490 dB and 38.4176 dB.
- RFSD I and Q differential peak amplitudes at the disclosed direct-input condition: 0.162188 V and 0.159949 V, with 90.0176 degree phase separation.
- Full receiver I and Q differential peak amplitudes: 0.0235834 V and 0.0235187 V, with 90.5266 degree separation.
- Full receiver power: 98.8245 mW. Each ADC output must traverse below 0.2 V and above 1.6 V.

These are actual SKY130 reconstruction results, not substituted paper claims. Other block-level and adversarial checks remain private.

## Physical-device and submission contract

Use `/app/public/interface_contract.json` as the exact file, subcircuit, and port contract. Write the 12 files into `/app/submission`. Every file must contain exactly one top-level subcircuit and must be flattened. An X instance is legal only when it directly calls an allow-listed SKY130 single-transistor wrapper. Candidate-defined hierarchy is forbidden even when the same logic is expanded elsewhere.

The DUT may contain physical R, L, C, MOSFET, and BJT devices only. Do not use E, F, G, H, B, S, W, A, T, K, arbitrary diode, digital primitive, behavioral source, controlled source, ideal switch, ideal transformer, S-parameter data, Verilog-A, lookup table, vendor macro, or functional subcircuit. Independent sources belong only in your disclosed local testbenches and must not appear in any submitted DUT file. Final files must not contain includes, model cards, analysis commands, measurements, or hard-coded outputs. The verifier attaches the trusted `tt` SKY130 library and private fixtures.

The public PDK is at `/opt/sky130`. You may create private working testbenches under `/app/work`, but keep final DUT files circuit-only. Preserve reproducible working files and simulator logs. Before finishing, run `/app/check_submission.py /app/submission` and ensure it passes.

MID scoring gives full criterion credit through 25% adverse error and zero credit at 50%, with linear interpolation between those points. Essential and nonessential criteria have different private weights. Mandatory integrity or completeness gate failures make the final grade zero.
