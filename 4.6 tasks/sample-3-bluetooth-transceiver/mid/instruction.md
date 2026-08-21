# Complete Bluetooth transceiver reconstruction, MID

## Objective

Implement the complete sample 3 2.4 GHz Bluetooth transceiver as a physical SKY130 transistor-level system, including every constituent circuit and both transmit and receive modes. A block diagram, behavioral approximation, partial channel, externally clocked internal function, or prose response is not a submission.

## Disclosed architecture and signal flow

Use the recreated paper architecture as follows.

- A transistor/BJT bandgap and beta-derived bias network produces shared analog and RF biases. A physical RC calibration oscillator, counter, and sampler produces the six calibration bits.
- A 12 MHz external reference is divided by 18. The synthesizer contains a transistor PFD, calibrated MOS charge pump, passive switched loop filter, complementary 1.6 GHz LC VCO with continuous MOS varactors and a six-bit switched capacitor bank, a transistor RF limiter, a CML divide-by-16 front end, and a transistor divide-by-150 fallback path. The nominal integrated ratio is 2400. Do not substitute an ideal clock or LO.
- The clock generator converts the differential 1.6 GHz VCO into roughly 800 MHz quadrature divider outputs and roughly 2.4 GHz quadrature LO outputs through a transistor-level divide-by-two and harmonic-generation path with physical resonant loads and buffers.
- In receive mode, the antenna path is a transistor TDD switch followed by a differential inductively matched LNA, I/Q transistor mixers, two coupled complex-filter sections, a limiting/RSSI chain with transistor rectification and Gray outputs, and an IF discriminator with physical differentiation, multiplication, low-pass filtering, peak/valley tracking, and slicing.
- In transmit mode, a self-starting current-starved quadrature ring generates binary FSK, physical fourth-order Gaussian I/Q filtering shapes it, transistor SSB mixers translate it with the internal quadrature LO, and a cascoded class-AB differential PA drives 50 ohms through the transistor TDD switch.

The frequency plan is 2.4 to 2.48 GHz RF, 1.6 GHz VCO, roughly 800 MHz divider quadrature, 2 MHz receiver IF, and approximately 666.667 kHz comparison frequency. The two transmit FSK states are separated by about 320 kHz. Use 5 V tolerant SKY130 MOS wrappers throughout the 2.7 V domain and the pinned PNP wrapper where a bipolar reference is needed. Keep every resonator, matching network, loop filter, Gaussian pole, complex-filter pole, and stabilization component physical.

## Essential verified numerical objectives

These are successful NGspice 46 replay values from the completed SKY130 reconstruction, not the paper's claimed silicon measurements.

- LNA gain at 2.4 GHz: 10.3672 dB.
- Complex-filter image rejection: 44.8679499 dB.
- Transmit FSK separation: 318595.678 Hz, with autonomous startup.
- PA output power into 50 ohms: 5.24623272 dBm.
- Loaded VCO coarse-code span: 79516269.4 Hz.
- Harmonic LO frequency: 2401450480 Hz.
- Integrated synthesizer VCO frequency: 1599493280 Hz.
- Integrated feedback frequency: 666306.861 Hz.
- Effective integrated divide ratio: 2400.53551.
- Complete-top startup VCO swing: 3.2175 V peak to peak.

The private MID rubric also checks nonessential block behavior, electrical bias, spectral response, supply current, startup, multi-mode behavior, stability, device stress, connectivity, and integrated perturbation response. MID gives full numerical credit through 25 percent adverse error and zero at 50 percent. Essential criteria have weight 1.0 and nonessential criteria have weight 0.5.

## Submission and isolation contract

Work only in `/app`. Produce both `/app/candidate.cir` and `/app/architecture.json`. Keep every intermediate netlist, simulation deck, script, log, and numerical result you create under `/app/working` so the full development trail is preserved. The circuit file must be a UTF-8, top-level, fully flattened NGspice DUT ending in `.end`. Do not define any `.subckt` or `.model`. The only permitted include, which may be omitted because the verifier supplies it, is:

```spice
.include "/opt/sky130-pdk/models/sky130_27v_tt.spice"
```

The pinned public model tree is Open PDKs SKY130A revision `c6d73a35f524070e85faff4a6a9eef49553ebc2b` at TT with mismatch disabled. Use only physical R, L, C, and these single-transistor SKY130 wrapper instances:

- `sky130_fd_pr__nfet_g5v0d10v5`
- `sky130_fd_pr__pfet_g5v0d10v5`
- `sky130_fd_pr__pnp_05v5_W0p68L0p68`

Every X instance must resolve directly to one of those wrappers. Candidate-defined hierarchy is forbidden. Do not use V, I, E, F, G, H, B, S, W, A, T, K, D, M, or Q instance lines in the DUT. Do not use behavioral or controlled sources, ideal switches, digital primitives, Verilog-A or AMS, lookup tables, S-parameters, vendor macros, local model cards, or analysis commands. Independent sources belong only to the private testbenches. Internal bias, reference, oscillation, LO, clock, control, conversion, gain, filtering, and digital support must be transistor-level circuitry.

The integrated system uses these external nodes: `antp antn txdata txen rxdata rssi g2 g1 g0 ref12 vdd 0`. The verifier supplies 2.7 V, a 12 MHz reference, data and mode stimuli, a differential 50 ohm antenna load, and genuine external RF input stimulus. It never drives an internal node of the integrated DUT.

Preserve these observation-node names in the flat circuit so block-level and integrated measurements refer to the same implemented devices:

`bias_vref bias_vbn bias_vbp bias_vbana bias_vbrf bias_vbpa bias_vcas rcclk cal0 cal1 cal2 cal3 cal4 cal5 ref667 vcop vcon vctrl vco_limited_clk divout up down cp loip loin loqp loqn divip divin divqp divqn prescaler_clk mod16_ctl prescaler_div15 prescaler_div16 prescaler_rf16 program_frame159 program_frame150 swallow_done divider_frame modsel sdone chan_s0 chan_s1 chan_s2 chan_s3 chan_s4 chan_s5 chan_s6 rxp rxn lna_outp lna_outn rx_mix_ip rx_mix_in rx_mix_qp rx_mix_qn bpf_ip bpf_in bpf_qp bpf_qn limitp limitn limitqp limitqn demod_discr fsk_ip fsk_in fsk_qp fsk_qn gauss_ip gauss_in gauss_qp gauss_qn tx_mixp tx_mixn txp txn`.

The architecture manifest has schema version 1, a unique `submission_id`, `operating_modes` equal to `["transmit", "receive"]`, and a `top.external_ports` list containing exactly the external nodes above. Its `blocks` object must contain these accounting identifiers: `bias_reference`, `rc_calibration`, `reference_divider`, `pfd_charge_pump_loop_filter`, `vco`, `prescaler_frontend`, `program_counter_159`, `program_counter_150`, `swallow_counter`, `programmable_divider_control`, `synthesizer_interconnect`, `clock_generator`, `tdd_switch`, `lna`, `rx_iq_mixer`, `complex_bpf`, `limiter_rssi`, `if_demodulator`, `tx_fsk_modulator`, `gaussian_filters`, `tx_ssb_mixer`, `power_amplifier`, and `top_interconnect`. Each block maps `elements` to the exact candidate element names it owns and `interface` to role-to-node mappings. Every circuit element must belong to exactly one block. The private verifier uses this ownership only to extract block-level views from the same flat DUT; duplicate standalone copies and disconnected decorative devices are not accepted.

A parse failure, required simulation failure, forbidden primitive, unapproved model, user hierarchy, internal source, missing block or mode, disconnected decoration, hard-coded output, dummy target branch, supply-current padding, probe bypass, unsafe stress, private-file access, or grader manipulation sets the final grade to zero. The verifier perturbs supply, load, input, reference clock, data, and operating mode to expose fixture-specific behavior. Missing and non-finite measurements score zero. All saved claims must be reproducible in NGspice 46.

The agent container has no access to the reference circuit, private fixtures, target ledger, grading code, other rollouts, or credentials. Web search is disabled. Use the local public PDK and local simulation tools only.
