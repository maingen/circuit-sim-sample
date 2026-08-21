from __future__ import annotations

import cmath
import math
import re
from pathlib import Path
from typing import Callable

def extract_measurements(run_root: Path) -> tuple[dict[str, float], list[dict[str, str]]]:
    logs = run_root / "logs"
    raw = run_root / "raw"
    output: dict[str, float] = {}
    errors: list[dict[str, str]] = []

    def measure(log_name: str, key: str) -> float:
        text = (logs / log_name).read_text(errors="replace")
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([+\-0-9.eE]+)", text)
        if not match:
            raise RuntimeError(f"missing {key} in {log_name}")
        return float(match.group(1))

    def load(name: str) -> list[list[float]]:
        rows = []
        for line in (raw / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append([float(token) for token in line.split()])
        if not rows:
            raise RuntimeError(f"empty data file: {name}")
        return rows

    def tone_amplitude(t: list[float], x: list[float], frequency: float) -> float:
        if len(t) != len(x) or len(t) < 2:
            raise ValueError("tone extraction needs at least two aligned samples")
        average = sum(x) / len(x)
        previous = (x[0] - average) * cmath.exp(-2j * math.pi * frequency * t[0])
        integral = 0j
        for index in range(1, len(t)):
            current = (x[index] - average) * cmath.exp(-2j * math.pi * frequency * t[index])
            integral += 0.5 * (previous + current) * (t[index] - t[index - 1])
            previous = current
        return float(2 * abs(integral) / (t[-1] - t[0]))

    def nearest_index(data: list[list[float]], column: int, target: float) -> int:
        return min(range(len(data)), key=lambda index: abs(data[index][column] - target))

    def db20(value: float) -> float:
        return 20 * math.log10(max(abs(value), 1e-30))

    def dbm(watts: float) -> float:
        return 10 * math.log10(max(watts, 1e-30) / 1e-3)

    def group(name: str, function: Callable[[], dict[str, float]]) -> None:
        try:
            values = function()
            for key, value in values.items():
                if not math.isfinite(float(value)):
                    raise ValueError(f"non-finite {key}")
            output.update(values)
        except Exception as exc:
            errors.append({"group": name, "error": str(exc)})

    def controls() -> dict[str, float]:
        return {
            f"control_{key}": measure("bias_control_tb.log", key)
            for key in ("vdac_code0", "vdac_code1", "vdac_code3", "vdac_code7", "drive_enabled", "drive_limited", "env_avg")
        }

    group("bias_and_control", controls)

    def pfd() -> dict[str, float]:
        values = {}
        for direction, log_name in [("up", "pfd_charge_pump_tb.log"), ("down", "pfd_charge_pump_down_tb.log")]:
            values[f"pfd_{direction}_up_avg"] = measure(log_name, "up_avg")
            values[f"pfd_{direction}_dn_avg"] = measure(log_name, "dn_avg")
            values[f"pfd_{direction}_vctrl_delta"] = measure(log_name, "vctrl_stop") - measure(log_name, "vctrl_start")
        return values

    group("pfd_charge_pump", pfd)
    group(
        "divider_chain_64",
        lambda: {f"divider_{key}": measure("divider_3040m_tb.log", key) for key in ("q2_period", "q4_period", "q64_period")},
    )

    def filter_metrics() -> dict[str, float]:
        data = load("filters_ac.dat")
        return {
            identifier: float(data[max(range(len(data)), key=lambda index: data[index][column])][1])
            for identifier, column in [
                ("tx_if_saw1_center_hz", 4), ("tx_if_saw2_center_hz", 6), ("rx_if1_center_hz", 8),
                ("rx_if2_center_hz", 10), ("tx_rf_center_hz", 12), ("rx_rf_center_hz", 14),
            ]
        }

    group("filters", filter_metrics)

    def vga_metrics() -> dict[str, float]:
        data = load("if_vga_ac.dat")
        return {
            f"if_vga_gain_{int(target / 1e6)}mhz_db": float(data[nearest_index(data, 1, target)][4])
            for target in (10e6, 475e6)
        }

    group("if_vga", vga_metrics)

    def lna_metrics() -> dict[str, float]:
        data = load("rx_lna_ac.dat")
        index = nearest_index(data, 1, 3.415e9)
        noise = load("rx_lna_noise.dat")
        noise_index = nearest_index(noise, 1, 3.415e9)
        k = 1.380649e-23
        nf_db = 10 * math.log10(noise[noise_index][5] ** 2 / (4 * k * 300 * 50))
        return {"lna_gain_db": float(data[index][4]), "lna_noise_figure_db": nf_db}

    group("rx_lna", lna_metrics)

    for identifier, filename, log_name, fout, input_peak, window in [
        ("tx_mix1", "tx_mixer_10m_to_475m_tran.dat", "tx_mixer_10m_to_475m_tb.log", 475e6, 0.010, 20e-9),
        ("tx_mix2", "tx_mixer_475m_to_rf_tran.dat", "tx_mixer_475m_to_rf_tb.log", 3.515e9, 0.010, 20e-9),
        ("rx_mix1", "rx_mixer_rf_to_if1_tran.dat", "rx_mixer_rf_to_if1_tb.log", 475e6, 0.002, 20e-9),
        ("rx_mix2", "rx_mixer_if1_to_10m_tran.dat", "rx_mixer_if1_to_10m_tb.log", 10e6, 0.010, 200e-9),
    ]:
        def mixer_metrics(
            identifier: str = identifier,
            filename: str = filename,
            log_name: str = log_name,
            fout: float = fout,
            input_peak: float = input_peak,
            window: float = window,
        ) -> dict[str, float]:
            data = load(filename)
            selected = [row for row in data if row[0] >= data[-1][0] - max(window, 2 / fout)]
            amplitude = tone_amplitude([row[0] for row in selected], [row[3] for row in selected], fout)
            return {
                f"{identifier}_conversion_gain_db": db20(amplitude / input_peak),
                f"{identifier}_supply_current_a": measure(log_name, "idd_avg"),
            }

        group(identifier, mixer_metrics)

    for identifier, log_name in [("vco_if", "vco_465m_tb.log"), ("vco_tx", "vco_3040m_tb.log"), ("vco_rx", "vco_2940m_tb.log")]:
        group(
            identifier,
            lambda identifier=identifier, log_name=log_name: {
                f"{identifier}_frequency_hz": 1 / measure(log_name, "vco_period"),
                f"{identifier}_vpp_v": measure(log_name, "vco_pp"),
            },
        )

    group(
        "vco_tx_tuning",
        lambda: {
            "vco_tx_tuning_delta_hz": 1 / measure("vco_3040m_tuning_tb.log", "period_vctrl_130")
            - 1 / measure("vco_3040m_tuning_tb.log", "period_vctrl_070")
        },
    )

    def lo_metrics() -> dict[str, float]:
        values = {}
        for prefix in ("tx", "rx", "if"):
            values[f"lo_buffer_{prefix}_frequency_hz"] = 1 / measure("lo_distribution_tb.log", f"{prefix}_period")
            values[f"lo_buffer_{prefix}_vpp_v"] = measure("lo_distribution_tb.log", f"{prefix}buf_pp")
        return values

    group("lo_distribution", lo_metrics)

    for prefix, log_name, qkey in [
        ("tx", "pll_synth_tx_tb.log", "q64_period"),
        ("rx", "pll_synth_rx_tb.log", "q64_period"),
        ("if", "pll_synth_if_tb.log", "q32_period"),
    ]:
        group(
            f"pll_{prefix}",
            lambda prefix=prefix, log_name=log_name, qkey=qkey: {
                f"pll_{prefix}_lo_frequency_hz": 1 / measure(log_name, "lo_period"),
                f"pll_{prefix}_feedback_period_s": measure(log_name, qkey),
                f"pll_{prefix}_control_v": measure(log_name, "vctrl_late"),
                f"pll_{prefix}_lo_vpp_v": measure(log_name, "lo_pp"),
            },
        )

    group(
        "tx_driver",
        lambda: {
            "tx_driver_gain_db": db20(measure("tx_driver_tb.log", "vout_pp") / measure("tx_driver_tb.log", "vin_pp")),
            "tx_driver_current_a": measure("tx_driver_tb.log", "idd_avg"),
        },
    )

    def pa_metrics() -> dict[str, float]:
        power = measure("tx_pa_tb.log", "pout_w")
        dc = measure("tx_pa_tb.log", "pdc_w")
        data = load("tx_pa_twotone_tran.dat")
        selected = [row for row in data if row[0] >= 200e-9]
        time = [row[0] for row in selected]
        output_voltage = [row[5] for row in selected]
        fundamental = min(tone_amplitude(time, output_voltage, 3.5115e9), tone_amplitude(time, output_voltage, 3.5185e9))
        imd = max(tone_amplitude(time, output_voltage, 3.5045e9), tone_amplitude(time, output_voltage, 3.5255e9))
        return {
            "pa_output_power_dbm": dbm(power),
            "pa_dc_power_w": dc,
            "pa_efficiency_ratio": power / dc,
            "pa_extended_drain_max_v": measure("tx_pa_tb.log", "drain_max"),
            "pa_thin_oxide_drain_max_v": measure("tx_pa_tb.log", "driver_drain_max"),
            "pa_imd3_dbc": db20(imd / fundamental),
            "pa_imd3_spur_dbm": dbm(imd * imd / (2 * 50)),
        }

    group("tx_pa", pa_metrics)

    group(
        "wimax_tx_core",
        lambda: {
            "tx_core_output_power_dbm": dbm(measure("wimax_tx_core_tb.log", "pout_w")),
            "tx_core_output_vpp_v": measure("wimax_tx_core_tb.log", "vout_pp"),
            "tx_core_pa_drain_max_v": measure("wimax_tx_core_tb.log", "pa_drain_max"),
        },
    )

    def rx_metrics() -> dict[str, float]:
        data = load("wimax_rx_core_tran.dat")
        selected = [row for row in data if row[0] >= 200e-9]
        time = [row[0] for row in selected]
        output_voltage = [row[-1] for row in selected]
        rx10 = tone_amplitude(time, output_voltage, 10e6)
        rx940 = tone_amplitude(time, output_voltage, 940e6)
        return {
            "rx_core_10mhz_peak_v": rx10,
            "rx_core_conversion_gain_db": db20(rx10 / 1e-3),
            "rx_core_sum_rejection_db": db20(rx10 / rx940),
        }

    group("wimax_rx_core", rx_metrics)

    def system_metrics() -> dict[str, float]:
        values = {
            "system_antenna_power_dbm": dbm(measure("wimax_transceiver_tb.log", "antenna_power")),
            "system_rx_rms_v": measure("wimax_transceiver_tb.log", "rxout_rms"),
            "system_pa_drain_max_v": measure("wimax_transceiver_tb.log", "pa_drain_max"),
        }
        for prefix, period_key, feedback_key in [
            ("tx", "tx_lo_period", "tx_q64_period"),
            ("rx", "rx_lo_period", "rx_q64_period"),
            ("if", "if_lo_period", "if_q32_period"),
        ]:
            values[f"system_{prefix}_lo_frequency_hz"] = 1 / measure("wimax_transceiver_tb.log", period_key)
            values[f"system_{prefix}_feedback_period_s"] = measure("wimax_transceiver_tb.log", feedback_key)
            values[f"system_{prefix}_settling_delta_mv"] = abs(
                measure("wimax_transceiver_tb.log", f"{prefix}_vctrl_800")
                - measure("wimax_transceiver_tb.log", f"{prefix}_vctrl_600")
            ) * 1e3
        return values

    group("wimax_transceiver", system_metrics)
    return output, errors
