from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from .common import (
    Candidate,
    SimulationError,
    harmonic,
    magnitude_at,
    persistent_settling_time,
    private_deck,
    read_complex_table,
    read_real_table,
    run_ngspice,
    upper_3db_frequency,
    waveform_metrics,
)


PORTS: dict[str, tuple[str, ...]] = {
    "agc_controller_tl_run_01": (
        "detp", "detn", "oa", "pkd", "agc", "agc_pkd_ref", "agc_ref", "vcc", "vss",
    ),
    "bias_servo_tl_run_05": (
        "vcc", "vtia", "inp", "inn", "bias_ldo_ref", "bias_inp_ref", "bias_inn_ref", "vss",
    ),
    "common_mode_controller_tl_run_08": (
        "gc", "vc1", "vc1b", "vc2", "vc2b", "cmc_fixed", "vcc", "vss",
    ),
    "input_tia_tl_regression": ("inp", "inn", "tia_p", "tia_n", "vtia", "vss"),
    "interstage_interface_tl_run_01": (
        "tia_p", "tia_n", "v1p", "v1n", "vga1p", "vga1n", "v2p", "v2n",
        "vga2p", "vga2n", "bufinp", "bufinn", "vcc", "vss",
    ),
    "mode_switch_tl_run_08": ("mgc", "agc", "mc", "gc", "vcc", "vss"),
    "output_buffer_tl_regression": (
        "bufinp", "bufinn", "outp", "outn", "finalp", "finaln", "vcc", "vss",
    ),
    "peak_detector_tl_regression": (
        "finalp", "finaln", "detp", "detn", "pkd_rebias_ref", "vcc", "vss",
    ),
    "vga1_tl_regression": (
        "v1p", "v1n", "vga1p", "vga1n", "vc1", "vc1b", "vcc", "vss",
    ),
    "vga2_tl_regression": (
        "v2p", "v2n", "vga2p", "vga2n", "vc2", "vc2b", "bw_cntrl", "vcc", "vss",
    ),
}

HELPER_TASKS = {"agc_controller_tl_run_01", "interstage_interface_tl_run_01"}


def _mean_in_window(time: list[float], values: list[float], start: float, stop: float) -> float:
    selected = [value for t, value in zip(time, values, strict=True) if start <= t <= stop]
    if not selected:
        raise SimulationError(f"no samples in window {start} through {stop}")
    return sum(selected) / len(selected)


def _differential(values_p: list[complex], values_n: list[complex]) -> list[complex]:
    return [left - right for left, right in zip(values_p, values_n, strict=True)]


def _differential_real(values_p: list[float], values_n: list[float]) -> list[float]:
    return [left - right for left, right in zip(values_p, values_n, strict=True)]


def _db(value: float) -> float:
    if value <= 0.0:
        raise SimulationError("cannot convert nonpositive gain to dB")
    return 20.0 * math.log10(value)


def evaluate_agc(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for oa in (1.2, 1.4):
        case = root / f"oa-{oa:.1f}"
        circuit = f"""
VCC vcc 0 3.3
VOA oa 0 {oa}
VPKDREF agc_pkd_ref 0 0.8
VAGCREF agc_ref 0 1.2864
VDETN detn 0 3.15
VDETD detp detn PWL(0 0 1u 0 1.01u 20m 3u 20m 3.01u 50m 5u 50m 5.01u 0 6u 0 6.01u 20m 8u 20m 8.01u 50m 10u 50m)
RLOAD agc 0 1Meg
CLOAD agc 0 10p
XDUT detp detn oa pkd agc agc_pkd_ref agc_ref vcc 0 candidate
"""
        controls = "tran 1n 10u\nwrdata tran.dat v(pkd) v(agc)"
        run_ngspice(private_deck("AGC private fixture", candidate, circuit, controls), case)
        time, vectors = read_real_table(case / "tran.dat", 2, 5_000)
        pkd, agc = vectors
        key = f"oa_{str(oa).replace('.', '_')}"
        for label, start, stop in (("zero", 0.5e-6, 0.9e-6), ("20mv", 2.0e-6, 2.9e-6), ("50mv", 4.0e-6, 4.9e-6)):
            results[f"{key}_pkd_{label}_v"] = _mean_in_window(time, pkd, start, stop)
            results[f"{key}_agc_{label}_v"] = _mean_in_window(time, agc, start, stop)
        final20 = _mean_in_window(time, agc, 2.7e-6, 2.9e-6)
        final50 = _mean_in_window(time, agc, 4.7e-6, 4.9e-6)
        results[f"{key}_settling_20mv_s"] = persistent_settling_time(
            time, agc, 1.01e-6, final20, 0.01, 3.0e-6
        )
        results[f"{key}_settling_50mv_s"] = persistent_settling_time(
            time, agc, 3.01e-6, final50, 0.01, 5.0e-6
        )
        results[f"{key}_agc_min_v"] = min(agc)
        results[f"{key}_agc_max_v"] = max(agc)
    delta = 0.05 - 0.02
    results["pkd_closed_loop_gain_v_per_v"] = (
        results["oa_1_2_pkd_50mv_v"] - results["oa_1_2_pkd_20mv_v"]
    ) / delta
    return results


def _bias_replica() -> str:
    return """
RRP vtia bias_tia_ap 80
QAP bias_tia_ap inp 0 QN_SYS area=6
QBP vtia bias_tia_ap tia_p QN_SYS area=1
RRFP vtia bias_tia_fbiasp 867
QRFP bias_tia_fbiasp bias_tia_fbiasp 0 QN_SYS area=1
QSP tia_p bias_tia_fbiasp 0 QN_SYS area=1
RFP tia_p inp 250
RRN vtia bias_tia_an 80
QAN bias_tia_an inn 0 QN_SYS area=6
QBN vtia bias_tia_an tia_n QN_SYS area=1
RRFN vtia bias_tia_fbiasn 867
QRFN bias_tia_fbiasn bias_tia_fbiasn 0 QN_SYS area=1
QSN tia_n bias_tia_fbiasn 0 QN_SYS area=1
RFN tia_n inn 250
"""


def evaluate_bias(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    corners = (("equal", 5e-3, 5e-3), ("mismatch", 5e-3, 3.75e-3))
    for label, inp_current, inn_current in corners:
        for vcc in (3.0, 3.3, 3.6):
            case = root / f"op-{label}-{vcc:.1f}"
            circuit = f"""
VCC vcc 0 {vcc}
VLDO bias_ldo_ref 0 2.05
VINPREF bias_inp_ref 0 0.78
VINNREF bias_inn_ref 0 0.78
IINP 0 inp {inp_current}
IINN 0 inn {inn_current}
{_bias_replica()}
XDUT vcc vtia inp inn bias_ldo_ref bias_inp_ref bias_inn_ref 0 candidate
"""
            controls = "op\nwrdata op.dat v(vtia) v(inp) v(inn) i(VCC)"
            run_ngspice(private_deck("Bias-servo private fixture", candidate, circuit, controls), case)
            _, vectors = read_real_table(case / "op.dat", 4)
            suffix = f"{label}_{str(vcc).replace('.', '_')}"
            results[f"vtia_{suffix}_v"] = vectors[0][-1]
            results[f"inp_{suffix}_v"] = vectors[1][-1]
            results[f"inn_{suffix}_v"] = vectors[2][-1]
            results[f"supply_current_{suffix}_a"] = abs(vectors[3][-1])

    for transient_label, final_inn_current in (("equal", "5m"), ("mismatch", "3.75m")):
        case = root / f"transient-{transient_label}"
        circuit = f"""
VCC vcc 0 PWL(0 0 100u 3.3 5m 3.3)
VLDO bias_ldo_ref 0 2.05
VINPREF bias_inp_ref 0 0.78
VINNREF bias_inn_ref 0 0.78
IINP 0 inp PWL(0 0 1m 0 1.01m 5m 5m 5m)
IINN 0 inn PWL(0 0 1m 0 1.01m {final_inn_current} 5m {final_inn_current})
IRP 0 inp SINE(0 10u 100k)
IRN 0 inn SINE(0 10u 100k 0 0 180)
{_bias_replica()}
XDUT vcc vtia inp inn bias_ldo_ref bias_inp_ref bias_inn_ref 0 candidate
"""
        controls = "tran 20n 5m\nwrdata tran.dat v(vtia) v(inp) v(inn)"
        run_ngspice(private_deck("Bias-servo transient fixture", candidate, circuit, controls), case, 180)
        time, vectors = read_real_table(case / "tran.dat", 3, 100_000)
        vtia, inp, inn = vectors
        startup_times = []
        step_times = []
        for values in (vtia, inp, inn):
            startup_final = _mean_in_window(time, values, 0.8e-3, 0.95e-3)
            final = _mean_in_window(time, values, 4.8e-3, 5.0e-3)
            startup_times.append(
                persistent_settling_time(time, values, 100e-6, startup_final, 0.01, 1.0e-3)
            )
            step_times.append(
                persistent_settling_time(time, values, 1.01e-3, final, 0.01, 5.0e-3)
            )
        results[f"startup_settling_{transient_label}_s"] = max(startup_times)
        results[f"current_step_settling_{transient_label}_s"] = max(step_times)
        results[f"inp_ripple_{transient_label}_vpp"] = max(
            value for t, value in zip(time, inp, strict=True) if t >= 4.8e-3
        ) - min(value for t, value in zip(time, inp, strict=True) if t >= 4.8e-3)
        results[f"inn_ripple_{transient_label}_vpp"] = max(
            value for t, value in zip(time, inn, strict=True) if t >= 4.8e-3
        ) - min(value for t, value in zip(time, inn, strict=True) if t >= 4.8e-3)
    return results


def evaluate_cmc(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for loaded in (False, True):
        load = 225e3 if loaded else 1e12
        for gc in (1.2, 1.3, 1.4):
            label = "loaded" if loaded else "unloaded"
            case = root / f"op-{label}-{gc:.1f}"
            circuit = f"""
VCC vcc 0 3.3
VFIX cmc_fixed 0 1.2
VGC gc 0 {gc}
R1 vc1 0 {load}
R1B vc1b 0 {load}
R2 vc2 0 {load}
R2B vc2b 0 {load}
C1 vc1 0 50f
C1B vc1b 0 50f
C2 vc2 0 50f
C2B vc2b 0 50f
XDUT gc vc1 vc1b vc2 vc2b cmc_fixed vcc 0 candidate
"""
            controls = "op\nwrdata op.dat v(vc1) v(vc1b) v(vc2) v(vc2b) i(VCC)"
            run_ngspice(private_deck("CMC private fixture", candidate, circuit, controls), case)
            _, vectors = read_real_table(case / "op.dat", 5)
            suffix = f"{label}_{str(gc).replace('.', '_')}"
            vc1, vc1b, vc2, vc2b, current = (values[-1] for values in vectors)
            results[f"vc1_diff_{suffix}_v"] = vc1 - vc1b
            results[f"vc2_diff_{suffix}_v"] = vc2 - vc2b
            results[f"vc1_cm_{suffix}_v"] = 0.5 * (vc1 + vc1b)
            results[f"vc2_cm_{suffix}_v"] = 0.5 * (vc2 + vc2b)
            results[f"supply_current_{suffix}_a"] = abs(current)

    case = root / "transient"
    circuit = """
VCC vcc 0 3.3
VFIX cmc_fixed 0 1.2
VGC gc 0 PWL(0 1.2 100n 1.2 101n 1.4 2u 1.4)
R1 vc1 0 225k
R1B vc1b 0 225k
R2 vc2 0 225k
R2B vc2b 0 225k
C1 vc1 0 50f
C1B vc1b 0 50f
C2 vc2 0 50f
C2B vc2b 0 50f
XDUT gc vc1 vc1b vc2 vc2b cmc_fixed vcc 0 candidate
"""
    controls = "tran 0.5n 2u\nwrdata tran.dat v(vc1) v(vc1b) v(vc2) v(vc2b)"
    run_ngspice(private_deck("CMC transient fixture", candidate, circuit, controls), case)
    time, vectors = read_real_table(case / "tran.dat", 4, 2_000)
    diff1 = _differential_real(vectors[0], vectors[1])
    diff2 = _differential_real(vectors[2], vectors[3])
    final1 = _mean_in_window(time, diff1, 1.8e-6, 2e-6)
    final2 = _mean_in_window(time, diff2, 1.8e-6, 2e-6)
    results["vc1_settling_s"] = persistent_settling_time(time, diff1, 101e-9, final1, 0.01)
    results["vc2_settling_s"] = persistent_settling_time(time, diff2, 101e-9, final2, 0.01)
    return results


def evaluate_input_tia(candidate: Candidate, root: Path) -> dict[str, float]:
    case = root / "nominal"
    circuit = """
VTIASUP vtia 0 2.05
IINP 0 inp DC 0 AC 0.5 SIN(0 10u 16G)
IINN inn 0 DC 0 AC 0.5 SIN(0 10u 16G)
XDUT inp inn tia_p tia_n vtia 0 candidate
"""
    controls = """op
wrdata op.dat v(inp) v(inn) v(tia_p) v(tia_n)
ac dec 100 1Meg 100G
wrdata ac.dat v(tia_p) v(tia_n)
tran 0.5p 10n 8n
wrdata tran.dat v(tia_p) v(tia_n)
"""
    run_ngspice(private_deck("Input-TIA private fixture", candidate, circuit, controls), case)
    _, op = read_real_table(case / "op.dat", 4)
    frequency, ac = read_complex_table(case / "ac.dat", 2, 400)
    differential = _differential(ac[0], ac[1])
    time, transient = read_real_table(case / "tran.dat", 2, 2_000)
    transient_diff = _differential_real(transient[0], transient[1])
    return {
        "inp_dc_v": op[0][-1],
        "inn_dc_v": op[1][-1],
        "output_common_mode_v": 0.5 * (op[2][-1] + op[3][-1]),
        "output_offset_v": abs(op[2][-1] - op[3][-1]),
        "transimpedance_10mhz_ohm": magnitude_at(frequency, differential, 10e6),
        "transimpedance_33ghz_ohm": magnitude_at(frequency, differential, 33e9),
        "minimum_transimpedance_10mhz_to_33ghz_ohm": min(
            magnitude_at(frequency, differential, 10e6),
            magnitude_at(frequency, differential, 33e9),
            *(
                abs(value)
                for f, value in zip(frequency, differential, strict=True)
                if 10e6 <= f <= 33e9
            ),
        ),
        "transimpedance_16ghz_ohm": magnitude_at(frequency, differential, 16e9),
        "bandwidth_hz": upper_3db_frequency(frequency, differential, 10e6),
        "transient_transimpedance_16ghz_ohm": abs(harmonic(time, transient_diff, 16e9)) / 20e-6,
    }


def _interface_case(candidate: Candidate, root: Path, path_index: int) -> dict[str, float]:
    names = (("tia_p", "tia_n", "v1p", "v1n", 1.568), ("vga1p", "vga1n", "v2p", "v2n", 2.2), ("vga2p", "vga2n", "bufinp", "bufinn", 2.064))
    inp, inn, outp, outn, common = names[path_index - 1]
    sources = []
    for index, (pinp, pinn, _, _, pcm) in enumerate(names, 1):
        ac = "AC 0.5 SIN(0 10m 16G)" if index == path_index else "AC 0"
        phase = "" if index == path_index else ""
        sources.append(f"VP{index} {pinp} 0 DC {pcm} {ac}")
        if index == path_index:
            sources.append(f"VN{index} {pinn} 0 DC {pcm} AC 0.5 180 SIN(0 10m 16G 0 0 180)")
        else:
            sources.append(f"VN{index} {pinn} 0 DC {pcm} AC 0")
    loads = []
    for index, (_, _, pout, nout, _) in enumerate(names, 1):
        loads.extend((f"RP{index} {pout} load_ref 10k", f"RN{index} {nout} load_ref 10k", f"CP{index} {pout} 0 10f", f"CN{index} {nout} 0 10f"))
    circuit = "\n".join([
        "VCC vcc 0 3.3", "VLOAD load_ref 0 1.8", *sources, *loads,
        "XDUT tia_p tia_n v1p v1n vga1p vga1n v2p v2n vga2p vga2n bufinp bufinn vcc 0 candidate",
    ])
    controls = f"""op
wrdata op.dat v({outp}) v({outn})
ac dec 100 1Meg 100G
wrdata ac.dat v({outp}) v({outn})
tran 0.5p 10n 8n
wrdata tran.dat v({outp}) v({outn})
"""
    case = root / f"path-{path_index}"
    run_ngspice(private_deck(f"Interface path {path_index} fixture", candidate, circuit, controls), case)
    _, op = read_real_table(case / "op.dat", 2)
    frequency, ac = read_complex_table(case / "ac.dat", 2, 400)
    differential = _differential(ac[0], ac[1])
    time, transient = read_real_table(case / "tran.dat", 2, 2_000)
    transient_diff = _differential_real(transient[0], transient[1])
    gain10 = magnitude_at(frequency, differential, 10e6)
    gain10_db = _db(gain10)
    gain33_db = _db(magnitude_at(frequency, differential, 33e9))
    maximum_deviation = max(
        abs(gain33_db - gain10_db),
        *(
            abs(_db(abs(value)) - gain10_db)
            for f, value in zip(frequency, differential, strict=True)
            if 10e6 <= f <= 33e9
        ),
    )
    return {
        "gain_10mhz_db": gain10_db,
        "gain_16ghz_db": _db(magnitude_at(frequency, differential, 16e9)),
        "gain_33ghz_db": gain33_db,
        "output_common_mode_v": 0.5 * (op[0][-1] + op[1][-1]),
        "transient_gain_16ghz_db": _db(abs(harmonic(time, transient_diff, 16e9)) / 20e-3),
        "maximum_deviation_10mhz_to_33ghz_db": maximum_deviation,
    }


def evaluate_interfaces(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for path_index in (1, 2, 3):
        for name, value in _interface_case(candidate, root, path_index).items():
            results[f"path_{path_index}_{name}"] = value
    return results


def evaluate_mode(candidate: Candidate, root: Path) -> dict[str, float]:
    case = root / "switching"
    circuit = """
VCC vcc 0 3.3
VMGC mgc 0 1.4
VAGC agc 0 1.25
VMC mc 0 PULSE(0 3.3 2u 1n 1n 2u 5u)
RLOAD gc 0 1Meg
CLOAD gc 0 10p
XDUT mgc agc mc gc vcc 0 candidate
"""
    controls = "tran 0.5n 7u\nwrdata tran.dat v(mc) v(gc) i(VMGC) i(VAGC)"
    run_ngspice(private_deck("Mode-switch private fixture", candidate, circuit, controls), case)
    time, vectors = read_real_table(case / "tran.dat", 4, 5_000)
    mc, gc, imgc, iagc = vectors
    manual = _mean_in_window(time, gc, 1.5e-6, 1.9e-6)
    automatic = _mean_in_window(time, gc, 3.5e-6, 3.9e-6)
    final_auto = automatic
    final_manual = _mean_in_window(time, gc, 6.5e-6, 6.9e-6)
    return {
        "manual_gc_v": manual,
        "automatic_gc_v": automatic,
        "manual_error_v": abs(manual - 1.4),
        "automatic_error_v": abs(automatic - 1.25),
        "automatic_settling_s": persistent_settling_time(
            time, gc, 2.001e-6, final_auto, 0.001 / 1.25, 4.0e-6
        ),
        "manual_settling_s": persistent_settling_time(
            time, gc, 4.002e-6, final_manual, 0.001 / 1.4, 7.0e-6
        ),
        "inactive_mgc_current_a": max(abs(value) for t, value in zip(time, imgc, strict=True) if 3.5e-6 <= t <= 3.9e-6),
        "inactive_agc_current_a": max(abs(value) for t, value in zip(time, iagc, strict=True) if 1.5e-6 <= t <= 1.9e-6),
        "gc_min_v": min(gc),
        "gc_max_v": max(gc),
        "mc_min_v": min(mc),
        "mc_max_v": max(mc),
    }


def _buffer_case(candidate: Candidate, root: Path, amplitude: float, label: str) -> dict[str, float]:
    case = root / label
    circuit = f"""
VCC vcc 0 3.3
VINN bufinn 0 1.8
VDIFF bufinp bufinn SIN(0 {amplitude} 33.5G)
XDUT bufinp bufinn outp outn finalp finaln vcc 0 candidate
"""
    controls = "op\nwrdata op.dat v(outp) v(outn)\ntran 0.2p 2n 0.805970149253731n\nwrdata tran.dat v(bufinp) v(bufinn) v(outp) v(outn) v(finalp) v(finaln)"
    run_ngspice(private_deck("Output-buffer private fixture", candidate, circuit, controls), case)
    _, op = read_real_table(case / "op.dat", 2)
    time, vectors = read_real_table(case / "tran.dat", 6, 4_000)
    input_diff = _differential_real(vectors[0], vectors[1])
    collector_diff = _differential_real(vectors[2], vectors[3])
    final_diff = _differential_real(vectors[4], vectors[5])
    collector = waveform_metrics(time, collector_diff, 33.5e9)
    final = waveform_metrics(time, final_diff, 33.5e9)
    input_fundamental = abs(harmonic(time, input_diff, 33.5e9))
    return {
        "output_common_mode_v": 0.5 * (op[0][-1] + op[1][-1]),
        "positive_branch_current_a": abs((3.3 - op[0][-1]) / 50.0),
        "negative_branch_current_a": abs((3.3 - op[1][-1]) / 50.0),
        "collector_gain_db": _db(collector["fundamental_peak"] / input_fundamental),
        "final_swing_vpp": final["peak_to_peak"],
        "final_thd_ratio": final["thd_ratio"],
        "final_min_v": final["minimum"],
        "final_max_v": final["maximum"],
    }


def evaluate_buffer(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for label, amplitude in (("linearity", 0.24), ("maximum", 0.60)):
        for name, value in _buffer_case(candidate, root, amplitude, label).items():
            results[f"{label}_{name}"] = value
    return results


def _peak_case(candidate: Candidate, root: Path, amplitude_vpp: float) -> dict[str, float]:
    label = f"amp-{int(amplitude_vpp * 1e3)}mv"
    case = root / label
    peak = amplitude_vpp / 4.0
    circuit = f"""
VCC vcc 0 3.3
VREBIAS pkd_rebias_ref 0 2.48
VSP srcp 0 SIN(2.7 {peak} 33.5G)
VSN srcn 0 SIN(2.7 {peak} 33.5G 0 0 180)
RSP srcp finalp 1
RSN srcn finaln 1
XDUT finalp finaln detp detn pkd_rebias_ref vcc 0 candidate
"""
    controls = "op\nwrdata op.dat v(detp) v(detn)\ntran 0.5p 20n 17.0149253731343n\nwrdata tran.dat v(srcp) v(srcn) v(finalp) v(finaln) v(detp) v(detn)"
    run_ngspice(private_deck("Peak-detector private fixture", candidate, circuit, controls), case, 180)
    time, vectors = read_real_table(case / "tran.dat", 6, 5_000)
    source_diff = _differential_real(vectors[0], vectors[1])
    sensed_diff = _differential_real(vectors[2], vectors[3])
    detector_diff = _differential_real(vectors[4], vectors[5])
    source_fund = abs(harmonic(time, source_diff, 33.5e9))
    sensed_fund = abs(harmonic(time, sensed_diff, 33.5e9))
    return {
        "detector_output_v": sum(detector_diff) / len(detector_diff),
        "loading_fraction": max(0.0, 1.0 - sensed_fund / source_fund),
        "detector_min_v": min(detector_diff),
        "detector_max_v": max(detector_diff),
    }


def evaluate_peak(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for amplitude in (0.05, 0.20, 0.40, 0.55):
        key = f"{int(amplitude * 1e3)}mv"
        for name, value in _peak_case(candidate, root, amplitude).items():
            results[f"{key}_{name}"] = value
    return results


def _vga1_case(candidate: Candidate, root: Path, control_v: float) -> dict[str, float]:
    label = f"control-{control_v * 1e3:.3f}mv".replace(".", "_")
    case = root / label
    circuit = f"""
VCC vcc 0 3.3
VINN v1n 0 1.8
VDIFF v1p v1n DC 0 AC 1 SIN(0 20m 16G)
VC1 vc1 0 {2.7 + control_v / 2}
VC1B vc1b 0 {2.7 - control_v / 2}
XDUT v1p v1n vga1p vga1n vc1 vc1b vcc 0 candidate
"""
    controls = "op\nwrdata op.dat v(vga1p) v(vga1n) i(VCC)\nac dec 100 1Meg 100G\nwrdata ac.dat v(vga1p) v(vga1n)\ntran 0.5p 10n 8n\nwrdata tran.dat v(vga1p) v(vga1n)"
    run_ngspice(private_deck("VGA1 private fixture", candidate, circuit, controls), case)
    _, op = read_real_table(case / "op.dat", 3)
    frequency, ac = read_complex_table(case / "ac.dat", 2, 400)
    differential = _differential(ac[0], ac[1])
    time, transient = read_real_table(case / "tran.dat", 2, 2_000)
    transient_diff = _differential_real(transient[0], transient[1])
    gain10 = magnitude_at(frequency, differential, 10e6)
    metrics = {
        "output_common_mode_v": 0.5 * (op[0][-1] + op[1][-1]),
        "output_offset_v": abs(op[0][-1] - op[1][-1]),
        "supply_current_a": abs(op[2][-1]),
        "gain_10mhz_db": _db(gain10),
        "gain_16ghz_db": _db(magnitude_at(frequency, differential, 16e9)),
        "gain_33ghz_db": _db(magnitude_at(frequency, differential, 33e9)),
        "transient_gain_16ghz_db": _db(abs(harmonic(time, transient_diff, 16e9)) / 20e-3),
    }
    if control_v > 0.0:
        metrics["bandwidth_hz"] = upper_3db_frequency(frequency, differential, 10e6)
    return metrics


def evaluate_vga1(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for label, control in (("zero", 0.0), ("mid", 6.155e-3), ("maximum", 12.31e-3)):
        for name, value in _vga1_case(candidate, root, control).items():
            results[f"{label}_{name}"] = value
    return results


def _vga2_case(candidate: Candidate, root: Path, bw: float) -> dict[str, float]:
    label = f"bw-{bw:.1f}".replace(".", "_")
    case = root / label
    control = 49.31e-3
    circuit = f"""
VCC vcc 0 3.3
VINN v2n 0 1.8
VDIFF v2p v2n DC 0 AC 1 SIN(0 20m 16G)
VC2 vc2 0 {2.7 + control / 2}
VC2B vc2b 0 {2.7 - control / 2}
VBW bw_cntrl 0 {bw}
XDUT v2p v2n vga2p vga2n vc2 vc2b bw_cntrl vcc 0 candidate
"""
    controls = "op\nwrdata op.dat v(vga2p) v(vga2n) i(VCC)\nac dec 100 1Meg 1T\nwrdata ac.dat v(vga2p) v(vga2n)\ntran 0.5p 10n 8n\nwrdata tran.dat v(vga2p) v(vga2n)"
    run_ngspice(private_deck("VGA2 private fixture", candidate, circuit, controls), case)
    _, op = read_real_table(case / "op.dat", 3)
    frequency, ac = read_complex_table(case / "ac.dat", 2, 400)
    differential = _differential(ac[0], ac[1])
    time, transient = read_real_table(case / "tran.dat", 2, 2_000)
    transient_diff = _differential_real(transient[0], transient[1])
    gain10 = magnitude_at(frequency, differential, 10e6)
    magnitudes_db = [_db(abs(value)) for value in differential]
    peaking = max(
        value
        for f, value in zip(frequency, magnitudes_db, strict=True)
        if 10e6 <= f <= 100e9
    ) - _db(gain10)
    try:
        bandwidth_hz = upper_3db_frequency(frequency, differential, 10e6)
    except SimulationError:
        bandwidth_hz = frequency[-1]
    return {
        "output_common_mode_v": 0.5 * (op[0][-1] + op[1][-1]),
        "output_offset_v": abs(op[0][-1] - op[1][-1]),
        "supply_current_a": abs(op[2][-1]),
        "gain_10mhz_db": _db(gain10),
        "gain_16ghz_db": _db(magnitude_at(frequency, differential, 16e9)),
        "gain_33ghz_db": _db(magnitude_at(frequency, differential, 33e9)),
        "bandwidth_hz": bandwidth_hz,
        "peaking_db": peaking,
        "transient_gain_16ghz_db": _db(abs(harmonic(time, transient_diff, 16e9)) / 20e-3),
    }


def evaluate_vga2(candidate: Candidate, root: Path) -> dict[str, float]:
    results: dict[str, float] = {}
    for label, bw in (("low_control", 0.0), ("high_control", 3.3)):
        for name, value in _vga2_case(candidate, root, bw).items():
            results[f"{label}_{name}"] = value
    return results


EVALUATORS: dict[str, Callable[[Candidate, Path], dict[str, float]]] = {
    "agc_controller_tl_run_01": evaluate_agc,
    "bias_servo_tl_run_05": evaluate_bias,
    "common_mode_controller_tl_run_08": evaluate_cmc,
    "input_tia_tl_regression": evaluate_input_tia,
    "interstage_interface_tl_run_01": evaluate_interfaces,
    "mode_switch_tl_run_08": evaluate_mode,
    "output_buffer_tl_regression": evaluate_buffer,
    "peak_detector_tl_regression": evaluate_peak,
    "vga1_tl_regression": evaluate_vga1,
    "vga2_tl_regression": evaluate_vga2,
}
