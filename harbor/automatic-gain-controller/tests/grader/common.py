from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MODEL_PATH = PACKAGE / "models/system.lib"
MAX_CANDIDATE_BYTES = 100_000
NUMBER = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?(?:meg|[tgkmunpf])?$",
    re.IGNORECASE,
)


class CandidateError(ValueError):
    pass


class SimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    source: str
    ports: tuple[str, ...]


def parse_candidate(path: Path, expected_ports: tuple[str, ...], allow_helpers: bool = False) -> Candidate:
    source = path.read_text(encoding="utf-8")
    if not source.strip():
        raise CandidateError("submission is empty")
    if len(source.encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateError(f"submission exceeds {MAX_CANDIDATE_BYTES} bytes")
    lowered = source.casefold()
    for token in (
        ".include", ".lib", ".model", ".control", ".endc", ".ac", ".dc", ".tran",
        ".noise", ".four", ".measure", ".meas", ".shell", ".csparam",
    ):
        if re.search(rf"(?m)^\s*{re.escape(token)}\b", lowered):
            raise CandidateError(f"candidate contains prohibited directive {token}")

    subcircuits = re.findall(r"(?im)^\s*\.subckt\s+(\S+)\s+([^\r\n]+)$", source)
    candidates = [(name, ports.split()) for name, ports in subcircuits if name.casefold() == "candidate"]
    if len(candidates) != 1:
        raise CandidateError("submission must define exactly one candidate subcircuit")
    actual_ports = tuple(port.casefold() for port in candidates[0][1])
    if actual_ports != expected_ports:
        raise CandidateError(
            "candidate port order is invalid; expected " + " ".join(expected_ports)
        )
    if not allow_helpers and len(subcircuits) != 1:
        raise CandidateError("nested or helper subcircuits are not allowed for this task")

    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("*") or line.startswith(".") or line.startswith("+"):
            continue
        kind = line[0].casefold()
        if kind in {"v", "i", "b", "e", "f", "g", "h", "s", "w", "t", "a"}:
            raise CandidateError(f"candidate contains prohibited element: {line.split()[0]}")
        if kind not in {"r", "c", "l", "d", "q", "m", "x"}:
            raise CandidateError(f"candidate contains unsupported element: {line.split()[0]}")
        if kind == "x" and not allow_helpers:
            raise CandidateError("X instances are not allowed for this task")
    return Candidate(source=source.rstrip() + "\n", ports=actual_ports)


def validate_task_structure(task: str, candidate: Candidate) -> None:
    """Enforce disclosed physical topology without requiring one reference netlist."""
    source = candidate.source
    lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("*")
    ]
    elements = [line for line in lines if not line.startswith(".") and not line.startswith("+")]
    by_kind = {
        kind: [line for line in elements if line[0].casefold() == kind]
        for kind in "rcldqmx"
    }

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CandidateError(message)

    def has_value(kind: str, value: str) -> bool:
        pattern = re.compile(rf"(?:^|\s){re.escape(value)}(?:\s|$)", re.IGNORECASE)
        return any(pattern.search(line) for line in by_kind[kind])

    def element_tokens(kind: str) -> list[list[str]]:
        return [line.split() for line in by_kind[kind]]

    def passives_between(kind: str, left: str, right: str, value: str) -> int:
        return sum(
            len(tokens) >= 4
            and {tokens[1].casefold(), tokens[2].casefold()} == {left, right}
            and tokens[3].casefold() == value
            for tokens in element_tokens(kind)
        )

    if task == "agc_controller_tl_run_01":
        helpers = re.findall(r"(?im)^\s*\.subckt\s+(?!candidate\b)(\S+)", source)
        require(len(helpers) == 1, "AGC must define exactly one local amplifier subcircuit")
        helper = helpers[0]
        calls = [line for line in by_kind["x"] if re.search(rf"\s{re.escape(helper)}\s*$", line, re.IGNORECASE)]
        require(len(calls) == 2, "AGC must instantiate its local amplifier exactly twice")
        require(has_value("r", "600"), "AGC requires the disclosed 600 ohm detector filter")
        require(has_value("c", "150f"), "AGC requires the disclosed 150 fF differential filter")
        require(len(by_kind["q"]) >= 4 and len(by_kind["m"]) >= 6, "AGC requires physical follower, mirror, and CMOS amplifier devices")
    elif task == "bias_servo_tl_run_05":
        require(len(by_kind["m"]) >= 3 and len(by_kind["q"]) >= 8, "bias servo requires a PMOS regulator and two transistor cancellation loops")
        cancellations = [
            line for line in by_kind["m"]
            if re.search(r"\bW\s*=\s*25u\b", line, re.IGNORECASE)
            and re.search(r"\bL\s*=\s*(?:\.33u|0\.33u)\b", line, re.IGNORECASE)
        ]
        require(len(cancellations) >= 2, "bias servo requires two disclosed 25 um by 0.33 um cancellation NMOS devices")
    elif task == "common_mode_controller_tl_run_08":
        require(len(by_kind["m"]) == 7, "common-mode controller requires exactly two physical differential-pair paths and mirror biasing")
        require(len(by_kind["r"]) >= 8, "common-mode controller requires resistor loads and source degeneration")
    elif task == "input_tia_tl_regression":
        require(len(by_kind["q"]) >= 8, "input TIA requires two physical shunt-feedback transistor halves")
        require(sum(bool(re.search(r"\s80(?:\s|$)", line, re.IGNORECASE)) for line in by_kind["r"]) >= 2, "input TIA requires two 80 ohm collector resistors")
        require(sum(bool(re.search(r"\s250(?:\s|$)", line, re.IGNORECASE)) for line in by_kind["r"]) >= 2, "input TIA requires two 250 ohm feedback resistors")
    elif task == "interstage_interface_tl_run_01":
        helpers = re.findall(r"(?im)^\s*\.subckt\s+(?!candidate\b)(\S+)", source)
        require(len(helpers) == 1, "interfaces task must define exactly one local interface cell")
        helper = helpers[0]
        calls = [line for line in by_kind["x"] if re.search(rf"\s{re.escape(helper)}(?:\s+PARAMS:.*)?$", line, re.IGNORECASE)]
        require(len(calls) == 6, "interfaces task must instantiate its local interface cell exactly six times")
        helper_match = re.search(
            rf"(?is)^\s*\.subckt\s+{re.escape(helper)}\b.*?^\s*\.ends\b",
            source,
            re.MULTILINE,
        )
        helper_body = helper_match.group(0) if helper_match else ""
        require(
            all(re.search(rf"(?im)^\s*{kind}\S*\s", helper_body) for kind in "rcqm"),
            "interface cell requires physical coupling, bias resistance, an emitter follower, and a mirror sink",
        )
    elif task == "mode_switch_tl_run_08":
        mos = element_tokens("m")
        require(len(mos) == 6, "mode switch requires one CMOS inverter and two transmission gates")
        require(
            sum(len(tokens) >= 6 and tokens[5].casefold() == "nmos_sys" for tokens in mos) == 3
            and sum(len(tokens) >= 6 and tokens[5].casefold() == "pmos_sys" for tokens in mos) == 3,
            "mode switch requires three NMOS and three PMOS devices",
        )
        for source_node in ("mgc", "agc"):
            require(
                sum(
                    len(tokens) >= 4
                    and {tokens[1].casefold(), tokens[3].casefold()} == {"gc", source_node}
                    for tokens in mos
                )
                == 2,
                f"mode switch requires one complementary transmission gate for {source_node}",
            )
    elif task == "output_buffer_tl_regression":
        require(len(by_kind["q"]) >= 2 and len(by_kind["m"]) >= 3, "output buffer requires a differential pair and transistor-mirror biasing")
        require(passives_between("r", "vcc", "outp", "50") == 1, "output buffer requires the positive 50 ohm collector resistor")
        require(passives_between("r", "vcc", "outn", "50") == 1, "output buffer requires the negative 50 ohm collector resistor")
        require(passives_between("r", "outp", "outn", "100") == 1, "output buffer requires the 100 ohm differential load")
        require(passives_between("r", "outp", "finalp", "50") == 1, "output buffer requires the positive 50 ohm output resistor")
        require(passives_between("r", "outn", "finaln", "50") == 1, "output buffer requires the negative 50 ohm output resistor")
        require(passives_between("c", "finalp", "0", "66f") == 1, "output buffer requires the positive 66 fF pad capacitor")
        require(passives_between("c", "finaln", "0", "66f") == 1, "output buffer requires the negative 66 fF pad capacitor")
    elif task == "peak_detector_tl_regression":
        require(len(by_kind["q"]) >= 10 and len(by_kind["m"]) >= 5, "peak detector requires the Gilbert core, calibration pair, and transistor-mirror biasing")
        require(len(by_kind["c"]) >= 4, "peak detector requires symmetric coupling and filtering capacitors")
    elif task == "vga1_tl_regression":
        require(len(by_kind["q"]) >= 8 and len(by_kind["m"]) >= 5, "VGA1 requires a current-steering core, follower outputs, and transistor-mirror biasing")
        require(sum(has_value("r", value) for value in ("225", "93")) == 2, "VGA1 requires 225 ohm loading and 93 ohm emitter degeneration")
    elif task == "vga2_tl_regression":
        require(len(by_kind["q"]) >= 8 and len(by_kind["m"]) >= 5, "VGA2 requires a current-steering core, follower outputs, and transistor-mirror biasing")
        require(len(by_kind["d"]) >= 2, "VGA2 requires a symmetric physical varactor pair")
        require(sum(has_value("r", value) for value in ("225", "93")) == 2, "VGA2 requires 225 ohm loading and 93 ohm emitter degeneration")


def run_ngspice(deck: str, artifact_dir: Path, timeout: int = 120) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODEL_PATH, artifact_dir / "system.lib")
    deck_path = artifact_dir / "fixture.cir"
    log_path = artifact_dir / "ngspice.log"
    deck_path.write_text(deck, encoding="utf-8")
    try:
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log_path), str(deck_path)],
            cwd=artifact_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulationError(f"Ngspice exceeded {timeout} seconds") from exc
    if completed.returncode != 0:
        log = log_path.read_text(errors="replace") if log_path.exists() else completed.stderr
        raise SimulationError(log.strip()[-3000:])
    log = log_path.read_text(errors="replace")
    if re.search(r"(?im)^\s*(?:fatal|error):", log):
        raise SimulationError(log.strip()[-3000:])
    return artifact_dir


def read_real_table(path: Path, vectors: int, minimum_rows: int = 1) -> tuple[list[float], list[list[float]]]:
    scale: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if len(fields) < vectors + 1:
            continue
        try:
            values = [float(value) for value in fields[: vectors + 1]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in values):
            raise SimulationError(f"nonfinite value in {path.name}")
        scale.append(values[0])
        for index in range(vectors):
            outputs[index].append(values[index + 1])
    if len(scale) < minimum_rows:
        raise SimulationError(f"too few rows in {path.name}: {len(scale)}")
    return scale, outputs


def read_complex_table(path: Path, vectors: int, minimum_rows: int = 100) -> tuple[list[float], list[list[complex]]]:
    scale: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if len(fields) < 1 + 2 * vectors:
            continue
        try:
            values = [float(value) for value in fields[: 1 + 2 * vectors]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in values):
            raise SimulationError(f"nonfinite value in {path.name}")
        scale.append(values[0])
        for index in range(vectors):
            outputs[index].append(complex(values[1 + 2 * index], values[2 + 2 * index]))
    if len(scale) < minimum_rows:
        raise SimulationError(f"too few rows in {path.name}: {len(scale)}")
    return scale, outputs


def interpolate_log_x(x0: float, y0: float, x1: float, y1: float, target: float) -> float:
    if y1 == y0:
        return x1
    fraction = (target - y0) / (y1 - y0)
    return math.exp(math.log(x0) + fraction * (math.log(x1) - math.log(x0)))


def interpolate_y_on_log_x(x0: float, y0: float, x1: float, y1: float, target_x: float) -> float:
    if x1 == x0:
        return y1
    fraction = math.log(target_x / x0) / math.log(x1 / x0)
    return y0 + fraction * (y1 - y0)


def magnitude_at(frequency: list[float], values: list[complex], target: float) -> float:
    for index, current in enumerate(frequency):
        if math.isclose(current, target, rel_tol=1e-12):
            return abs(values[index])
        if current > target and index:
            left = abs(values[index - 1])
            right = abs(values[index])
            return interpolate_y_on_log_x(
                frequency[index - 1], left, current, right, target
            )
    raise SimulationError(f"AC sweep does not contain {target} Hz")


def upper_3db_frequency(frequency: list[float], values: list[complex], baseline_hz: float) -> float:
    baseline = magnitude_at(frequency, values, baseline_hz)
    threshold = baseline / math.sqrt(2.0)
    for index in range(1, len(frequency)):
        if frequency[index] <= baseline_hz:
            continue
        left = abs(values[index - 1])
        right = abs(values[index])
        if left >= threshold > right:
            return interpolate_log_x(
                frequency[index - 1], left, frequency[index], right, threshold
            )
    raise SimulationError("AC response has no descending 3 dB crossing")


def harmonic(time: list[float], values: list[float], frequency_hz: float, order: int = 1) -> complex:
    angular = 2.0 * math.pi * frequency_hz * order
    duration = time[-1] - time[0]
    if duration <= 0.0:
        raise SimulationError("waveform duration is not positive")
    sine_integral = 0.0
    cosine_integral = 0.0
    for index in range(1, len(time)):
        left_t, right_t = time[index - 1], time[index]
        dt = right_t - left_t
        left_value, right_value = values[index - 1], values[index]
        sine_integral += 0.5 * dt * (
            left_value * math.sin(angular * left_t)
            + right_value * math.sin(angular * right_t)
        )
        cosine_integral += 0.5 * dt * (
            left_value * math.cos(angular * left_t)
            + right_value * math.cos(angular * right_t)
        )
    scale = 2.0 / duration
    return complex(sine_integral * scale, cosine_integral * scale)


def waveform_metrics(time: list[float], values: list[float], frequency_hz: float) -> dict[str, float]:
    fundamental = abs(harmonic(time, values, frequency_hz))
    harmonics = [abs(harmonic(time, values, frequency_hz, order)) for order in range(2, 6)]
    thd = math.inf if fundamental <= 0.0 else math.sqrt(sum(value * value for value in harmonics)) / fundamental
    return {
        "fundamental_peak": fundamental,
        "peak_to_peak": max(values) - min(values),
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
        "thd_ratio": thd,
    }


def persistent_settling_time(
    time: list[float],
    values: list[float],
    step_time: float,
    final_value: float,
    fraction: float,
    stop_time: float | None = None,
) -> float:
    tolerance = max(abs(final_value) * fraction, 1e-12)
    last_bad = step_time
    found = False
    for t, value in zip(time, values, strict=True):
        if t < step_time:
            continue
        if stop_time is not None and t > stop_time:
            break
        found = True
        if abs(value - final_value) > tolerance:
            last_bad = t
    if not found:
        raise SimulationError("settling window has no samples")
    return max(0.0, last_bad - step_time)


def private_deck(title: str, candidate: Candidate, circuit: str, controls: str) -> str:
    return f"""{title}
.include system.lib
{candidate.source}
{circuit}
.control
set wr_vecnames
set wr_singlescale
{controls}
quit
.endc
.end
"""
