# SKY130 2.4 GHz RF sampling receiver reconstruction, HARD

Build a complete flattened transistor-level NGspice implementation of a quadrature 2.4 GHz RF sampling receiver using the pinned open-source SKY130 PDK. Submit executable circuits for every required block and a separately flattened end-to-end receiver. Partial channels, behavioral approximations, idealized functions, and prose are ineligible.

## Operating contract

The complete receiver interface is:

```spice
.subckt FULL_RECEIVER ANT LOP LON RESET VDD VSS IOUTP IOUTN QOUTP QOUTN IBIT IBITB QBIT QBITB ADCCLK
```

Operate at 1.8 V and 27 C. The primary RF input is 2.413 GHz. LOP and LON are complementary 1.072 GHz external differential inputs centered at 0.9 V with 0.25 V peak amplitude. RESET is the only external startup control. The frequency plan uses a 24-phase state sequence, decimation by 12, and an approximately 89.3 MS/s ADC cadence. The antenna fixture is a 50 ohm Thevenin source. Differential I and Q analog outputs drive four 50 ohm loads referred to 0.55 V.

The same physical timing path must accept the paper's approximately 567.5 MS/s lower external sampling mode without a block replacement or internal phase injection. This mode receives an architecture check because the frozen reference has no reproducible lower-mode numerical ledger.

## Required architecture

Your implementation must contain a physical RF preselector, tuned transistor LNA, sample-and-hold RF mixer, four time-interleaved 23-tap switched-capacitor I/Q FIR paths, I/Q selection, 50 ohm output drivers, differential clock slicing, transistor-level phase and transfer-clock generation, internal transistor bias generation, and two transistor-level ADC decision paths. Both I and Q channels and all 24 timing states must be genuine connected signal paths. Synthesize, bias, size, stabilize, and tune the circuits yourself.

Fundamental verified objectives are:

- RF front-end center 2.450 GHz, gain 32.3485 dB, and 77.0 MHz bandwidth.
- Sampling clock 1.07194 GHz and ADC cadence 89.1917 MHz.
- Integrated I/Q phase separation 90.5266 degrees and differential peak amplitudes near 23.6 mV per channel at about -37 dBm available antenna power.
- Valid complementary ADC rail traversal below 0.2 V and above 1.6 V.
- Total integrated power 98.8245 mW.

The private verifier includes additional actual-reference block, spectral, balance, startup, load, supply, and connectivity criteria.

## Physical-device and artifact rules

`/app/public/interface_contract.json` defines the 12 required files, top-level subcircuit names, and ports. Write all files to `/app/submission`. Each file must be independently flattened. The complete receiver must contain its physical circuitry directly, not X calls to your block files. X instances are legal only when they resolve directly to an allow-listed SKY130 wrapper for one physical transistor.

Final DUTs may contain only physical R, L, C and SKY130 transistors. No internal independent source, candidate include, candidate model card, user hierarchy, dependent or behavioral source, ideal switch, functional macro, abstract digital primitive, S-parameter block, Verilog-A, lookup table, or analysis directive is allowed. External supplies, clocks, reset, RF input, and loads appear only in testbenches. The public PDK is at `/opt/sky130`; the private verifier attaches the same pinned `tt` library.

Save working notes, self-test decks, logs, and the final artifacts. Run `/app/check_submission.py /app/submission` before finishing. HARD scoring gives full credit through 5% adverse error and zero at 25%, with linear interpolation in between. Every numerical criterion has equal weight unless a mandatory gate zeros the candidate.
