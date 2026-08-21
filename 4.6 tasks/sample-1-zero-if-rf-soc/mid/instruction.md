# Complete SKY130 zero-IF RF-to-SerDes SoC reconstruction, MID

## Objective and architecture

Reconstruct the complete 1.8 V zero-IF RF-to-SerDes system. Implement two receive channels, one four-input feedback receive channel, two eight-bit transmit channels, three RF PLLs, four 5 Gb/s SerDes lanes, and all clock, SPI, memory, calibration, GPIO, and housekeeping support represented by the starter interfaces.

Use this signal flow:

- Each main RX path uses a lumped package port, inductively degenerated cascode LNA, active balun, two-state differential RF attenuator, quadrature passive downmixer, per-I/Q baseband LPF, two-state differential VGA/ADC driver, 3-bit flash conversion, decimation, and calibration control.
- The feedback RX adds a transistor-level four-input differential mux before the same receive path.
- Each TX uses eight-bit interpolation and calibration, transistor-switch R-2R I/Q DACs, differential reconstruction LPFs, a quadrature passive upmixer, pre-power amplifier, RF power amplifier, and differential output match.
- Each RF PLL uses a differential LC VCO, limiting and isolation amplification, quadrature generation, divide by 16 feedback, static-CMOS phase detection, transistor-level charge pump, and loop filter. The PLL must generate the internal RF LO. Do not replace it with testbench LO sources in the complete SoC.
- Implement SPI shifting, four 6T SRAM cells, control sequencing, GPIO, a 3-bit housekeeping ADC, a 4-bit housekeeping DAC, and four transistor-level SerDes lanes.

Reference guidance from the verified SKY130 migration includes 0.15 um logic and RF channel lengths, 0.5 um bias-device lengths, approximately 1.0 V NMOS bias, 0.5 V PMOS bias, 0.9 V common mode, a 2.6 GHz divide-by-16 plan from 162.5 MHz, 50 MHz per-I/Q RX filtering, 100 MHz per-I/Q TX reconstruction filtering, and 100 ohm differential TX loading.

## Essential verified objectives

- LNA gain at 2.6 GHz, higher is acceptable: 20.8745 dB
- approximate LNA noise figure at 2.6 GHz, lower is acceptable: 4.77090645 dB
- two-tone LNA IIP3, higher is acceptable: -4.03276745 dBm
- RF attenuator state range, higher is acceptable: 21.57338 dB
- per-I/Q receive low-pass cutoff: 51826240 Hz
- high-state VGA gain: 15.25195 dB
- per-I/Q transmit reconstruction cutoff: 99834290 Hz
- transmit carrier frequency: 2.60075994e+09 Hz
- transmit output power into 100 ohm differential: -0.69550408 dBm
- one-lane serial rate: 5.00723295e+09 bit/s
- single-carrier EVM proxy, lower is acceptable: 5.23269052 %
- lower adjacent-channel leakage proxy, more negative is acceptable: -29.7591674 dB
- upper adjacent-channel leakage proxy, more negative is acceptable: -29.7938765 dB

The private verifier also checks block interfaces, both modes, converter codes, clock phasing, startup, spectral behavior, power, rail stress, digital activity, and complete-system structure. MID numerical credit is full through 25 percent adverse error and falls linearly to zero at 50 percent. Essential criteria have weight 1.0 and nonessential criteria weight 0.5.


## Submission contract

Work directly in `/app/candidate.cir` and leave a complete reproducible circuit there. The starter contains all 70 required subcircuit signatures. Implement every signature and the complete `zero_if_rf_soc` entry point. Each definition must be internally flat. The complete SoC must contain the physical circuitry for all channels and support functions; it may not call the other candidate definitions.

The final DUT may contain only positive-valued R, L, and C elements plus physical SKY130 transistors. An X instance is legal only when it calls `sky130_fd_pr__nfet_01v8` or `sky130_fd_pr__pfet_01v8`, each of which is one physical transistor. Direct M or Q instances are legal only with an exact model present in the pinned bundle. Do not define model cards or include files in the final DUT.

Rejectable shortcuts include E, F, G, H, B, S, W, A, T, K, arbitrary D devices, controlled or behavioral sources, ideal switches or transformers, digital primitives, Verilog-A or AMS, lookup tables, S-parameters, vendor macros, predefined functional blocks, and candidate-defined hierarchical X calls. Independent sources may be used only in scratch testbenches. They are forbidden in the final DUT.

The public SKY130A TT model bundle is mounted at `/pdk`. It is version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. Scratch testbenches may include `/pdk/sky130_tt.inc`. A normal wrapper instance looks like `XMN d g s b sky130_fd_pr__nfet_01v8 l=0.15 w=1.26 nf=1`. The final candidate must not contain the include statement because the private verifier supplies the trusted model bundle.

Use 1.8 V devices and remain within the 1.8 V supply domain. Do not inject a source into an internal node, pad supply current, add disconnected decorative devices, alias a probe around the real output, or hard-code a waveform or target. The verifier rejects missing blocks, untouched required ports, insufficient physical implementation, unflattened hierarchy, simulation failure, and any forbidden construct before numerical scoring.

You may create any scratch netlists and run NGspice 46 while designing. Save only the circuit core, all required `.subckt` definitions, and a final `.end` in `/app/candidate.cir`.
