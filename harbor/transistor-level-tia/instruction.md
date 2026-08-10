TASK: DESIGN A COMPLETE TRANSISTOR-LEVEL DIFFERENTIAL TIA

Create one self-contained LTspice-compatible .cir file for the complete differential transimpedance amplifier described below. Design every device value, transistor size, bias current, pole, zero, and compensation network yourself. The target is the behavior and architecture in this prompt, not a transcription of an existing netlist.

The private Harbor verifier runs Ngspice 46. Keep the submitted netlist compatible with both LTspice and Ngspice 46.

DELIVERABLE

Save the finished circuit as `/app/candidate.cir`. Return one circuit-only .cir file. The file must contain the complete signal path, gain-control path, peak detector, automatic gain-control path, bias circuits, model cards, and named probe nodes. Do not include .op, .ac, .tran, .noise, .four, .meas, or other analysis commands.

Use only resistors, capacitors, inductors, NMOS transistors, PMOS transistors, NPN BJTs, PNP BJTs, and independent sources connected to external supply or control pins. Do not use built-in or macromodel op-amps, controlled sources, behavioral sources, Laplace blocks, lookup tables, digital devices, vendor compound blocks, or black-box subcircuits. If an amplifier, regulator, selector, detector, or servo is required, build it from transistors and passive elements. Keep the final netlist flattened, with no X-device instances.

REQUIRED EXTERNAL INTERFACE AND PROBE NODES

Use these external and system node names so an independent grader can attach testbenches:

- The supply and controls must be named vcc, mc, mgc, and oa.
- The differential current inputs must be named inp and inn.
- The final differential outputs must be named finalp and finaln.
- Expose the selected gain-control node as gc and the AGC output as agc.
- Expose VGA control nodes as vc1, vc1b, vc2, and vc2b.
- Expose the input-TIA outputs as tia_p and tia_n.
- Expose the first interface outputs as v1p and v1n.
- Expose the first VGA outputs as vga1p and vga1n.
- Expose the second interface outputs as v2p and v2n.
- Expose the second VGA outputs as vga2p and vga2n.
- Expose the output-buffer inputs as bufinp and bufinn, its loaded outputs as outp and outn, the detector tap inputs as pkdinp and pkdinn, and the detector outputs as detp, detn, and pkd.
- Name the positive and negative DC-cancellation sink transistors M_CANCEL_P and M_CANCEL_N so the grader can measure their drain currents.

CIRCUIT ARCHITECTURE

1. Build two matched input TIA halves. Each half must use a BJT common-emitter transimpedance stage with local shunt feedback and a transistor follower in the feedback path. Regulate the local TIA rail with a transistor-level loop. Add a slow DC-overload cancellation path that senses input bias error and uses a MOS current sink to remove large photodiode DC current without suppressing the high-frequency signal. Keep the signal path fully differential.

2. AC-couple each TIA output into a transistor emitter-follower interface. The interface must establish the next stage's common mode, present a low driving impedance, and preserve differential bandwidth. Use matched positive and negative halves.

3. Build VGA1 and VGA2 as BJT variable-gain cells. Each VGA must contain a differential input pair with emitter degeneration, a transistor steering or cascode quad controlled by complementary control voltages, resistive collector loading, transistor emitter followers at the outputs, and transistor current sinks. VGA2 may use a passive emitter-degeneration compensation element to shape its high-frequency response.

4. Build a transistor-level gain-control generator that converts gc into the complementary control pairs vc1 and vc1b, and vc2 and vc2b. The two control pairs may have different slopes so the two VGA stages distribute gain change while maintaining bandwidth.

5. Build a transistor-level mode selector. When mc is 0 V, it must route the external mgc voltage to gc. The alternate state must route agc to gc. Use CMOS switches or an equivalent transistor-only analog selection circuit.

6. AC-couple and buffer the VGA stages as needed. Each interstage network must use only passive devices, BJTs, and MOSFET current sinks. Preserve balanced loading and expose the required probe nodes.

7. Build the output buffer as a degenerated BJT differential pair with resistive collector loads, transistor current sinks, and a 100 ohm differential output load. Add a passive output pole between outp/outn and finalp/finaln. The output must support the swing and distortion corners below.

8. Build an eight-BJT Gilbert-cell peak detector. Use input followers, a lower differential pair with emitter degeneration, a four-transistor switching core, resistive collector loads, and transistor current sinks. Couple it to finalp/finaln through a high-impedance differential tap so it does not materially load the signal output.

9. Build the AGC path from the differential detector output. Include passive detector filtering, transistor followers, a differential error amplifier, and a second control amplifier that drives agc. Any operational-amplifier function must be implemented as a transistor-level CMOS amplifier with its own input pair, active load, gain stage, bias network, and compensation. Do not use an op-amp symbol or macromodel.

10. Generate every internal bias with transistor mirrors, diode-connected transistors, resistor dividers, and transistor feedback loops. Preserve symmetry between positive and negative signal paths.

NOMINAL OPERATING CORNER

Use a 3.3 V supply. Set mc to 0 V for manual gain control, mgc to 1.40 V, and oa to 1.20 V. With zero DC input current, target the following operating point:

- Each input self-bias voltage is 0.7594 V and must remain below 0.9 V.
- The differential input-bias mismatch is nominally zero.
- The output common-mode voltage is 2.706 V.
- The final differential DC offset is nominally zero.
- The selected gain-control voltage is 1.400 V.
- The magnitudes of vc1 minus vc1b and vc2 minus vc2b are 8.006 mV and 33.19 mV, respectively.
- The nominal supply current is 95.43 mA, corresponding to 314.9 mW from 3.3 V.

GLOBAL TRANSIMPEDANCE AND BANDWIDTH TARGETS

The differential transimpedance is the differential output voltage divided by the equal-magnitude, opposite-polarity small-signal input current. Preserve approximately the same 3 dB bandwidth as gain changes.

| MGC voltage | Transimpedance at 10 MHz | Transimpedance at 33 GHz | 3 dB bandwidth |
| 1.25 V | 70.48 dB ohm | 67.43 dB ohm | 32.73 GHz |
| 1.30 V | 71.82 dB ohm | 68.78 dB ohm | 32.77 GHz |
| 1.35 V | 73.00 dB ohm | 69.96 dB ohm | 32.80 GHz |
| 1.40 V | 74.01 dB ohm | 70.98 dB ohm | 32.83 GHz |

At maximum gain, the design target is approximately 74 dB ohm low-frequency transimpedance and 33 GHz bandwidth. The 33 GHz response should be approximately 3 dB below the 10 MHz response. Across the four MGC settings, the 3 dB bandwidth spread must not exceed 2 GHz.

At maximum gain and 10 MHz, target local differential voltage gains of 7.5 dB for VGA1, 10.5 dB for VGA2, and 3.5 dB for the output buffer. With the supplied generic transistor cards, target a local signal-path group delay of 13.01 ps around 10 GHz. The paper's reported 43.30 ps average delay remains a comparison value, not a target for this pre-layout model.

DC-OVERLOAD CORNER

At the nominal supply and control settings, apply 5.00 mA DC current to inp and 3.75 mA DC current to inn. Target these settled values:

- inp is 0.7800 V and inn is 0.7765 V. Both must remain below 0.9 V.
- The input mismatch is 3.545 mV.
- The final differential DC offset is nominally zero.
- The positive and negative cancellation devices sink 4.616 mA and 3.654 mA, respectively.

OUTPUT-BUFFER CORNERS

Use a 3.3 V supply, a 1.8 V input common mode, a 100 ohm differential load, and a 1 GHz differential sine wave. Meet the following differential behavior:

| Input peak-to-peak | Output peak-to-peak | Differential gain | Maximum reference THD |
| 400 mV | 592.5 mV | 3.413 dB | 0.3216 percent |
| 600 mV | 869.6 mV | 3.223 dB | 0.9286 percent |
| 625 mV | 902.0 mV | 3.186 dB | 1.052 percent |
| 800 mV | 1.098 V | 2.750 dB | 2.590 percent |

The principal swing requirement is approximately 900 mV peak-to-peak differential output for a 625 mV peak-to-peak input with low distortion.

PEAK-DETECTOR AND AGC CORNERS

Drive the detector with a 33.5 GHz differential sine wave. Its average differential output must rise monotonically with amplitude and target these values:

| Detector input peak-to-peak | Average differential detector output |
| 50 mV | 14.97 mV |
| 200 mV | 92.03 mV |
| 400 mV | 158.9 mV |
| 550 mV | 179.4 mV |

Across detector differences of 20 mV and 50 mV, target an AGC amplifier gain of 14 V/V.

PAM4 FUNCTIONAL CORNER

At 25 Gbaud, drive the two input branches with opposite four-level currents so the differential current levels are minus 200 microamps, minus 66.67 microamps, plus 66.67 microamps, and plus 200 microamps. With mc at 0 V and mgc at 1.40 V, target approximately 0.8204 V peak-to-peak differential output. After settling, a deterministic noiseless eye folded over a 40 ps unit interval must show four separated rails and three open eyes. The minimum 10th-to-90th-percentile vertical opening should be at least 188.9 mV.

MODEL CARDS

Use these model cards exactly unless LTspice requires a purely syntactic correction. These generic cards define the grading environment, so do not claim silicon or process accuracy from them.

.model NMOS NMOS(VTO=.55 KP=220u LAMBDA=.02)
.model PMOS PMOS(VTO=-.55 KP=100u LAMBDA=.02)
.model QN NPN(IS=1e-16 BF=200 VAF=100 IKF=50m RB=5 RC=1 RE=.2 CJE=2f CJC=1f TF=.45p TR=5p)
.model QP PNP(IS=1e-16 BF=100 VAF=60 IKF=20m RB=8 RC=1 RE=.3 CJE=3f CJC=1.5f TF=.7p TR=8p)
.model QBUF NPN(IS=1e-16 BF=200 VAF=100 IKF=100m RB=3 RC=.5 RE=.15 CJE=3f CJC=1.5f TF=.45p TR=5p)

LIMITS OF THE AVAILABLE MODELS

Do not invent process, voltage, temperature, mismatch, Monte Carlo, or extracted-parasitic corners because none are supplied. The paper-level goals of 12.2 pA per square-root hertz input-referred noise, at least 30 dB worst-case CMRR at 25 GHz, 4.2 mV peak-to-peak BER sensitivity at 32 Gb/s, and measured 25 Gbaud PAM4 statistics cannot be substantiated with these generic matched models. Keep them as documented future verification goals and do not claim that nominal noiseless simulation proves them.
