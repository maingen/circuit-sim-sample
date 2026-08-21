from __future__ import annotations


FIXTURES = {
    "bias_dc": {
        "blocks": ["bias_reference"],
        "measurements": {
            "bias_vref_nom_v": "vref_nom",
        },
        "body": r"""
.option temp=27 reltol=1e-5 abstol=1e-12 vntol=1e-8 gmin=1e-12
VDD_TB vdd 0 2.7
RLOAD_TB bias_vref 0 1meg
.dc VDD_TB 2.69 2.70 0.005
.meas dc vref_nom FIND v(bias_vref) AT=2.695
.end
""",
    },
    "bias_temp": {
        "blocks": ["bias_reference"],
        "measurements": {
            "bias_vref_min_v": "vref_min",
            "bias_vref_max_v": "vref_max",
        },
        "body": r"""
.option temp=27 reltol=1e-5 abstol=1e-12 vntol=1e-8 gmin=1e-12
VDD_TB vdd 0 2.7
RLOAD_TB bias_vref 0 1meg
.dc TEMP -25 100 5
.meas dc vref_min MIN v(bias_vref)
.meas dc vref_max MAX v(bias_vref)
.end
""",
    },
    "lna": {
        "blocks": ["lna"],
        "measurements": {
            "lna_gain_2p4g_db": "gain_db",
            "lna_output_cm_v": "output_cm",
            "lna_supply_current_a": "idd",
        },
        "body": r"""
.option temp=27 reltol=1e-4 abstol=1e-12 vntol=1e-7
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbrf 0 1.50
VRFP_TB srcp 0 dc 0 ac 0.5 0
VRFN_TB srcn 0 dc 0 ac 0.5 180
RSP_TB srcp rxp 50
RSN_TB srcn rxn 50
RLP_TB lna_outp 0 2k
RLN_TB lna_outn 0 2k
.dc VDD_TB 2.69 2.70 0.005
.meas dc idd FIND i(VDD_TB) AT=2.695
.meas dc output_cm FIND v(lna_outp) AT=2.695
.ac dec 100 100meg 10gig
.meas ac gain_db FIND db(v(lna_outp)-v(lna_outn)) AT=2.4g
.end
""",
    },
    "rx_mixer": {
        "blocks": ["rx_iq_mixer"],
        "measurements": {
            "rx_mixer_if_pp_v": "if_pp",
            "rx_mixer_supply_current_a": "idd_avg",
        },
        "body": r"""
.option temp=27 reltol=2e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.12
VRFP_TB lna_outp 0 sin(1.35 5m 2.402g)
VRFN_TB lna_outn 0 sin(1.35 -5m 2.402g)
VLOIP_TB loip 0 pulse(0.1 2.6 0 30p 30p 178.3p 416.667p)
VLOIN_TB loin 0 pulse(2.6 0.1 0 30p 30p 178.3p 416.667p)
VLOQP_TB loqp 0 pulse(0.1 2.6 104.167p 30p 30p 178.3p 416.667p)
VLOQN_TB loqn 0 pulse(2.6 0.1 104.167p 30p 30p 178.3p 416.667p)
CIP_TB rx_mix_ip 0 5p
CIN_TB rx_mix_in 0 5p
.tran 10p 1u 400n
.meas tran if_pp PP v(rx_mix_ip,rx_mix_in) FROM=500n TO=1u
.meas tran idd_avg AVG i(VDD_TB) FROM=500n TO=1u
.end
""",
    },
    "complex_bpf_desired": {
        "blocks": ["complex_bpf"],
        "measurements": {"complex_bpf_desired_rms_v": "desired_rms"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIIP_TB rx_mix_ip 0 sin(1.35 10m 2meg 0 0 0)
VIIN_TB rx_mix_in 0 sin(1.35 -10m 2meg 0 0 0)
VIQP_TB rx_mix_qp 0 sin(1.35 10m 2meg 0 0 90)
VIQN_TB rx_mix_qn 0 sin(1.35 -10m 2meg 0 0 90)
.tran 2n 8u 3u
.meas tran desired_rms RMS v(bpf_ip,bpf_in) FROM=5u TO=8u
.end
""",
    },
    "complex_bpf_image": {
        "blocks": ["complex_bpf"],
        "measurements": {"complex_bpf_image_rms_v": "image_rms"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIIP_TB rx_mix_ip 0 sin(1.35 10m 2meg 0 0 0)
VIIN_TB rx_mix_in 0 sin(1.35 -10m 2meg 0 0 0)
VIQP_TB rx_mix_qp 0 sin(1.35 10m 2meg 0 0 -90)
VIQN_TB rx_mix_qn 0 sin(1.35 -10m 2meg 0 0 -90)
.tran 2n 8u 3u
.meas tran image_rms RMS v(bpf_ip,bpf_in) FROM=5u TO=8u
.end
""",
    },
    "limiter_low": {
        "blocks": ["limiter_rssi"],
        "measurements": {"limiter_low_pp_v": "limit_pp", "rssi_low_v": "rssi_value"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIP_TB bpf_ip 0 sin(1.35 0.5m 2meg)
VIN_TB bpf_in 0 sin(1.35 -0.5m 2meg)
VIQP_TB bpf_qp 0 1.35
VIQN_TB bpf_qn 0 1.35
.tran 2n 12u 4u
.meas tran limit_pp PP v(limitp,limitn) FROM=8u TO=12u
.meas tran rssi_value AVG v(rssi) FROM=8u TO=12u
.end
""",
    },
    "limiter_high": {
        "blocks": ["limiter_rssi"],
        "measurements": {"limiter_high_pp_v": "limit_pp", "rssi_high_v": "rssi_value"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIP_TB bpf_ip 0 sin(1.35 20m 2meg)
VIN_TB bpf_in 0 sin(1.35 -20m 2meg)
VIQP_TB bpf_qp 0 1.35
VIQN_TB bpf_qn 0 1.35
.tran 2n 12u 4u
.meas tran limit_pp PP v(limitp,limitn) FROM=8u TO=12u
.meas tran rssi_value AVG v(rssi) FROM=8u TO=12u
.end
""",
    },
    "demod_low": {
        "blocks": ["if_demodulator"],
        "measurements": {"demod_low_data_v": "data_value"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIP_TB limitp 0 sin(1.35 500m 1.84meg 0 0 0)
VIN_TB limitn 0 sin(1.35 -500m 1.84meg 0 0 0)
VQP_TB limitqp 0 sin(1.35 500m 1.84meg 0 0 90)
VQN_TB limitqn 0 sin(1.35 -500m 1.84meg 0 0 90)
.tran 2n 18u 5u
.meas tran data_value AVG v(rxdata) FROM=10u TO=14u
.end
""",
    },
    "demod_high": {
        "blocks": ["if_demodulator"],
        "measurements": {"demod_high_data_v": "data_value"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIP_TB limitp 0 sin(1.35 500m 2.16meg 0 0 0)
VIN_TB limitn 0 sin(1.35 -500m 2.16meg 0 0 0)
VQP_TB limitqp 0 sin(1.35 500m 2.16meg 0 0 90)
VQN_TB limitqn 0 sin(1.35 -500m 2.16meg 0 0 90)
.tran 2n 18u 5u
.meas tran data_value AVG v(rxdata) FROM=10u TO=14u
.end
""",
    },
    "tx_modulator": {
        "blocks": ["tx_fsk_modulator"],
        "measurements": {
            "tx_fsk_low_period3_s": "low_3cycles",
            "tx_fsk_high_period10_s": "high_10cycles",
            "tx_fsk_output_pp_v": "output_pp",
        },
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VDATA_TB txdata 0 pulse(0 2.7 30u 1n 1n 30u 80u)
.ic v(fsk_ip)=0 v(fsk_in)=2.7 v(fsk_qp)=0 v(fsk_qn)=2.7
.tran 5n 75u 5u uic
.meas tran low_3cycles TRIG v(fsk_ip,fsk_in) VAL=0 RISE=1 FROM=8u TO=28u TARG v(fsk_ip,fsk_in) VAL=0 RISE=4 FROM=8u TO=28u
.meas tran high_10cycles TRIG v(fsk_ip,fsk_in) VAL=0 RISE=8 FROM=40u TO=70u TARG v(fsk_ip,fsk_in) VAL=0 RISE=18 FROM=40u TO=70u
.meas tran output_pp PP v(fsk_ip,fsk_in) FROM=40u TO=70u
.end
""",
    },
    "tx_modulator_self_start": {
        "blocks": ["tx_fsk_modulator"],
        "measurements": {"tx_fsk_self_start_pp_v": "startup_pp"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VDATA_TB txdata 0 0
.tran 5n 15u
.meas tran startup_pp PP v(fsk_ip,fsk_in) FROM=8u TO=15u
.end
""",
    },
    "gaussian_filter": {
        "blocks": ["gaussian_filters"],
        "measurements": {
            "gaussian_gain_100k_db": "gain_100k",
            "gaussian_gain_1m_db": "gain_1m",
            "gaussian_gain_2m_db": "gain_2m",
        },
        "body": r"""
.option temp=27 reltol=1e-4 abstol=1e-11 vntol=1e-6
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VIP_TB fsk_ip 0 dc 1.35 ac 0.5
VIN_TB fsk_in 0 dc 1.35 ac 0.5 180
VQP_TB fsk_qp 0 1.35
VQN_TB fsk_qn 0 1.35
.ac dec 100 10k 20meg
.meas ac gain_100k FIND db(v(gauss_ip)-v(gauss_in)) AT=100k
.meas ac gain_1m FIND db(v(gauss_ip)-v(gauss_in)) AT=1meg
.meas ac gain_2m FIND db(v(gauss_ip)-v(gauss_in)) AT=2meg
.end
""",
    },
    "tx_mixer": {
        "blocks": ["tx_ssb_mixer"],
        "measurements": {"tx_mixer_rf_pp_v": "rf_pp"},
        "body": r"""
.option temp=27 reltol=2e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vcas 0 1.85
VBIP_TB gauss_ip 0 sin(1.35 100m 160k 0 0 0)
VBIN_TB gauss_in 0 sin(1.35 -100m 160k 0 0 0)
VBQP_TB gauss_qp 0 sin(1.35 100m 160k 0 0 90)
VBQN_TB gauss_qn 0 sin(1.35 -100m 160k 0 0 90)
VLOIP_TB loip 0 pulse(0.1 2.6 0 30p 30p 178.3p 416.667p)
VLOIN_TB loin 0 pulse(2.6 0.1 0 30p 30p 178.3p 416.667p)
VLOQP_TB loqp 0 pulse(0.1 2.6 104.167p 30p 30p 178.3p 416.667p)
VLOQN_TB loqn 0 pulse(2.6 0.1 104.167p 30p 30p 178.3p 416.667p)
RLOAD_TB tx_mixp tx_mixn 1k
.tran 20p 12.5u 6.25u
.meas tran rf_pp PP v(tx_mixp,tx_mixn) FROM=6.25u TO=12.5u
.end
""",
    },
    "pa_ac": {
        "blocks": ["power_amplifier"],
        "measurements": {"pa_gain_2p4g_db": "gain_2p4g"},
        "body": r"""
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbpa 0 1.55
VCAS_TB bias_vcas 0 1.85
VINP_TB tx_mixp 0 dc 1.35 ac 0.5
VINN_TB tx_mixn 0 dc 1.35 ac 0.5 180
RLOAD_TB txp txn 50
.ac dec 200 500meg 5gig
.meas ac gain_2p4g FIND db(v(txp)-v(txn)) AT=2.4g
.end
""",
    },
    "pa_tran": {
        "blocks": ["power_amplifier"],
        "measurements": {"pa_output_rms_v": "pout_rms", "pa_supply_current_a": "idd_avg"},
        "body": r"""
.option temp=27 reltol=1e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbpa 0 1.55
VCAS_TB bias_vcas 0 1.85
VINP_TB tx_mixp 0 sin(1.35 120m 2.4g)
VINN_TB tx_mixn 0 sin(1.35 -120m 2.4g)
RLOAD_TB txp txn 50
.tran 2p 20n 5n
.meas tran pout_rms RMS v(txp,txn) FROM=10n TO=20n
.meas tran idd_avg AVG i(VDD_TB) FROM=10n TO=20n
.end
""",
    },
    "vco": {
        "blocks": ["vco"],
        "measurements": {"vco_cycles40_s": "cycles_40", "vco_tank_pp_v": "tank_pp"},
        "body": r"""
.option temp=27 reltol=2e-3 abstol=1e-10 vntol=1e-5 method=gear gmin=1e-10 rshunt=1e12
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbrf 0 1.45
VTUNE_TB vctrl 0 1.35
VC0_TB cal0 0 2.7
VC1_TB cal1 0 2.7
VC2_TB cal2 0 2.7
VC3_TB cal3 0 2.7
VC4_TB cal4 0 2.7
VC5_TB cal5 0 2.7
.ic v(vcop)=2.0 v(vcon)=1.7
.tran 3p 80n 10n
.meas tran cycles_40 TRIG v(vcop,vcon) VAL=0 RISE=20 FROM=30n TO=80n TARG v(vcop,vcon) VAL=0 RISE=60 FROM=30n TO=80n
.meas tran tank_pp PP v(vcop,vcon) FROM=50n TO=80n
.end
""",
    },
    "vco_loaded_low": {
        "blocks": ["vco", "prescaler_frontend", "synthesizer_interconnect"],
        "measurements": {"vco_loaded_low_cycles20_s": "cycles_20"},
        "body": r"""
.option temp=27 reltol=3e-3 abstol=1e-10 vntol=1e-5 method=gear gmin=1e-10 rshunt=1e12
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbrf 0 1.45
VTUNE_TB vctrl 0 1.35
VC0_TB cal0 0 0
VC1_TB cal1 0 0
VC2_TB cal2 0 0
VC3_TB cal3 0 0
VC4_TB cal4 0 0
VC5_TB cal5 0 0
VMOD_TB mod16_ctl 0 2.7
.ic v(vcop)=2.0 v(vcon)=1.7
.tran 50p 500n 100n
.meas tran cycles_20 TRIG v(vcop,vcon) VAL=0 RISE=20 FROM=300n TO=500n TARG v(vcop,vcon) VAL=0 RISE=40 FROM=300n TO=500n
.end
""",
    },
    "vco_loaded_high": {
        "blocks": ["vco", "prescaler_frontend", "synthesizer_interconnect"],
        "measurements": {"vco_loaded_high_cycles20_s": "cycles_20"},
        "body": r"""
.option temp=27 reltol=3e-3 abstol=1e-10 vntol=1e-5 method=gear gmin=1e-10 rshunt=1e12
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbrf 0 1.45
VTUNE_TB vctrl 0 1.35
VC0_TB cal0 0 2.7
VC1_TB cal1 0 2.7
VC2_TB cal2 0 2.7
VC3_TB cal3 0 2.7
VC4_TB cal4 0 2.7
VC5_TB cal5 0 2.7
VMOD_TB mod16_ctl 0 2.7
.ic v(vcop)=2.0 v(vcon)=1.7
.tran 50p 500n 100n
.meas tran cycles_20 TRIG v(vcop,vcon) VAL=0 RISE=20 FROM=300n TO=500n TARG v(vcop,vcon) VAL=0 RISE=40 FROM=300n TO=500n
.end
""",
    },
    "clock_generator": {
        "blocks": ["clock_generator"],
        "measurements": {
            "clock_div_cycles4_s": "div_4cycles",
            "clock_lo_cycles10_s": "lo_10cycles",
            "clock_lo_i_pp_v": "lo_i_pp",
        },
        "body": r"""
.option temp=27 reltol=2e-3 abstol=1e-11 vntol=1e-6 method=gear
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbana 0 1.05
VCP_TB vcop 0 pulse(0.2 2.5 0 20p 20p 272.5p 625p)
VCN_TB vcon 0 pulse(2.5 0.2 0 20p 20p 272.5p 625p)
.ic v(divip)=2.0 v(divin)=1.7 v(divqp)=2.7 v(divqn)=0
.tran 5p 12n 2n
.meas tran div_4cycles TRIG v(divip,divin) VAL=0 RISE=2 FROM=3n TO=12n TARG v(divip,divin) VAL=0 RISE=6 FROM=3n TO=12n
.meas tran lo_10cycles TRIG v(loip,loin) VAL=0 RISE=5 FROM=3n TO=12n TARG v(loip,loin) VAL=0 RISE=15 FROM=3n TO=12n
.meas tran lo_i_pp PP v(loip,loin) FROM=6n TO=12n
.end
""",
    },
    "prescaler_diagnostic": {
        "blocks": ["prescaler_frontend"],
        "measurements": {
            "prescaler_mod15_period_s": "mod15_period",
            "prescaler_mod16_period_s": "mod16_period",
        },
        "body": r"""
VDD_TB vdd 0 2.7
VCLK_TB prescaler_clk 0 pulse(0 2.7 0 100p 100p 4.8n 10n)
.tran 100p 700n 20n
.meas tran mod15_period TRIG v(prescaler_div15) VAL=1.35 RISE=2 FROM=100n TO=700n TARG v(prescaler_div15) VAL=1.35 RISE=3 FROM=100n TO=700n
.meas tran mod16_period TRIG v(prescaler_div16) VAL=1.35 RISE=2 FROM=100n TO=700n TARG v(prescaler_div16) VAL=1.35 RISE=3 FROM=100n TO=700n
.end
""",
    },
    "prescaler_rf": {
        "blocks": ["prescaler_frontend"],
        "measurements": {"cml_div16_four_periods_s": "div_4periods"},
        "body": r"""
VDD_TB vdd 0 2.7
VBIAS_TB bias_vbrf 0 1.45
VCLK_TB prescaler_clk 0 pulse(0.2 2.5 0 20p 20p 272.5p 625p)
.tran 2p 80n 5n
.meas tran div_4periods TRIG v(prescaler_rf16) VAL=1.35 RISE=2 FROM=10n TO=80n TARG v(prescaler_rf16) VAL=1.35 RISE=6 FROM=10n TO=80n
.end
""",
    },
    "program_counter_159": {
        "blocks": ["program_counter_159"],
        "measurements": {"program_counter_159_period_s": "frame_period"},
        "body": r"""
VDD_TB vdd 0 2.7
VCLK_TB prescaler_div15 0 pulse(0 2.7 0 100p 100p 4.8n 10n)
.tran 100p 5u 100n
.meas tran frame_period TRIG v(program_frame159) VAL=1.35 RISE=2 FROM=1u TO=5u TARG v(program_frame159) VAL=1.35 RISE=3 FROM=1u TO=5u
.end
""",
    },
    "program_counter_150": {
        "blocks": ["program_counter_150"],
        "measurements": {"program_counter_150_period_s": "frame_period"},
        "body": r"""
VDD_TB vdd 0 2.7
VCLK_TB prescaler_div16 0 pulse(0 2.7 0 100p 100p 4.8n 10n)
.tran 100p 5u 100n
.meas tran frame_period TRIG v(program_frame150) VAL=1.35 RISE=2 FROM=1u TO=5u TARG v(program_frame150) VAL=1.35 RISE=3 FROM=1u TO=5u
.end
""",
    },
    "swallow_counter": {
        "blocks": ["swallow_counter"],
        "measurements": {"swallow_done_pp_v": "done_pp"},
        "body": r"""
VDD_TB vdd 0 2.7
VCLK_TB prescaler_div16 0 pulse(0 2.7 0 0.5n 0.5n 4.5n 10n)
VS0_TB chan_s0 0 2.7
VS1_TB chan_s1 0 0
VS2_TB chan_s2 0 2.7
VS3_TB chan_s3 0 2.7
VS4_TB chan_s4 0 0
VS5_TB chan_s5 0 0
VS6_TB chan_s6 0 0
.tran 100p 250n
.meas tran done_pp PP v(swallow_done) FROM=20n TO=250n
.end
""",
    },
    "reference_divider": {
        "blocks": ["reference_divider"],
        "measurements": {"reference_divider_period_s": "ref_period"},
        "body": r"""
VDD_TB vdd 0 2.7
VREF_TB ref12 0 pulse(0 2.7 0 1n 1n 40.667n 83.333n)
.tran 200p 6u 100n
.meas tran ref_period TRIG v(ref667) VAL=1.35 RISE=2 FROM=1u TO=6u TARG v(ref667) VAL=1.35 RISE=3 FROM=1u TO=6u
.end
""",
    },
    "pll_loop": {
        "blocks": ["pfd_charge_pump_loop_filter"],
        "measurements": {"pll_vctrl_rise_v": "vctrl_rise", "pll_vctrl_fall_v": "vctrl_fall"},
        "body": r"""
VDD_TB vdd 0 2.7
VBN_TB bias_vbn 0 1.05
VBP_TB bias_vbp 0 1.65
VUP_TB up 0 pulse(0 2.7 1u 1n 1n 1u 4u)
VDN_TB down 0 pulse(0 2.7 3u 1n 1n 1u 4u)
VC0_TB cal0 0 2.7
VC1_TB cal1 0 2.7
VC2_TB cal2 0 0
VC3_TB cal3 0 0
VC4_TB cal4 0 0
VC5_TB cal5 0 0
.tran 2n 10u
.meas tran vctrl_rise FIND v(vctrl) AT=2u
.meas tran vctrl_fall FIND v(vctrl) AT=4u
.end
""",
    },
    "rc_calibration": {
        "blocks": ["rc_calibration"],
        "measurements": {"rc_cal_10cycles_s": "rc_10cycles"},
        "body": r"""
VDD_TB vdd 0 2.7
VREF_TB ref12 0 pulse(0 2.7 0 1n 1n 40.667n 83.333n)
.tran 200p 2u 100n
.meas tran rc_10cycles TRIG v(rcclk) VAL=1.35 RISE=10 FROM=200n TO=2u TARG v(rcclk) VAL=1.35 RISE=20 FROM=200n TO=2u
.end
""",
    },
    "synthesizer": {
        "blocks": [
            "bias_reference", "rc_calibration", "reference_divider",
            "pfd_charge_pump_loop_filter", "vco", "prescaler_frontend",
            "program_counter_150", "swallow_counter", "programmable_divider_control",
            "synthesizer_interconnect", "top_interconnect",
        ],
        "measurements": {
            "synth_vco_cycles50_s": "vco_50cycles",
            "synth_div_period_s": "div_period",
            "synth_divider_swing_v": "div_pp",
            "synth_vctrl_ripple_v": "vctrl_pp",
            "synth_supply_current_a": "idd_avg",
        },
        "body": r"""
.option temp=27 reltol=3e-3 abstol=1e-10 vntol=1e-5 method=gear gmin=1e-10 rshunt=1e12
VDD_TB vdd 0 2.7
VREF_TB ref12 0 pulse(0 2.7 0 2n 2n 39.667n 83.333n)
.ic v(vcop)=2.0 v(vcon)=1.7 v(vctrl)=1.35
.tran 50p 3.4u 200n
.meas tran vco_50cycles TRIG v(vcop,vcon) VAL=0 RISE=50 FROM=2.4u TO=3.4u TARG v(vcop,vcon) VAL=0 RISE=100 FROM=2.4u TO=3.4u
.meas tran div_period TRIG v(divout) VAL=1.35 RISE=1 FROM=500n TO=3.4u TARG v(divout) VAL=1.35 RISE=2 FROM=500n TO=3.4u
.meas tran div_pp PP v(divout) FROM=500n TO=3.4u
.meas tran vctrl_pp PP v(vctrl) FROM=3.0u TO=3.4u
.meas tran idd_avg AVG i(VDD_TB) FROM=2.6u TO=3.4u
.end
""",
    },
    "transceiver_smoke": {
        "blocks": "ALL",
        "measurements": {
            "top_smoke_vco_pp_v": "vco_pp",
            "top_smoke_supply_current_a": "idd_avg",
        },
        "body": r"""
.option temp=27 reltol=4e-3 abstol=1e-10 vntol=2e-5 method=gear gmin=1e-10 rshunt=1e12
VDD_TB vdd 0 2.7
VREF_TB ref12 0 pulse(0 2.7 0 2n 2n 39.667n 83.333n)
VDATA_TB txdata 0 2.7
VTXEN_TB txen 0 2.7
RLOAD_TB antp antn 50
.ic v(vcop)=2.0 v(vcon)=1.7 v(vctrl)=1.35
.tran 75p 30n 1n
.meas tran vco_pp PP v(vcop,vcon) FROM=15n TO=30n
.meas tran idd_avg AVG i(VDD_TB) FROM=15n TO=30n
.end
""",
    },
}


DERIVED = {
    "complex_bpf_image_rejection_db": "20*log10(complex_bpf_desired_rms_v/complex_bpf_image_rms_v)",
    "tx_fsk_low_hz": "3/tx_fsk_low_period3_s",
    "tx_fsk_high_hz": "10/tx_fsk_high_period10_s",
    "tx_fsk_separation_hz": "tx_fsk_high_hz-tx_fsk_low_hz",
    "pa_output_w": "pa_output_rms_v*pa_output_rms_v/50",
    "pa_output_dbm": "10*log10(pa_output_w/0.001)",
    "vco_frequency_hz": "40/vco_cycles40_s",
    "vco_loaded_low_hz": "20/vco_loaded_low_cycles20_s",
    "vco_loaded_high_hz": "20/vco_loaded_high_cycles20_s",
    "vco_loaded_span_hz": "abs(vco_loaded_low_hz-vco_loaded_high_hz)",
    "clock_divider_frequency_hz": "4/clock_div_cycles4_s",
    "clock_lo_frequency_hz": "10/clock_lo_cycles10_s",
    "cml_div16_period_s": "cml_div16_four_periods_s/4",
    "synth_vco_frequency_hz": "50/synth_vco_cycles50_s",
    "synth_feedback_frequency_hz": "1/synth_div_period_s",
    "synth_divide_ratio": "synth_vco_frequency_hz/synth_feedback_frequency_hz",
}
