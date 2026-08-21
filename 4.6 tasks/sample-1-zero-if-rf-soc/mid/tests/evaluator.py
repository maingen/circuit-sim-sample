#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIXTURE_DIR = Path(os.environ.get("BENCH_FIXTURES", HERE / "fixtures"))
LEDGER_PATH = Path(os.environ.get("BENCH_LEDGER", HERE / "target-ledger.json"))
ARCHITECTURE_PATH = Path(os.environ.get("BENCH_ARCHITECTURE", HERE / "architecture-map.json"))
ALLOWLIST_PATH = Path(os.environ.get("BENCH_ALLOWLIST", HERE / "sky130-allowlist.json"))
PDK_DIR = Path(os.environ.get("SKY130_PDK_BUNDLE", "/pdk"))
PDK_ENTRY = PDK_DIR / "sky130_tt.inc"
MAX_CANDIDATE_BYTES = 10_000_000
ALLOWED_WRAPPERS = {
    "sky130_fd_pr__nfet_01v8",
    "sky130_fd_pr__pfet_01v8",
}
ALLOWED_PREFIXES = {"R", "L", "C", "M", "Q", "X"}
FORBIDDEN_DIRECTIVES = {
    ".include", ".inc", ".lib", ".model", ".control", ".endc", ".ac",
    ".dc", ".tran", ".noise", ".pz", ".tf", ".four", ".measure", ".meas",
    ".save", ".probe", ".plot", ".print", ".ic", ".nodeset", ".func", ".csparam",
    ".if", ".elseif", ".else", ".endif", ".alter", ".option", ".options",
}
BANDS = {
    "mid": (0.25, 0.50),
    "hard": (0.05, 0.25),
    "harder": (0.01, 0.10),
}
SUFFIXES = {
    "t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3,
    "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15,
}


class CandidateError(ValueError):
    pass


class SimulationError(RuntimeError):
    pass


def round9(value: float) -> float:
    return float(format(float(value), ".9g"))


def spice_number(text: str) -> float:
    match = re.fullmatch(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)([A-Za-z]+)?",
        text.strip().rstrip(","),
        re.I,
    )
    if not match:
        raise ValueError(f"invalid SPICE number {text!r}")
    value = float(match.group(1))
    suffix = (match.group(2) or "").casefold()
    if not suffix:
        return value
    if suffix.startswith("meg"):
        return value * 1e6
    if suffix[0] not in SUFFIXES:
        raise ValueError(f"unsupported SPICE suffix {text!r}")
    return value * SUFFIXES[suffix[0]]


def logical_lines(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        if raw.lstrip().startswith("+"):
            if not result:
                raise CandidateError(f"line {number}: orphan continuation")
            first, prior = result[-1]
            result[-1] = (first, prior + " " + raw.lstrip()[1:].strip())
        else:
            result.append((number, raw.rstrip()))
    return result


def x_call(tokens: list[str]) -> tuple[list[str], str, list[str]]:
    positional: list[str] = []
    parameters: list[str] = []
    parameter_mode = False
    for token in tokens[1:]:
        if token.casefold() == "params:" or "=" in token:
            parameter_mode = True
        (parameters if parameter_mode else positional).append(token)
    if len(positional) < 2:
        raise CandidateError("malformed X instance")
    return positional[:-1], positional[-1].casefold(), parameters


def parse_candidate(path: Path, architecture: dict) -> tuple[str, dict]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CandidateError(f"candidate unavailable: {exc}") from exc
    if not raw or len(raw) > MAX_CANDIDATE_BYTES:
        raise CandidateError("candidate is empty or exceeds 10,000,000 bytes")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateError("candidate must be UTF-8 text") from exc
    if "reference-flat" in source.casefold() or "target-ledger" in source.casefold():
        raise CandidateError("candidate contains a forbidden private-artifact marker")

    allowlist = json.loads(ALLOWLIST_PATH.read_text())
    allowed_wrappers = set(allowlist["allowed_transistor_wrappers"])
    allowed_direct_models = set(allowlist["allowed_direct_models"])
    required = {
        row["name"].casefold(): tuple(port.casefold() for port in row["ports"])
        for row in architecture["required_subcircuits"]
    }
    definitions: dict[str, dict] = {}
    current: dict | None = None
    kept: list[str] = []
    final_end_seen = False
    for number, raw_line in logical_lines(source):
        line = raw_line.strip()
        if not line or line.startswith(("*", ";")):
            kept.append(raw_line)
            continue
        token = line.split()[0]
        lower = token.casefold()
        start = re.match(r"(?i)^\.subckt\s+(\S+)(?:\s+(.*))?$", line)
        if start:
            if current is not None:
                raise CandidateError(f"line {number}: nested .subckt")
            name = start.group(1).casefold()
            ports = tuple((start.group(2) or "").casefold().split())
            if name not in required:
                raise CandidateError(f"line {number}: unapproved subcircuit {name}")
            if name in definitions:
                raise CandidateError(f"line {number}: duplicate subcircuit {name}")
            if ports != required[name]:
                raise CandidateError(f"line {number}: port contract mismatch for {name}")
            current = {
                "name": name,
                "ports": ports,
                "devices": 0,
                "counts": {},
                "instances": set(),
                "touched_ports": set(),
            }
            definitions[name] = current
            kept.append(raw_line)
            continue
        if re.match(r"(?i)^\.ends(?:\s+(\S+))?$", line):
            if current is None:
                raise CandidateError(f"line {number}: orphan .ends")
            named = re.match(r"(?i)^\.ends(?:\s+(\S+))?$", line).group(1)
            if named and named.casefold() != current["name"]:
                raise CandidateError(f"line {number}: .ends name mismatch")
            current = None
            kept.append(raw_line)
            continue
        if lower == ".end":
            if current is not None:
                raise CandidateError(f"line {number}: .end inside subcircuit")
            final_end_seen = True
            continue
        if token.startswith("."):
            directive = lower.split("(", 1)[0]
            if directive in FORBIDDEN_DIRECTIVES or directive not in {".subckt", ".ends", ".end"}:
                raise CandidateError(f"line {number}: forbidden directive {token}")
        if current is None:
            raise CandidateError(f"line {number}: circuit element outside a subcircuit")
        prefix = token[0].upper()
        if prefix not in ALLOWED_PREFIXES:
            raise CandidateError(f"line {number}: forbidden DUT element {token}")
        instance_key = token.casefold()
        if instance_key in current["instances"]:
            raise CandidateError(f"line {number}: duplicate instance {token} in {current['name']}")
        current["instances"].add(instance_key)
        current["devices"] += 1
        current["counts"][prefix] = current["counts"].get(prefix, 0) + 1
        tokens = line.split()
        nodes: list[str]
        if prefix == "X":
            nodes, called, parameters = x_call(tokens)
            if called not in allowed_wrappers:
                raise CandidateError(
                    f"line {number}: X instance resolves to forbidden or user-defined {called}"
                )
            if len(nodes) != 4:
                raise CandidateError(f"line {number}: SKY130 transistor wrapper needs four terminals")
            allowed_parameters = {
                "l", "w", "nf", "ad", "as", "pd", "ps", "nrd", "nrs", "sa", "sb", "sd",
            }
            for parameter in parameters:
                if parameter.casefold() == "params:":
                    continue
                if "=" not in parameter or parameter.split("=", 1)[0].casefold() not in allowed_parameters:
                    raise CandidateError(f"line {number}: unapproved wrapper parameter {parameter}")
        elif prefix in {"R", "L", "C"}:
            if len(tokens) < 4:
                raise CandidateError(f"line {number}: malformed {prefix} element")
            nodes = tokens[1:3]
            try:
                value = spice_number(tokens[3].strip("{}"))
            except ValueError as exc:
                raise CandidateError(f"line {number}: passive value must be numeric") from exc
            if not math.isfinite(value) or value <= 0:
                raise CandidateError(f"line {number}: passive value must be positive and finite")
        elif prefix == "M":
            if len(tokens) < 6:
                raise CandidateError(f"line {number}: malformed MOSFET")
            nodes = tokens[1:5]
            model = tokens[5].casefold()
            if model not in allowed_direct_models:
                raise CandidateError(f"line {number}: unapproved direct MOS model {model}")
        else:
            nodes = tokens[1:5]
            candidates = [item.casefold() for item in tokens[4:6]]
            if not any(item in allowed_direct_models for item in candidates):
                raise CandidateError(f"line {number}: unapproved BJT model")
        current["touched_ports"].update(node.casefold() for node in nodes if node.casefold() in current["ports"])
        kept.append(raw_line)
    if current is not None:
        raise CandidateError(f"unterminated .subckt {current['name']}")
    if set(definitions) != set(required):
        missing = sorted(set(required) - set(definitions))
        raise CandidateError(f"missing required subcircuits: {', '.join(missing)}")
    if not final_end_seen:
        raise CandidateError("candidate must end with .end")

    structural_failures: list[str] = []
    reference_rows = {row["name"].casefold(): row for row in architecture["required_subcircuits"]}
    for name, definition in definitions.items():
        reference_count = int(reference_rows[name]["flat_device_total"])
        minimum = max(1, math.ceil(reference_count * 0.05))
        if name == "zero_if_rf_soc":
            minimum = 700
        if definition["devices"] < minimum:
            structural_failures.append(
                f"{name}: {definition['devices']} physical devices, minimum completeness floor {minimum}"
            )
        required_touched = set(reference_rows[name].get("reference_touched_ports", definition["ports"]))
        untouched = required_touched - definition["touched_ports"]
        if untouched:
            structural_failures.append(f"{name}: untouched ports {', '.join(sorted(untouched))}")
    top = definitions["zero_if_rf_soc"]
    for prefix, minimum in {"R": 20, "C": 20, "L": 4, "X": 500}.items():
        if top["counts"].get(prefix, 0) < minimum:
            structural_failures.append(
                f"zero_if_rf_soc: {prefix} count {top['counts'].get(prefix, 0)} below {minimum}"
            )
    if structural_failures:
        raise CandidateError("; ".join(structural_failures))
    report = {
        "bytes": len(raw),
        "subcircuits": len(definitions),
        "device_counts": {name: row["counts"] for name, row in definitions.items()},
        "total_candidate_devices": sum(row["devices"] for row in definitions.values()),
        "top_devices": top["devices"],
        "final_end_removed_for_fixture_attachment": True,
    }
    return "\n".join(kept).strip() + "\n", report


def sanitize_fixture(text: str, fixture_name: str, raw_path: Path) -> str:
    result: list[str] = []
    skip_continuation = False
    for _, raw in logical_lines(text):
        line = raw.strip()
        lower = line.casefold()
        if not line or line.startswith(("*", ";")):
            result.append(raw)
            continue
        if lower.startswith(".title") or lower == ".end":
            continue
        if lower.startswith(".include"):
            if "@@fixture_dir@@" in lower:
                result.append(raw.replace("@@FIXTURE_DIR@@", str(FIXTURE_DIR)))
            continue
        if lower.startswith("wrdata"):
            if "@@raw_path@@" in lower:
                result.append(raw.replace("@@RAW_PATH@@", str(raw_path)))
            continue
        if lower.startswith(".ic") and re.search(r"(?i)v\(x", line):
            skip_continuation = True
            continue
        if skip_continuation:
            skip_continuation = False
        if "xlna." in lower:
            continue
        result.append(raw)
    return "\n".join(result).strip() + "\n"


def parse_log_measurements(text: str) -> dict[str, float]:
    measurements: dict[str, float] = {}
    pattern = re.compile(
        r"(?im)^\s*([A-Za-z_][A-Za-z0-9_]*(?:\([^\n=]+\))?)\s*=\s*"
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)"
    )
    for match in pattern.finditer(text):
        measurements[match.group(1).upper()] = float(match.group(2))
    return measurements


def load_waveform(path: Path) -> tuple[list[float], list[float]]:
    times: list[float] = []
    values: list[float] = []
    for raw in path.read_text().splitlines():
        fields = raw.split()
        if len(fields) >= 2:
            times.append(float(fields[0]))
            values.append(float(fields[1]))
    if len(times) < 100:
        raise SimulationError("modulation waveform is too short")
    return times, values


def trapz(x: list[float], y: list[complex | float]) -> complex:
    total = 0j
    for index in range(1, len(x)):
        total += 0.5 * (y[index - 1] + y[index]) * (x[index] - x[index - 1])
    return total


def dot_conj(a: list[complex], b: list[complex]) -> complex:
    return sum(x.conjugate() * y for x, y in zip(a, b))


def analyze_modulation(raw_path: Path) -> dict[str, float]:
    times, rf = load_waveform(raw_path)
    ideal_rows = []
    for raw in (FIXTURE_DIR / "tx_modulation_ideal.dat").read_text().splitlines():
        if raw.strip() and not raw.lstrip().startswith("#"):
            ideal_rows.append([float(item) for item in raw.split()])
    metadata = json.loads((FIXTURE_DIR / "tx_modulation_metadata.json").read_text())
    sample_period = 1.0 / float(metadata["sample_rate_hz"])
    carrier = 2.6e9
    recovered: list[complex] = []
    cursor = 0
    for row in ideal_rows:
        start = row[0]
        stop = start + sample_period
        while cursor < len(times) and times[cursor] < start:
            cursor += 1
        right = cursor
        while right < len(times) and times[right] < stop:
            right += 1
        local_t = times[cursor:right]
        local_y = [
            rf[index] * cmath.exp(-2j * math.pi * carrier * times[index])
            for index in range(cursor, right)
        ]
        if len(local_t) < 2 or local_t[-1] == local_t[0]:
            recovered.append(complex(float("nan"), float("nan")))
        else:
            recovered.append(2.0 * trapz(local_t, local_y) / (local_t[-1] - local_t[0]))

    ideal = [complex(row[1], row[2]) for row in ideal_rows]
    modes = [int(row[5]) for row in ideal_rows]
    single_indices = [index for index, mode in enumerate(modes) if mode == 0]
    start = single_indices[0] + 16
    stop = single_indices[-1] - 8
    best: tuple[float, int, bool, complex] | None = None
    reference_window = ideal[start:stop]
    observed_window = recovered[start:stop]
    for conjugated in (False, True):
        reference = [value.conjugate() if conjugated else value for value in reference_window]
        for delay in range(25):
            ref = reference[: len(reference) - delay or None]
            obs = observed_window[delay:]
            pairs = [(a, b) for a, b in zip(ref, obs) if math.isfinite(b.real) and math.isfinite(b.imag)]
            if len(pairs) < 16:
                continue
            ref = [item[0] for item in pairs]
            obs = [item[1] for item in pairs]
            gain = dot_conj(ref, obs) / dot_conj(ref, ref)
            error = [b - gain * a for a, b in zip(ref, obs)]
            evm = math.sqrt((dot_conj(error, error).real) / (dot_conj([gain * a for a in ref], [gain * a for a in ref]).real))
            if best is None or evm < best[0]:
                best = (evm, delay, conjugated, gain)
    if best is None:
        raise SimulationError("modulation EVM alignment failed")

    multi_indices = [index for index, mode in enumerate(modes) if mode == 1]
    multi_start = multi_indices[0] + 24
    signal = recovered[multi_start : multi_start + 128]
    if len(signal) != 128 or any(not math.isfinite(item.real) for item in signal):
        raise SimulationError("modulation spectrum window is incomplete")
    n = len(signal)
    windowed = [signal[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]
    spectrum = [
        sum(windowed[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n))
        for k in range(n)
    ]
    powers = [abs(value) ** 2 for value in spectrum]
    frequencies = [((k if k < n / 2 else k - n) / (n * sample_period)) for k in range(n)]
    main = sum(power for power, frequency in zip(powers, frequencies) if -30e6 <= frequency <= 30e6)
    lower = sum(power for power, frequency in zip(powers, frequencies) if -90e6 <= frequency < -30e6)
    upper = sum(power for power, frequency in zip(powers, frequencies) if 30e6 < frequency <= 90e6)

    def power_dbm(first: float, last: float) -> float:
        pairs = [(t, y) for t, y in zip(times, rf) if first <= t <= last]
        tx = [item[0] for item in pairs]
        square = [item[1] * item[1] for item in pairs]
        mean_square = trapz(tx, square).real / (tx[-1] - tx[0])
        return 10.0 * math.log10((mean_square / 100.0) / 1e-3)

    lower_aclr = 10.0 * math.log10(lower / main)
    upper_aclr = 10.0 * math.log10(upper / main)
    return {
        "MOD_EVM_PERCENT": 100.0 * best[0],
        "MOD_ACLR_LOWER_DB": lower_aclr,
        "MOD_ACLR_UPPER_DB": upper_aclr,
        "MOD_ACLR_WORST_DB": max(lower_aclr, upper_aclr),
        "MOD_SINGLE_POWER_DBM": power_dbm(80e-9, 280e-9),
        "MOD_MULTI_POWER_DBM": power_dbm(400e-9, 780e-9),
        "MOD_ALIGNMENT_DELAY": float(best[1]),
    }


def analyze_lna_noise(raw_path: Path) -> dict[str, float]:
    rows = []
    for raw in raw_path.read_text().splitlines():
        fields = raw.split()
        if len(fields) >= 6:
            rows.append([float(item) for item in fields])
    if not rows:
        raise SimulationError("LNA noise waveform is empty")
    row = min(rows, key=lambda item: abs(item[1] - 2.6e9))
    source_noise = math.sqrt(4.0 * 1.380649e-23 * 300.15 * 50.0)
    return {
        "LNA_NOISE_FREQUENCY_HZ": row[1],
        "LNA_OUTPUT_NOISE_V_SQRT_HZ": row[3],
        "LNA_INPUT_NOISE_V_SQRT_HZ": row[5],
        "LNA_NOISE_FIGURE_DB_APPROX": 20.0 * math.log10(row[5] / source_noise),
    }


def analyze_lna_linearity(raw_path: Path) -> dict[str, float]:
    times, output = load_waveform(raw_path)
    selected = [(t, y) for t, y in zip(times, output) if 50e-9 <= t <= 150e-9]
    tx = [item[0] for item in selected]
    y = [item[1] for item in selected]
    mean = trapz(tx, y).real / (tx[-1] - tx[0])
    centered = [item - mean for item in y]

    def amplitude(frequency: float) -> float:
        mixed = [value * cmath.exp(-2j * math.pi * frequency * t) for t, value in zip(tx, centered)]
        return abs(trapz(tx, mixed))

    fundamentals = [amplitude(2.59e9), amplitude(2.61e9)]
    im3 = [amplitude(2.57e9), amplitude(2.63e9)]
    fund = math.sqrt(fundamentals[0] * fundamentals[1])
    distortion = math.sqrt(im3[0] * im3[1])
    separation = 20.0 * math.log10(fund / distortion)
    pin_w = 0.01**2 / (8.0 * 50.0)
    pin_dbm = 10.0 * math.log10(pin_w / 1e-3)
    return {
        "LNA_FUND_TO_IM3_DB": separation,
        "LNA_IIP3_DBM": pin_dbm + separation / 2.0,
        "LNA_INPUT_POWER_PER_TONE_DBM": pin_dbm,
    }


_PDK_VERIFIED = False


def verify_trusted_pdk() -> None:
    global _PDK_VERIFIED
    if _PDK_VERIFIED:
        return
    allowlist = json.loads(ALLOWLIST_PATH.read_text())
    for row in allowlist["recursive_files"]:
        path = PDK_DIR / row["path"]
        if not path.is_file():
            raise SimulationError(f"trusted PDK file is missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise SimulationError(f"trusted PDK hash mismatch: {path}")
    _PDK_VERIFIED = True


def run_fixture(core: str, fixture_name: str, artifact_dir: Path) -> dict[str, float]:
    fixture_path = FIXTURE_DIR / fixture_name
    if not fixture_path.is_file():
        raise SimulationError(f"missing fixture {fixture_name}")
    if not PDK_ENTRY.is_file():
        raise SimulationError(f"missing trusted SKY130 entry point {PDK_ENTRY}")
    verify_trusted_pdk()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = artifact_dir.resolve()
    stem = Path(fixture_name).stem
    deck_path = artifact_dir / f"{stem}.deck.cir"
    log_path = artifact_dir / f"{stem}.ngspice.log"
    raw_path = artifact_dir / f"{stem}.waveform.dat"
    fixture = sanitize_fixture(fixture_path.read_text(encoding="utf-8"), fixture_name, raw_path)
    deck = (
        f"* Private sample 1 benchmark fixture: {fixture_name}\n"
        f'.include "{PDK_ENTRY}"\n'
        + core.rstrip()
        + "\n"
        + fixture.rstrip()
        + "\n.end\n"
    )
    deck_path.write_text(deck, encoding="utf-8")
    timeout = 2400 if fixture_name in {"tx_modulation_public_tb.cir", "pll_public_tb.cir", "soc_public_tb.cir"} else 900
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log_path), str(deck_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SimulationError(f"ngspice could not run {fixture_name}: {exc}") from exc
    elapsed = time.monotonic() - started
    text = log_path.read_text(errors="replace") if log_path.exists() else completed.stdout + completed.stderr
    fatal = re.search(r"(?i)(fatal|unknown subckt|timestep too small|cannot open|error:)", text)
    if completed.returncode != 0 or fatal:
        detail = fatal.group(0) if fatal else f"exit {completed.returncode}"
        raise SimulationError(f"ngspice failed {fixture_name}: {detail}")
    measurements = parse_log_measurements(text)
    measurements["FIXTURE_WALL_SECONDS"] = elapsed
    if fixture_name == "tx_modulation_public_tb.cir":
        measurements.update(analyze_modulation(raw_path))
    elif fixture_name == "lna_noise_public_tb.cir":
        measurements.update(analyze_lna_noise(raw_path))
    elif fixture_name == "lna_linearity_public_tb.cir":
        measurements.update(analyze_lna_linearity(raw_path))
    (artifact_dir / f"{stem}.measurements.json").write_text(
        json.dumps(measurements, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return measurements


def evaluate_formula(formula: str, measurements: dict[str, float]) -> float:
    environment = {name.casefold(): value for name, value in measurements.items()}
    rewritten = formula.casefold()
    if re.search(r"[^A-Za-z0-9_+*/().\-\s]", rewritten):
        raise SimulationError(f"unsupported formula {formula}")
    return float(eval(rewritten, {"__builtins__": {}}, environment))


def measured_value(criterion: dict, measurements: dict[str, float]) -> float | None:
    if criterion.get("derived") == "vpp_to_dbm_100ohm":
        vpp = measurements.get(criterion["measurement"].upper())
        if vpp is None or vpp <= 0:
            return None
        value = 10.0 * math.log10((((vpp / (2.0 * math.sqrt(2.0))) ** 2) / 100.0) / 1e-3)
    elif criterion.get("formula"):
        try:
            value = evaluate_formula(criterion["formula"], measurements)
        except Exception:
            return None
    else:
        value = measurements.get(criterion["measurement"].upper())
    if value is None or not math.isfinite(value):
        return None
    transform = criterion.get("transform", "identity")
    if transform == "abs":
        value = abs(value)
    elif transform == "negate":
        value = -value
    elif transform == "db20":
        if value <= 0:
            return None
        value = 20.0 * math.log10(value)
    return value


def criterion_reward(criterion: dict, measured: float, difficulty: str) -> tuple[float, float]:
    full_error, zero_error = BANDS[difficulty]
    measured = round9(measured)
    floor = round9(float(criterion["scale_floor"]))
    kind = criterion["criterion_type"]
    if kind == "central":
        target = round9(criterion["target"])
        error = abs(measured - target) / max(abs(target), floor)
    elif kind == "lower":
        target = round9(criterion["target"])
        error = max(0.0, (measured - target) / max(abs(target), floor))
    elif kind == "higher":
        target = round9(criterion["target"])
        error = max(0.0, (target - measured) / max(abs(target), floor))
    elif kind == "range":
        lower = round9(criterion["lower"])
        upper = round9(criterion["upper"])
        denominator = max(abs(lower), abs(upper - lower), floor)
        if measured < lower:
            error = (lower - measured) / denominator
        elif measured > upper:
            error = (measured - upper) / denominator
        else:
            error = 0.0
    else:
        raise ValueError(f"unsupported criterion type {kind}")
    if error <= full_error:
        reward = 1.0
    elif error >= zero_error:
        reward = 0.0
    else:
        reward = (zero_error - error) / (zero_error - full_error)
    return max(0.0, min(1.0, reward)), error


def grade_submission(candidate: Path, artifact_dir: Path, difficulty: str) -> dict:
    if difficulty not in BANDS:
        raise ValueError(f"unknown difficulty {difficulty}")
    ledger = json.loads(LEDGER_PATH.read_text())
    architecture = json.loads(ARCHITECTURE_PATH.read_text())
    result = {
        "difficulty": difficulty,
        "candidate": str(candidate),
        "eligibility_gate_pass": False,
        "structural_failures": [],
        "simulation_failures": [],
        "criteria": [],
    }
    try:
        core, structural_report = parse_candidate(candidate, architecture)
        result["structural_report"] = structural_report
    except CandidateError as exc:
        result["structural_failures"].append(str(exc))
        core = ""
    fixture_cache: dict[str, dict[str, float] | Exception] = {}
    if core:
        for fixture in sorted({row["fixture"] for row in ledger["targets"]}):
            try:
                fixture_cache[fixture] = run_fixture(core, fixture, artifact_dir / "fixtures")
            except Exception as exc:
                fixture_cache[fixture] = exc
                result["simulation_failures"].append(f"{fixture}: {exc}")
    weighted = 0.0
    weight_sum = 0.0
    for criterion in ledger["targets"]:
        fixture_result = fixture_cache.get(criterion["fixture"])
        failure = None
        measured = None
        if not core:
            failure = "candidate failed structural eligibility"
        elif isinstance(fixture_result, Exception):
            failure = str(fixture_result)
        elif fixture_result is None:
            failure = "fixture was not evaluated"
        else:
            measured = measured_value(criterion, fixture_result)
            if measured is None:
                failure = f"missing or non-finite measurement {criterion['measurement']}"
        if measured is None:
            reward, error = 0.0, None
        else:
            reward, error = criterion_reward(criterion, measured, difficulty)
        weight = 1.0 if difficulty in {"hard", "harder"} else (1.0 if criterion["essential"] else 0.5)
        weighted += reward * weight
        weight_sum += weight
        result["criteria"].append(
            {
                "id": criterion["id"],
                "category": criterion["category"],
                "description": criterion["description"],
                "fixture": criterion["fixture"],
                "measurement": criterion["measurement"],
                "criterion_type": criterion["criterion_type"],
                "target": criterion.get("target"),
                "lower": criterion.get("lower"),
                "upper": criterion.get("upper"),
                "scale_floor": criterion["scale_floor"],
                "measured": measured,
                "unit": criterion["unit"],
                "essential": criterion["essential"],
                "weight": weight,
                "normalized_adverse_error": error,
                "reward": reward,
                "failure": failure,
            }
        )
    gate_pass = bool(core) and not result["simulation_failures"] and all(
        row["measured"] is not None for row in result["criteria"]
    )
    result["eligibility_gate_pass"] = gate_pass
    result["raw_deterministic_score_before_gate"] = weighted / weight_sum if weight_sum else 0.0
    result["final_reward"] = result["raw_deterministic_score_before_gate"] if gate_pass else 0.0
    result["criteria_expected"] = len(result["criteria"])
    result["criteria_measured"] = sum(row["measured"] is not None for row in result["criteria"])
    result["artifact_evaluable"] = gate_pass
    result["production_pass"] = gate_pass and math.isclose(result["final_reward"], 1.0, abs_tol=1e-12)
    return result


def calibrate(candidate: Path, template_path: Path, output_path: Path, artifact_dir: Path) -> dict:
    architecture = json.loads(ARCHITECTURE_PATH.read_text())
    core, report = parse_candidate(candidate, architecture)
    template = json.loads(template_path.read_text())
    cache = {}
    failures = []
    targets = []
    for fixture in sorted({row["fixture"] for row in template["criteria"]}):
        try:
            cache[fixture] = run_fixture(core, fixture, artifact_dir / "fixtures")
        except Exception as exc:
            cache[fixture] = exc
            failures.append(f"{fixture}: {exc}")
    for criterion in template["criteria"]:
        measurements = cache.get(criterion["fixture"])
        measured = measured_value(criterion, measurements) if isinstance(measurements, dict) else None
        if measured is None:
            reason = str(measurements) if isinstance(measurements, Exception) else f"missing {criterion['measurement']}"
            failures.append(f"{criterion['id']}: {reason}")
            continue
        row = dict(criterion)
        row["reference_measurement"] = round9(measured)
        if row["criterion_type"] != "range":
            row["target"] = round9(measured)
        row["provenance"] = {
            "kind": "fresh_ngspice_reference_replay",
            "analysis_deck": criterion["fixture"],
            "measurement_expression": criterion.get("formula", criterion["measurement"]),
            "operating_condition": criterion["operating_condition"],
        }
        targets.append(row)
    calibration_exclusions = [
        {
            "metric": item.split(":", 1)[0],
            "reason": item.split(":", 1)[1].strip() if ":" in item else item,
            "kind": "fresh_reference_calibration_failure",
        }
        for item in failures
    ]
    if not targets:
        raise RuntimeError("reference calibration produced no successful targets")
    ledger = {
        "schema": "sample-1-target-ledger-v1",
        "simulator": "ngspice-46",
        "pdk_version": "c6d73a35f524070e85faff4a6a9eef49553ebc2b",
        "pdk_corner": "tt",
        "temperature_c": 27,
        "supply_v": 1.8,
        "random_seed": 1,
        "reference_candidate": str(candidate),
        "reference_structural_report": report,
        "targets": targets,
        "excluded_reference_metrics": [*template["excluded_reference_metrics"], *calibration_exclusions],
        "calibration_failure_count": len(calibration_exclusions),
    }
    output_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"calibrated {len(targets)} targets to {output_path}")
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--difficulty", choices=tuple(BANDS), default="hard")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibrate-template", type=Path)
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    if args.calibrate_template:
        result = calibrate(
            args.candidate,
            args.calibrate_template,
            args.output,
            args.artifact_dir,
        )
    else:
        result = grade_submission(args.candidate, args.artifact_dir, args.difficulty)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "difficulty": args.difficulty,
            "final_reward": result["final_reward"],
            "eligibility_gate_pass": result["eligibility_gate_pass"],
            "criteria_measured": result["criteria_measured"],
            "criteria_expected": result["criteria_expected"],
        }, indent=2))


if __name__ == "__main__":
    main()
