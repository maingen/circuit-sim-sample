# SKY130 2.4 GHz RF sampling receiver reconstruction, HARDER

Create a complete physical transistor-level quadrature RF sampling receiver in NGspice using the pinned open-source SKY130 PDK. The submission must include every independently testable receiver function and a separately flattened full system. You must infer all transistor topologies, sizes, passive values, internal connectivity, bias circuits, clock/control circuits, stabilization, and tuning.

## Interface and operating objectives

The complete receiver interface is:

```spice
.subckt FULL_RECEIVER ANT LOP LON RESET VDD VSS IOUTP IOUTN QOUTP QOUTN IBIT IBITB QBIT QBITB ADCCLK
```

Use 1.8 V, 27 C, a 2.413 GHz RF input, and complementary 1.072 GHz LOP/LON inputs centered at 0.9 V with 0.25 V peak amplitude. RESET is the external startup input. The system must perform quadrature RF sampling, 24-state timing, divide-by-12 rate conversion, baseband filtering and output drive, and I/Q one-bit conversion. The antenna interface is 50 ohms; four analog outputs drive 50 ohm loads referred to 0.55 V.

The physical timing system must also retime from lower external LOP/LON operation near 567.5 MS/s without replacing circuitry or exposing any internal phase input. No lower-mode numerical target is supplied because the frozen reference does not reproduce one; completeness is reviewed structurally.

At a 50 ohm Thevenin antenna input of 8.934 mV peak, the actual SKY130 reference produces about 23.58 mV and 23.52 mV differential I and Q peak amplitude, 90.5266 degrees quadrature separation, valid complementary ADC rail traversal below 0.2 V and above 1.6 V, and 98.8245 mW total power. Its RF front end peaks at 2.450 GHz with 32.3485 dB gain and 77.0 MHz contiguous 3 dB bandwidth. Its derived ADC cadence is 89.1917 MHz.

No implementation topology, component count, size, internal connectivity, or tuning guidance is provided at this tier. The private verifier also grades undisclosed block-level, spectral, timing, balance, startup, loading, and supply behavior reproduced by the same reference.

## Legal implementation

Follow `/app/public/interface_contract.json` exactly and write all 12 circuit files to `/app/submission`. Each file contains one top-level subcircuit and is flat. The integrated receiver must duplicate and connect its physical devices directly. Candidate-defined X hierarchy is ineligible. An X line is legal only when it resolves directly to an allow-listed SKY130 wrapper representing one transistor.

Only physical R, L, C and SKY130 transistor devices are legal in the DUT. No internal independent sources, externally injected internal nodes, dependent or behavioral sources, ideal switches, abstract logic, functional blocks, model cards, candidate libraries, Verilog-A, tables, S-parameters, analysis directives, hard-coded outputs, dummy current branches, or decorative disconnected devices are permitted. The verifier supplies only true external power, RF, clock, reset, reference, and load fixtures.

The public PDK is available at `/opt/sky130`. Preserve the complete working record and run `/app/check_submission.py /app/submission` before finalizing. HARDER scoring gives full criterion credit through 1% adverse error and zero at 10%, linearly interpolated between. Every numerical criterion is equally weighted. Any mandatory integrity, safety, flattening, architecture, or completeness violation makes the audited final grade zero.
