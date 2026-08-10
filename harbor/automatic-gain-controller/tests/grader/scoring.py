from __future__ import annotations

import math
from collections.abc import Iterable


BLOCKED_TASKS: dict[str, str] = {}


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def central(value: float, target: float, full_tolerance: float) -> float:
    if not _finite(value):
        return 0.0
    error = abs(value - target)
    if error <= full_tolerance:
        return 1.0
    zero_error = 4.0 * full_tolerance
    if error >= zero_error:
        return 0.0
    return (zero_error - error) / (zero_error - full_tolerance)


def upper(value: float, limit: float, falloff: float | None = None) -> float:
    if not _finite(value):
        return 0.0
    if value <= limit:
        return 1.0
    width = falloff if falloff is not None else max(abs(limit), 1e-12)
    return max(0.0, 1.0 - (value - limit) / width)


def lower(value: float, limit: float, falloff: float | None = None) -> float:
    if not _finite(value):
        return 0.0
    if value >= limit:
        return 1.0
    width = falloff if falloff is not None else max(abs(limit), 1e-12)
    return max(0.0, 1.0 - (limit - value) / width)


def interval(value: float, low: float, high: float, falloff: float | None = None) -> float:
    if not _finite(value):
        return 0.0
    if low <= value <= high:
        return 1.0
    width = falloff if falloff is not None else max(high - low, 1e-12)
    distance = low - value if value < low else value - high
    return max(0.0, 1.0 - distance / width)


def relation(condition: bool) -> float:
    return 1.0 if condition else 0.0


def worst(values: Iterable[float]) -> float:
    materialized = list(values)
    return max(materialized) if materialized else math.inf


def score_agc(m: dict[str, float]) -> dict[str, float]:
    agc_values = [value for key, value in m.items() if "_agc_" in key and key.endswith("_v")]
    return {
        "AGC-R01-closed-loop-gain": central(m["pkd_closed_loop_gain_v_per_v"], 13.973269666666662, 0.279466),
        "AGC-R02-pkd-20mv": min(
            central(m[f"oa_{oa}_pkd_20mv_v"], 1.07975283, 0.02699375)
            for oa in ("1_2", "1_4")
        ),
        "AGC-R03-pkd-50mv": min(
            central(m[f"oa_{oa}_pkd_50mv_v"], 1.49895092, 0.03747375)
            for oa in ("1_2", "1_4")
        ),
        "AGC-R04-agc-20mv": min(
            central(m[f"oa_{oa}_agc_20mv_v"], 1.3988833956, 0.025)
            for oa in ("1_2", "1_4")
        ),
        "AGC-R05-agc-50mv": min(
            central(m[f"oa_{oa}_agc_50mv_v"], 1.2015161425, 0.025)
            for oa in ("1_2", "1_4")
        ),
        "AGC-R06-command-range": min(interval(value, 1.2, 1.4, 0.2) for value in agc_values),
        "AGC-R07-required-polarity": relation(
            m["oa_1_2_pkd_50mv_v"] > m["oa_1_2_pkd_20mv_v"]
            and m["oa_1_2_agc_50mv_v"] < m["oa_1_2_agc_20mv_v"]
        ),
        "AGC-R08-settling": upper(
            worst(value for key, value in m.items() if "settling" in key), 5e-6, 5e-6
        ),
    }


def score_bias(m: dict[str, float]) -> dict[str, float]:
    equal_inputs = [value for key, value in m.items() if (key.startswith("inp_equal") or key.startswith("inn_equal"))]
    mismatch_inputs = [value for key, value in m.items() if (key.startswith("inp_mismatch") or key.startswith("inn_mismatch"))]
    vtia = [value for key, value in m.items() if key.startswith("vtia_equal")]
    mismatch_error = max(
        abs(m[f"inp_mismatch_{corner}_v"] - m[f"inn_mismatch_{corner}_v"])
        for corner in ("3_0", "3_3", "3_6")
    )
    return {
        "BIAS-R01-vtia": min(central(value, 2.05, 20.5e-3) for value in vtia),
        "BIAS-R02-equal-input-voltage": min(central(value, 0.78, 20e-3) for value in equal_inputs),
        "BIAS-R03-mismatch-input-maximum": upper(max(mismatch_inputs), 0.9, 0.1),
        "BIAS-R04-input-mismatch": upper(mismatch_error, 20e-3, 20e-3),
        "BIAS-R06-line-regulation": upper(max(vtia) - min(vtia), 20.5e-3, 20.5e-3),
        "BIAS-R07-startup-settling": upper(
            max(m["startup_settling_equal_s"], m["startup_settling_mismatch_s"]), 5e-3, 5e-3
        ),
        "BIAS-R08-current-step-settling": upper(
            max(m["current_step_settling_equal_s"], m["current_step_settling_mismatch_s"]),
            5e-3,
            5e-3,
        ),
        "BIAS-R09-input-ripple": upper(
            max(
                m[f"{node}_ripple_{corner}_vpp"]
                for node in ("inp", "inn")
                for corner in ("equal", "mismatch")
            ),
            20e-3,
            20e-3,
        ),
    }


def score_cmc(m: dict[str, float]) -> dict[str, float]:
    cm1 = [value for key, value in m.items() if key.startswith("vc1_cm_")]
    cm2 = [value for key, value in m.items() if key.startswith("vc2_cm_")]
    load1 = abs(m["vc1_diff_loaded_1_4_v"] / m["vc1_diff_unloaded_1_4_v"] - 1.0)
    load2 = abs(m["vc2_diff_loaded_1_4_v"] / m["vc2_diff_unloaded_1_4_v"] - 1.0)
    monotonic1 = m["vc1_diff_unloaded_1_2_v"] <= m["vc1_diff_unloaded_1_3_v"] <= m["vc1_diff_unloaded_1_4_v"]
    monotonic2 = m["vc2_diff_unloaded_1_2_v"] <= m["vc2_diff_unloaded_1_3_v"] <= m["vc2_diff_unloaded_1_4_v"]
    return {
        "CMC-R01-vga1-control": central(m["vc1_diff_unloaded_1_4_v"], 12.31e-3, 0.02 * 12.31e-3),
        "CMC-R02-vga2-control": central(m["vc2_diff_unloaded_1_4_v"], 49.31e-3, 0.02 * 49.31e-3),
        "CMC-R03-vga1-common-mode": min(interval(value, 2.68, 2.72, 0.04) for value in cm1),
        "CMC-R04-vga2-common-mode": min(interval(value, 2.68, 2.72, 0.04) for value in cm2),
        "CMC-R05-load-sensitivity": upper(max(load1, load2), 0.02, 0.02),
        "CMC-R06-monotonicity": relation(monotonic1 and monotonic2),
        "CMC-R08-settling": upper(max(m["vc1_settling_s"], m["vc2_settling_s"]), 1e-6, 1e-6),
        "CMC-R09-supply-current": upper(m["supply_current_loaded_1_4_a"], 5e-3, 5e-3),
    }


def score_tia(m: dict[str, float]) -> dict[str, float]:
    loss = _db_ratio(
        m["transimpedance_10mhz_ohm"], m["minimum_transimpedance_10mhz_to_33ghz_ohm"]
    )
    consistency = abs(m["transient_transimpedance_16ghz_ohm"] / m["transimpedance_16ghz_ohm"] - 1.0)
    return {
        "TIA-R01-transimpedance": central(m["transimpedance_10mhz_ohm"], 249.0, 2.49),
        "TIA-R02-input-bias": min(central(m["inp_dc_v"], 0.78, 20e-3), central(m["inn_dc_v"], 0.78, 20e-3)),
        "TIA-R03-input-maximum": upper(max(m["inp_dc_v"], m["inn_dc_v"]), 0.9, 0.1),
        "TIA-R04-output-common-mode": central(m["output_common_mode_v"], 1.57, 0.1),
        "TIA-R05-output-offset": upper(m["output_offset_v"], 20e-3, 20e-3),
        "TIA-R06-33ghz-loss": upper(loss, 1.0, 1.0),
        "TIA-R07-bandwidth": lower(m["bandwidth_hz"], 33e9, 33e9),
        "TIA-R10-transient-consistency": upper(consistency, 0.02, 0.02),
    }


def score_interfaces(m: dict[str, float]) -> dict[str, float]:
    targets = (-1.878, -10.67, -0.0393)
    tolerances = (0.20, 0.20, 0.10)
    scores: dict[str, float] = {}
    for index, (target, tolerance) in enumerate(zip(targets, tolerances, strict=True), 1):
        gain10 = m[f"path_{index}_gain_10mhz_db"]
        scores[f"IF-R01-path-{index}-gain"] = central(gain10, target, tolerance)
        scores[f"IF-R02-path-{index}-flatness"] = upper(
            m[f"path_{index}_maximum_deviation_10mhz_to_33ghz_db"], 0.10, 0.10
        )
        scores[f"IF-R03-path-{index}-common-mode"] = central(
            m[f"path_{index}_output_common_mode_v"], 1.8, 0.1
        )
        scores[f"IF-R07-path-{index}-transient-consistency"] = upper(
            abs(m[f"path_{index}_transient_gain_16ghz_db"] - m[f"path_{index}_gain_16ghz_db"]),
            0.10,
            0.10,
        )
    return scores


def score_mode(m: dict[str, float]) -> dict[str, float]:
    return {
        "MODE-R01-manual-selection": upper(m["manual_error_v"], 1e-3, 1e-3),
        "MODE-R02-automatic-selection": upper(m["automatic_error_v"], 1e-3, 1e-3),
        "MODE-R04-settling": upper(max(m["automatic_settling_s"], m["manual_settling_s"]), 100e-9, 100e-9),
        "MODE-R05-output-rails": min(interval(m["gc_min_v"], 0.0, 3.3, 3.3), interval(m["gc_max_v"], 0.0, 3.3, 3.3)),
        "MODE-R06-inactive-source-current": upper(max(m["inactive_mgc_current_a"], m["inactive_agc_current_a"]), 1e-6, 1e-6),
    }


def score_buffer(m: dict[str, float]) -> dict[str, float]:
    asymmetry = abs(abs(m["maximum_final_max_v"]) - abs(m["maximum_final_min_v"])) / max(
        abs(m["maximum_final_max_v"]), abs(m["maximum_final_min_v"])
    )
    return {
        "BUF-R01-branch-current": min(
            central(m["linearity_positive_branch_current_a"], 12e-3, 0.6e-3),
            central(m["linearity_negative_branch_current_a"], 12e-3, 0.6e-3),
        ),
        "BUF-R02-branch-current-mismatch": upper(
            abs(
                m["linearity_positive_branch_current_a"]
                - m["linearity_negative_branch_current_a"]
            )
            / max(
                m["linearity_positive_branch_current_a"],
                m["linearity_negative_branch_current_a"],
            ),
            0.05,
            0.05,
        ),
        "BUF-R03-transient-gain": central(m["linearity_collector_gain_db"], 3.6070053406659444, 0.20),
        "BUF-R04-output-common-mode": central(m["linearity_output_common_mode_v"], 2.7, 0.15),
        "BUF-R05-linearity-swing": central(m["linearity_final_swing_vpp"], 0.6, 0.06),
        "BUF-R06-thd": upper(m["linearity_final_thd_ratio"], 0.01, 0.01),
        "BUF-R07-maximum-swing": lower(m["maximum_final_swing_vpp"], 0.9, 0.9),
        "BUF-R08-clipping-symmetry": upper(asymmetry, 0.05, 0.05),
    }


def score_peak(m: dict[str, float]) -> dict[str, float]:
    targets = {
        "50mv": (0.010359402976050916, 0.010),
        "200mv": (0.09517307843744766, 0.10 * 0.09517307843744766),
        "400mv": (0.16312670889633227, 0.10 * 0.16312670889633227),
        "550mv": (0.17830322011053426, 0.05 * 0.17830322011053426),
    }
    scores = {
        f"PKD-R01-{label}": central(m[f"{label}_detector_output_v"], target, tolerance)
        for label, (target, tolerance) in targets.items()
    }
    outputs = [m[f"{label}_detector_output_v"] for label in ("50mv", "200mv", "400mv", "550mv")]
    scores["PKD-R02-monotonicity"] = relation(
        all(outputs[index] > outputs[index - 1] for index in range(1, len(outputs)))
    )
    scores["PKD-R03-loading"] = upper(m["550mv_loading_fraction"], 0.01, 0.01)
    return scores


def score_vga1(m: dict[str, float]) -> dict[str, float]:
    gains = [m[f"{state}_gain_10mhz_db"] for state in ("zero", "mid", "maximum")]
    consistency = abs(m["maximum_transient_gain_16ghz_db"] - m["maximum_gain_16ghz_db"])
    return {
        "VGA1-R02-output-common-mode": central(m["maximum_output_common_mode_v"], 2.2, 0.1),
        "VGA1-R03-gain": central(m["maximum_gain_10mhz_db"], 7.5, 0.15),
        "VGA1-R04-33ghz-loss": upper(
            max(0.0, m["maximum_gain_10mhz_db"] - m["maximum_gain_33ghz_db"]), 1.0, 1.0
        ),
        "VGA1-R05-bandwidth": lower(m["maximum_bandwidth_hz"], 33e9, 33e9),
        "VGA1-R06-offset": upper(
            max(m[f"{state}_output_offset_v"] for state in ("zero", "mid", "maximum")),
            1e-3,
            1e-3,
        ),
        "VGA1-R07-monotonicity": relation(gains[0] <= gains[1] <= gains[2]),
        "VGA1-R09-transient-consistency": upper(consistency, 0.10, 0.10),
    }


def score_vga2(m: dict[str, float]) -> dict[str, float]:
    high_is_max = m["high_control_bandwidth_hz"] > m["low_control_bandwidth_hz"]
    prefix = "high_control" if high_is_max else "low_control"
    gain_change = abs(m["high_control_gain_10mhz_db"] - m["low_control_gain_10mhz_db"])
    consistency = max(
        abs(m[f"{state}_transient_gain_16ghz_db"] - m[f"{state}_gain_16ghz_db"])
        for state in ("low_control", "high_control")
    )
    return {
        "VGA2-R02-output-common-mode": central(m[f"{prefix}_output_common_mode_v"], 2.064, 0.1),
        "VGA2-R03-gain": central(m[f"{prefix}_gain_10mhz_db"], 10.5, 0.15),
        "VGA2-R04-33ghz-loss": upper(
            abs(m[f"{prefix}_gain_10mhz_db"] - m[f"{prefix}_gain_33ghz_db"]), 1.0, 1.0
        ),
        "VGA2-R05-bandwidth": lower(m[f"{prefix}_bandwidth_hz"], 33e9, 33e9),
        "VGA2-R06-low-frequency-invariance": upper(gain_change, 0.2, 0.2),
        "VGA2-R08-bandwidth-control": relation(high_is_max),
        "VGA2-R09-peaking-low": interval(m["low_control_peaking_db"], 0.0, 2.5, 2.5),
        "VGA2-R09-peaking-high": interval(m["high_control_peaking_db"], 0.0, 2.5, 2.5),
        "VGA2-R10-offset": upper(max(m["low_control_output_offset_v"], m["high_control_output_offset_v"]), 1e-3, 1e-3),
        "VGA2-R12-transient-consistency": upper(consistency, 0.10, 0.10),
    }


def _db_ratio(numerator: float, denominator: float) -> float:
    if numerator <= 0.0 or denominator <= 0.0:
        return math.inf
    return 20.0 * math.log10(numerator / denominator)


SCORERS = {
    "agc_controller_tl_run_01": score_agc,
    "bias_servo_tl_run_05": score_bias,
    "common_mode_controller_tl_run_08": score_cmc,
    "input_tia_tl_regression": score_tia,
    "interstage_interface_tl_run_01": score_interfaces,
    "mode_switch_tl_run_08": score_mode,
    "output_buffer_tl_regression": score_buffer,
    "peak_detector_tl_regression": score_peak,
    "vga1_tl_regression": score_vga1,
    "vga2_tl_regression": score_vga2,
}
