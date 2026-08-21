# Complete Bluetooth transceiver reconstruction, HARD

## Objective

Synthesize and implement the full sample 3 2.4 GHz Bluetooth transceiver as one flattened SKY130 transistor-level DUT. Both transmit and receive signal paths, the complete frequency-generation path, all internal biases and clocks, calibration, control logic, and the TDD antenna connection are mandatory. Partial or representative paths are ineligible.

## Required functional architecture

The implemented system must contain and connect a shared bias/reference network, RC calibration, reference division, frequency synthesizer, tunable VCO, programmable feedback division, quadrature and harmonic clock generation, TDD switch, receive LNA, I/Q downconversion, fourth-order complex filtering, limiter/RSSI and Gray outputs, IF demodulation, binary FSK generation, Gaussian I/Q filtering, SSB upconversion, and differential power amplification. The external 12 MHz reference must produce the internal approximately 666.667 kHz comparison, approximately 1.6 GHz VCO, approximately 800 MHz quadrature divider signals, and approximately 2.4 GHz quadrature LO. The receiver IF is 2 MHz. The transmit tones differ by about 320 kHz.

Choose and size the transistor topologies, bias points, resonators, filters, compensation, and digital state circuitry yourself. No reference-derived connectivity, sizing, passive values, or tuning guidance is disclosed.

## Fundamental verified objectives

- Complex-filter image rejection: 44.8679499 dB.
- Transmit FSK separation: 318595.678 Hz with autonomous startup.
- PA output power into 50 ohms: 5.24623272 dBm.
- Loaded VCO coarse-code span: 79516269.4 Hz.
- Harmonic LO frequency: 2401450480 Hz.
- Integrated synthesizer VCO frequency: 1599493280 Hz.
- Integrated feedback frequency: 666306.861 Hz.
- Effective integrated divide ratio: 2400.53551.
- Complete-top startup VCO swing: 3.2175 V peak to peak.

The private HARD rubric grades every listed private criterion equally. Full numerical credit requires no more than 5 percent adverse error; credit falls linearly to zero at 25 percent. Architecture and integrity gates remain absolute.

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
