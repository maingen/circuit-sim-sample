from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from linter import lint_candidate
from scoring import grade


HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
LEDGER_PATH = HERE / "target_ledger.json" if (HERE / "target_ledger.json").is_file() else PACKAGE_ROOT / "private/target_ledger.json"
ALLOWLIST_PATH = HERE / "allowlist.json" if (HERE / "allowlist.json").is_file() else PACKAGE_ROOT / "config/allowlist.json"
FIXTURE_ROOT = HERE / "fixtures" if (HERE / "fixtures").is_dir() else PACKAGE_ROOT / "private/fixtures/reference_decks"
TRUSTED_PDK_ROOT = Path("/opt/pdk") if Path("/opt/pdk/sky130_tt.inc").is_file() else PACKAGE_ROOT / "pdk"
NGSPICE = shutil.which("ngspice") or "/usr/bin/ngspice"

DECK_ARTIFACTS = {
    "tb_bias.cir": "blocks/bias.cir",
    "tb_lna_ac.cir": "blocks/lna.cir",
    "tb_mixer_tran.cir": "blocks/mixer.cir",
    "tb_cbpf_ac.cir": "blocks/cbpf.cir",
    "tb_cbpf_desired_ac.cir": "blocks/cbpf.cir",
    "tb_cbpf_image_ac.cir": "blocks/cbpf.cir",
    "tb_filter_tuning_tran.cir": "blocks/tuning.cir",
    "tb_limiter_tran.cir": "blocks/limiter.cir",
    "tb_ifbuf_limiter.cir": "blocks/limiter.cir",
    "tb_crystal_tran.cir": "blocks/crystal.cir",
    "tb_pfd_cp_tran.cir": "blocks/pfd_cp.cir",
    "tb_por_tran.cir": "blocks/por.cir",
    "tb_prescaler8_403m_tran.cir": "blocks/prescaler.cir",
    "tb_prescaler9_403m_tran.cir": "blocks/prescaler.cir",
    "tb_counter5_50m_tran.cir": "blocks/counter.cir",
    "tb_swallow3_tran.cir": "blocks/swallow.cir",
    "tb_mash_tran.cir": "blocks/mash.cir",
    "tb_qvco_tran.cir": "blocks/qvco.cir",
    "tb_qvco_tune_low.cir": "blocks/qvco.cir",
    "tb_qvco_tune_high.cir": "blocks/qvco.cir",
    "tb_synth_smoke.cir": "blocks/synth.cir",
    "tb_full_system_smoke.cir": "candidate.cir",
    "tb_end_to_end.cir": "blocks/receiver.cir",
}

METRIC_LABELS = {
    "bias_vbn_v": ("tb_bias.cir", "v(vbn)", "identity"),
    "bias_vbp_v": ("tb_bias.cir", "v(vbp)", "identity"),
    "bias_current_a": ("tb_bias.cir", "i(vdd)", "abs"),
    "lna_gain_403_db": ("tb_lna_ac.cir", "lna_gain_403_db", "identity"),
    "lna_s11_403_db": ("tb_lna_ac.cir", "lna_s11_403_db", "identity"),
    "lna_current_a": ("tb_lna_ac.cir", "i(vdd)", "abs"),
    "cbpf_gain_750_db": ("tb_cbpf_ac.cir", "cbpf_gain_750_db", "identity"),
    "cbpf_gain_100k_db": ("tb_cbpf_ac.cir", "cbpf_gain_100k_db", "identity"),
    "cbpf_gain_3m_db": ("tb_cbpf_ac.cir", "cbpf_gain_3m_db", "identity"),
    "cbpf_desired_750_db": ("tb_cbpf_desired_ac.cir", "cbpf_desired_750_db", "identity"),
    "cbpf_image_750_db": ("tb_cbpf_image_ac.cir", "cbpf_image_750_db", "identity"),
    "cbpf_current_a": ("tb_cbpf_ac.cir", "i(vdd)", "abs"),
    "tuning_frequency_hz": ("tb_filter_tuning_tran.cir", "tune_osc_hz", "identity"),
    "tuning_average_v": ("tb_filter_tuning_tran.cir", "tune_avg", "identity"),
    "limiter_vpp_v": ("tb_limiter_tran.cir", "limiter_vpp", "identity"),
    "rssi_average_v": ("tb_limiter_tran.cir", "rssi_avg", "identity"),
    "limiter_current_a": ("tb_limiter_tran.cir", "limiter_supply_i", "abs"),
    "crystal_frequency_hz": ("tb_crystal_tran.cir", "ref_freq_hz", "identity"),
    "crystal_vpp_v": ("tb_crystal_tran.cir", "ref_vpp", "identity"),
    "pfd_up_max_v": ("tb_pfd_cp_tran.cir", "up_max", "identity"),
    "pfd_dn_max_v": ("tb_pfd_cp_tran.cir", "dn_max", "identity"),
    "charge_pump_final_v": ("tb_pfd_cp_tran.cir", "vc_final", "identity"),
    "por_low_v": ("tb_por_tran.cir", "por_min", "identity"),
    "por_release_s": ("tb_por_tran.cir", "por_fall", "identity"),
    "prescaler_div8_hz": ("tb_prescaler8_403m_tran.cir", "prescaler_403m_out_hz", "identity"),
    "prescaler_div9_hz": ("tb_prescaler9_403m_tran.cir", "prescaler9_403m_out_hz", "identity"),
    "counter_50m_hz": ("tb_counter5_50m_tran.cir", "counter_50m_out_hz", "identity"),
    "swallow_hz": ("tb_swallow3_tran.cir", "swallow_out_hz", "identity"),
    "mash_density": ("tb_mash_tran.cir", "y_avg", "identity"),
    "qvco_frequency_hz": ("tb_qvco_tran.cir", "qvco_freq_hz", "identity"),
    "qvco_vpp_v": ("tb_qvco_tran.cir", "qvco_vpp", "identity"),
    "qvco_current_a": ("tb_qvco_tran.cir", "qvco_supply_i", "abs"),
    "qvco_tune_low_hz": ("tb_qvco_tune_low.cir", "tune_low_hz", "identity"),
    "qvco_tune_high_hz": ("tb_qvco_tune_high.cir", "tune_high_hz", "identity"),
    "synth_startup_lo_hz": ("tb_synth_smoke.cir", "synth_lo_hz", "identity"),
    "synth_startup_vpp_v": ("tb_synth_smoke.cir", "synth_lo_vpp", "identity"),
    "synth_startup_current_a": ("tb_synth_smoke.cir", "synth_supply_i", "abs"),
    "full_startup_lo_hz": ("tb_full_system_smoke.cir", "full_lo_hz", "identity"),
    "full_startup_lo_vpp_v": ("tb_full_system_smoke.cir", "full_lo_vpp", "identity"),
    "full_startup_rfout_vpp_v": ("tb_full_system_smoke.cir", "full_rfout_pp", "identity"),
    "full_startup_current_a": ("tb_full_system_smoke.cir", "full_vdd_i", "abs"),
}


def strip_candidate(path: Path) -> str:
    kept: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if re.match(r"(?i)^\.(include|end)\b", line):
            continue
        kept.append(raw)
    return "\n".join(kept).strip() + "\n"


def _replace_node_tokens(text: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        text = re.sub(rf"(?i)(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, text)
    return text


def sanitize_fixture(text: str, candidate: str, deck_name: str) -> str:
    output: list[str] = []
    replacements = {
        "v(XTUNE.n1)": "v(tune_n1)", "v(XTUNE.n2)": "v(tune_n2)",
        "v(XTUNE.n3)": "v(tune_n3)", "v(XTUNE.n4)": "v(tune_n4)",
        "v(XTUNE.n5)": "v(tune_n5)", "v(xosc.xin)": "v(xtal_xin)",
        "v(xosc.xout)": "v(xtal_xout)", "v(XSYN.vf)": "v(vctrl)",
        "v(xfull.xsyn.vf)": "v(vctrl)",
        "v(xfull.xftune.n1)": "v(tune_n1)", "v(xfull.xftune.n2)": "v(tune_n2)",
        "v(xfull.xftune.n3)": "v(tune_n3)", "v(xfull.xftune.n4)": "v(tune_n4)",
        "v(xfull.xftune.n5)": "v(tune_n5)",
    }
    for index, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if index == 0:
            output.extend([raw, '.include "/opt/pdk/sky130_tt.inc"', ".option seed=1 temp=27", candidate.rstrip()])
            continue
        if re.match(r"(?i)^\.include\b", line):
            continue
        if line and line[0].upper() == "X" and not line.startswith(("*", ";")):
            continue
        if re.match(r"(?i)^(wrdata|write|noise|setplot)\b", line):
            continue
        if line.casefold() == ".end":
            continue
        if "v(xrx." in line.casefold() or "v(xlim." in line.casefold():
            continue
        if re.match(r"(?i)^meas", line) and any(name in line.casefold() for name in (
            "e2e_buf_", "e2e_stage", "ifbuf_gate_", "ifbuf_s1_", "ifbuf_s5_"
        )):
            continue
        if re.match(r"(?i)^print\b", line) and "v(x" in line.casefold():
            continue
        for old, new in replacements.items():
            raw = raw.replace(old, new)
        output.append(raw)
    transformed = "\n".join(output)
    if deck_name in {"tb_qvco_tran.cir", "tb_qvco_tune_low.cir", "tb_qvco_tune_high.cir", "tb_synth_smoke.cir"}:
        transformed = _replace_node_tokens(transformed, {
            "ip": "loi_p", "in": "loi_n", "qp": "loq_p", "qn": "loq_n",
        })
    if deck_name == "tb_pfd_cp_tran.cir":
        transformed = _replace_node_tokens(transformed, {"vc": "vctrl"})
    if deck_name == "tb_limiter_tran.cir":
        transformed = _replace_node_tokens(transformed, {"inp": "iop", "inn": "ion"})
    if deck_name == "tb_ifbuf_limiter.cir":
        transformed = _replace_node_tokens(transformed, {"inp": "iop", "inn": "ion"})
    if deck_name == "tb_mixer_tran.cir":
        transformed = _replace_node_tokens(transformed, {
            "rf": "rfout", "lop": "loi_p", "lon": "loi_n", "outp": "ip", "outn": "in",
        })
        transformed = transformed.replace(
            "VLON loi_n 0 sin(0.5 0.5 403meg 0 0 180)",
            "VLON loi_n 0 sin(0.5 0.5 403meg 0 0 180)\n"
            "VLOQP loq_p 0 sin(0.5 0.5 403meg 0 0 90)\n"
            "VLOQN loq_n 0 sin(0.5 0.5 403meg 0 0 270)",
        )
    return transformed + "\n.end\n"


def parse_log(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    pattern = re.compile(r"(?im)^\s*([^\s=]+)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)")
    for label, raw in pattern.findall(path.read_text(errors="replace")):
        try:
            values[label.casefold()] = float(raw)
        except ValueError:
            pass
    return values


def run_deck(candidate_root: Path, deck_name: str, work: Path, fixture_text: str | None = None) -> tuple[dict[str, float], dict[str, Any]]:
    artifact = candidate_root / DECK_ARTIFACTS[deck_name]
    fixture = fixture_text if fixture_text is not None else (FIXTURE_ROOT / deck_name).read_text(encoding="utf-8")
    deck_path = work / deck_name
    log_path = work / f"{deck_path.stem}.log"
    deck_path.write_text(sanitize_fixture(fixture, strip_candidate(artifact), deck_name), encoding="utf-8")
    completed = subprocess.run(
        [NGSPICE, "-b", "-o", str(log_path), str(deck_path)], cwd=work,
        capture_output=True, text=True, timeout=21600, check=False,
    )
    fatal = re.search(r"fatal|error:|failed!|no such vector|can't parse|can't find", log_path.read_text(errors="replace"), re.I)
    status = {"deck": deck_name, "returncode": completed.returncode, "fatal_log_pattern": bool(fatal), "log": str(log_path)}
    return parse_log(log_path), status


def grade_submission(candidate_root: Path, logs: Path, difficulty: str) -> dict[str, Any]:
    logs.mkdir(parents=True, exist_ok=True)
    ledger = json.loads(LEDGER_PATH.read_text())
    lint = lint_candidate(candidate_root, ALLOWLIST_PATH, TRUSTED_PDK_ROOT)
    if not lint["eligible"]:
        return {"difficulty": difficulty, "artifact_evaluable": False, "production_pass": False, "eligibility_gate": lint, "measurements": {}, "criteria": [], "raw_score": 0.0, "final_reward": 0.0}

    required_decks = sorted({item[0] for item in METRIC_LABELS.values()}) + [
        "tb_mixer_tran.cir", "tb_ifbuf_limiter.cir", "tb_end_to_end.cir",
    ]
    deck_values: dict[str, dict[str, float]] = {}
    deck_status: list[dict[str, Any]] = []
    simulation_gate = True
    with tempfile.TemporaryDirectory(prefix="medradio-grade-") as temporary:
        work = Path(temporary)
        for deck in required_decks:
            try:
                values, status = run_deck(candidate_root, deck, work)
            except (OSError, subprocess.SubprocessError, TimeoutError) as error:
                values = {}
                status = {"deck": deck, "returncode": -1, "fatal_log_pattern": True, "error": str(error)}
            deck_values[deck] = values
            deck_status.append(status)
            if status["returncode"] != 0 or status["fatal_log_pattern"]:
                simulation_gate = False
        for path in work.glob("*.log"):
            shutil.copy2(path, logs / path.name)

    measurements: dict[str, float | None] = {}
    for identifier, (deck, label, transform) in METRIC_LABELS.items():
        value = deck_values.get(deck, {}).get(label.casefold())
        if value is not None and transform == "abs":
            value = abs(value)
        measurements[identifier] = value
    desired = measurements.get("cbpf_desired_750_db")
    image = measurements.get("cbpf_image_750_db")
    measurements["cbpf_irr_db"] = None if desired is None or image is None else desired - image
    phase = deck_values.get("tb_qvco_tran.cir", {}).get("qvco_phase_raw_deg")
    measurements["qvco_phase_error_deg"] = None if phase is None else abs((phase % 360.0) - 270.0)
    low = measurements.get("qvco_tune_low_hz")
    high = measurements.get("qvco_tune_high_hz")
    measurements["qvco_sensitivity_hz_per_v"] = None if low is None or high is None else abs(low - high) / 0.6

    external = deck_values.get("tb_end_to_end.cir", {})
    mixer = deck_values.get("tb_mixer_tran.cir", {})
    if_chain = deck_values.get("tb_ifbuf_limiter.cir", {})
    architecture_checks = {
        "mixer_frequency_conversion_activity": bool(mixer.get("if_vpp", 0.0) > 1e-3),
        "if_buffer_activity": bool(if_chain.get("ifbuf_vpp", 0.0) > 1e-3),
        "if_buffer_to_limiter_activity": bool(if_chain.get("ifbuf_limiter_vpp", 0.0) > 0.25),
        "external_lo_rf_to_if_activity": bool(external.get("e2e_if_vpp", 0.0) > 1e-4),
        "external_lo_limiter_activity": bool(external.get("e2e_vo_vpp", 0.0) > 0.25),
        "full_internal_lo_activity": bool((measurements.get("full_startup_lo_vpp_v") or 0.0) > 0.005),
    }
    architecture_gate = all(architecture_checks.values())
    scored = grade(measurements, ledger, difficulty)
    final = scored["score"] if simulation_gate and architecture_gate else 0.0
    result = {
        "difficulty": difficulty, "artifact_evaluable": simulation_gate,
        "production_pass": simulation_gate and architecture_gate, "eligibility_gate": lint,
        "simulation_gate": simulation_gate, "architecture_gate": architecture_gate,
        "architecture_checks": architecture_checks, "deck_status": deck_status,
        "measurements": measurements, "criteria": scored["criteria"],
        "raw_score": scored["score"], "final_reward": final,
    }
    (logs / "details.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def grade_reference(difficulty: str) -> dict[str, Any]:
    ledger = json.loads(LEDGER_PATH.read_text())
    measurement_path = LEDGER_PATH.parent / "reference_measurements.json"
    replay = json.loads(measurement_path.read_text())
    if replay["reference_run_id"] != ledger["reference_run_id"]:
        raise RuntimeError("reference measurement run does not match target ledger")
    measurements = replay["measurements"]
    result = grade(measurements, ledger, difficulty)
    result["reference_run_id"] = ledger["reference_run_id"]
    return result
