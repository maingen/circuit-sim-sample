from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


MODEL_PATH = Path(os.environ.get("EESIM_CMOS_MODEL", "/opt/eesim/models/cmos018-s112b.lib"))
MODEL_SHA256 = "6cb4327c4fa5d00af4eff9805e6a22689ac75939e3d173f0ae1b44dd4a522a99"
EXPECTED_PORTS = ("in", "out", "vdd", "vss")
MAX_CANDIDATE_BYTES = 100_000
MAX_ELEMENTS = 256
AC_POINTS_PER_DECADE = 400
AC_START_HZ = 1.0e6
AC_STOP_HZ = 5.0e9
GAIN_FREQUENCY_HZ = 10.0e6
TRANSIENT_STEP_SECONDS = 1.0e-6
TRANSIENT_STOP_SECONDS = 20.0e-3
TRANSIENT_START_SECONDS = 15.0e-3
TRANSIENT_INPUT_AMPLITUDE_V = 1.0e-3
TRANSIENT_FREQUENCY_HZ = 1_000.0

# Reseeded from the exact legal reference under Ngspice 46.  These are
# replaced only after running the final private fixture.
GAIN_TARGET = 45.56398908157094
UPPER_CUTOFF_LIMIT_HZ = 82_720_000.0
TRANSIENT_GAIN_TARGET = 47.510692006527876
THD_LIMIT_PERCENT = 0.004032
UNLOADED_GAIN_REFERENCE = 45.74228581462005
LOADED_RATIO_MINIMUM = 0.97
LOADED_RATIO_MAXIMUM = 1.00

STRUCTURAL_CRITERIA = (
    "exact_interface",
    "accepted_bounded_netlist",
    "required_two_stage_cmos_topology_and_open_feedback_network",
    "allowed_elements_and_models",
    "exact_reference_current",
    "no_hidden_dependencies",
    "ngspice_completed",
    "finite_required_measurements",
)
NODE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*|0)$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
NUMBER = re.compile(
    r"^([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?)(meg|[tgkmunpf])?$",
    re.IGNORECASE,
)
SUFFIXES = {
    "t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3,
    "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15,
}


class CandidateError(ValueError):
    pass


class SimulationError(RuntimeError):
    pass


class InfrastructureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Element:
    name: str
    kind: str
    nodes: tuple[str, ...]
    model: str | None = None
    value: float | None = None
    parameters: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class Candidate:
    source: str
    elements: tuple[Element, ...]
    first_branch_device_a: str
    first_branch_device_b: str
    tail_branch_device: str
    second_branch_device_a: str
    second_branch_device_b: str
    bias_branch_device: str


def parse_value(raw: str) -> float:
    match = NUMBER.fullmatch(raw)
    if not match:
        raise CandidateError(f"invalid SPICE value: {raw}")
    value = float(match.group(1)) * SUFFIXES.get((match.group(2) or "").casefold(), 1.0)
    if not math.isfinite(value) or abs(value) > 1e12:
        raise CandidateError(f"SPICE value is out of range: {raw}")
    return value


def validate_node(raw: str) -> str:
    if not NODE.fullmatch(raw):
        raise CandidateError(f"invalid node name: {raw}")
    return raw.casefold()


def validate_connectivity(elements: list[Element]) -> None:
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        if parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for element in elements:
        for terminal in element.nodes:
            find(terminal)
        for terminal in element.nodes[1:]:
            union(element.nodes[0], terminal)
    for port in EXPECTED_PORTS:
        if port not in parent:
            raise CandidateError(f"port {port} is not connected")
    root = find("in")
    if any(find(port) != root for port in EXPECTED_PORTS):
        raise CandidateError("all candidate ports must belong to one connected circuit")
    orphaned = sorted(terminal for terminal in parent if find(terminal) != root)
    if orphaned:
        raise CandidateError(f"disconnected internal node: {orphaned[0]}")


def require_topology(elements: list[Element]) -> tuple[str, str, str, str, str, str]:
    mos = [element for element in elements if element.kind == "m"]
    if len(mos) < 8:
        raise CandidateError("the two-stage op amp must contain at least eight MOSFETs")
    nmos = [element for element in mos if element.model == "nmos4"]
    pmos = [element for element in mos if element.model == "pmos4"]
    references = [element for element in elements if element.kind == "i"]
    bias_node = references[0].nodes[1]
    resistors = [element for element in elements if element.kind == "r"]
    upper_feedback = [
        resistor for resistor in resistors
        if math.isclose(float(resistor.value), 92.0e3, rel_tol=1e-12)
        and "out" in resistor.nodes
    ]
    open_nodes = {node for resistor in upper_feedback for node in resistor.nodes if node != "out"}
    lower_feedback = [
        resistor for resistor in resistors
        if math.isclose(float(resistor.value), 8.0e3, rel_tol=1e-12)
        and "0" in resistor.nodes
        and any(node in open_nodes for node in resistor.nodes)
    ]
    if not upper_feedback or not lower_feedback:
        raise CandidateError("the open 92 kOhm and 8 kOhm feedback divider is missing")
    feedback_node = next(node for node in lower_feedback[0].nodes if node != "0")
    touching_feedback = [element for element in elements if feedback_node in element.nodes]
    if len(touching_feedback) != 2 or any(element.kind != "r" for element in touching_feedback):
        raise CandidateError("the feedback divider midpoint must remain open")
    grounded_gate_nodes = {
        node
        for resistor in resistors
        if "0" in resistor.nodes
        for node in resistor.nodes
        if node != "0"
    }

    for driven in nmos:
        if driven.nodes[1] != "in":
            continue
        for grounded in nmos:
            if grounded is driven or grounded.nodes[1] not in ({"0"} | grounded_gate_nodes) or grounded.nodes[2] != driven.nodes[2]:
                continue
            left_drain, right_drain = driven.nodes[0], grounded.nodes[0]
            for diode in pmos:
                if diode.nodes[0] != diode.nodes[1] or diode.nodes[2:] != ("vdd", "vdd"):
                    continue
                for mirror in pmos:
                    if mirror is diode or mirror.nodes[1] != diode.nodes[1] or mirror.nodes[2:] != ("vdd", "vdd"):
                        continue
                    if {diode.nodes[0], mirror.nodes[0]} != {left_drain, right_drain}:
                        continue
                    first_output = mirror.nodes[0]
                    tails = [m for m in nmos if m.nodes[0] == driven.nodes[2] and m.nodes[1] == bias_node and m.nodes[2] == "vss"]
                    bias_diodes = [m for m in nmos if m.nodes[0] == bias_node and m.nodes[1] == bias_node and m.nodes[2] == "vss"]
                    output_loads = [m for m in nmos if m.nodes[0] == "out" and m.nodes[1] == bias_node and m.nodes[2] == "vss"]
                    second_devices = [m for m in nmos if m.nodes[0] == "vdd" and m.nodes[1] == first_output and m.nodes[2] == "out"]
                    if tails and bias_diodes and output_loads and second_devices:
                        return (
                            driven.name.casefold(), grounded.name.casefold(), tails[0].name.casefold(),
                            second_devices[0].name.casefold(), output_loads[0].name.casefold(),
                            bias_diodes[0].name.casefold(),
                        )
    raise CandidateError("required differential pair, PMOS mirror, second stage, and NMOS bias mirrors are missing")


def parse_candidate(source: str) -> Candidate:
    if not source.strip():
        raise CandidateError("submission is empty")
    if len(source.encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateError("submission is too large")
    logical = [line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith("*")]
    if len(logical) < 2:
        raise CandidateError("submission must contain the candidate subcircuit")
    if [token.casefold() for token in logical[0].split()] != [".subckt", "candidate", *EXPECTED_PORTS]:
        raise CandidateError("header must be '.subckt candidate in out vdd vss'")
    if [token.casefold() for token in logical[-1].split()] not in ([".ends"], [".ends", "candidate"]):
        raise CandidateError("submission must end with '.ends candidate'")

    elements: list[Element] = []
    names: set[str] = set()
    for line in logical[1:-1]:
        if line.startswith(".") or line.startswith("+"):
            raise CandidateError(f"unsupported directive or continuation: {line}")
        tokens = line.split()
        instance = tokens[0]
        folded = instance.casefold()
        if not NAME.fullmatch(instance) or folded in names:
            raise CandidateError(f"invalid or duplicate instance name: {instance}")
        names.add(folded)
        kind = instance[0].casefold()
        if kind == "m":
            if len(tokens) < 8:
                raise CandidateError(f"{instance} requires four nodes, a model, L, and W")
            nodes = tuple(validate_node(item) for item in tokens[1:5])
            model = tokens[5].casefold()
            if model not in {"nmos4", "pmos4"}:
                raise CandidateError(f"{instance} must use NMOS4 or PMOS4")
            parameters: dict[str, float] = {}
            for token in tokens[6:]:
                if token.count("=") != 1:
                    raise CandidateError(f"invalid MOS parameter: {token}")
                key, raw = token.split("=", 1)
                key = key.casefold()
                if key not in {"l", "w", "ad", "as", "pd", "ps", "m"} or key in parameters:
                    raise CandidateError(f"unsupported or duplicate MOS parameter: {key}")
                parameters[key] = parse_value(raw)
                if parameters[key] <= 0.0:
                    raise CandidateError(f"{instance} parameter {key} must be positive")
            if "l" not in parameters or "w" not in parameters:
                raise CandidateError(f"{instance} must specify literal L and W")
            elements.append(Element(instance, kind, nodes, model=model, parameters=tuple(parameters.items())))
        elif kind in {"r", "c", "l"}:
            if len(tokens) != 4:
                raise CandidateError(f"{instance} must have two nodes and one value")
            nodes = tuple(validate_node(item) for item in tokens[1:3])
            value = parse_value(tokens[3])
            if value <= 0.0 or nodes[0] == nodes[1]:
                raise CandidateError(f"{instance} must have a positive value and distinct nodes")
            elements.append(Element(instance, kind, nodes, value=value))
        elif kind == "i":
            if folded != "iref":
                raise CandidateError("the only current source must be named IREF")
            if len(tokens) == 4:
                raw = tokens[3]
            elif len(tokens) == 5 and tokens[3].casefold() == "dc":
                raw = tokens[4]
            else:
                raise CandidateError("IREF must be an independent DC current source")
            nodes = tuple(validate_node(item) for item in tokens[1:3])
            value = parse_value(raw)
            if nodes[0] != "vdd" or nodes[1] in EXPECTED_PORTS or not math.isclose(value, 200e-6, rel_tol=1e-12):
                raise CandidateError("IREF must supply 200 uA from vdd to an internal bias node")
            elements.append(Element(instance, kind, nodes, value=value))
        else:
            raise CandidateError(f"unsupported element: {instance}")
    if not elements or len(elements) > MAX_ELEMENTS:
        raise CandidateError("submission has an invalid element count")
    if sum(element.kind == "i" for element in elements) != 1:
        raise CandidateError("exactly one 200 uA IREF source is required")
    selected = require_topology(elements)
    validate_connectivity(elements)
    return Candidate(source.rstrip() + "\n", tuple(elements), *selected)


def read_table(path: Path, columns: int, minimum_rows: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if len(fields) < columns:
            continue
        try:
            row = [float(item) for item in fields[:columns]]
        except ValueError:
            continue
        if not all(math.isfinite(item) for item in row):
            raise SimulationError("Ngspice produced a nonfinite value")
        rows.append(row)
    if len(rows) < minimum_rows:
        raise SimulationError(f"Ngspice produced too few rows in {path.name}")
    return rows


def interpolate_log_x(x0: float, y0: float, x1: float, y1: float, target: float) -> float:
    fraction = (target - y0) / (y1 - y0)
    return math.exp(math.log(x0) + fraction * (math.log(x1) - math.log(x0)))


def harmonic(time: list[float], values: list[float], number: int) -> tuple[float, float]:
    omega = 2.0 * math.pi * TRANSIENT_FREQUENCY_HZ * number
    sine = 2.0 / len(time) * sum(value * math.sin(omega * sample) for sample, value in zip(time, values, strict=True))
    cosine = 2.0 / len(time) * sum(value * math.cos(omega * sample) for sample, value in zip(time, values, strict=True))
    return math.hypot(sine, cosine), math.degrees(math.atan2(cosine, sine))


def simulate(candidate: Candidate, artifact_root: Path) -> dict[str, float | bool]:
    if not MODEL_PATH.is_file() or hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != MODEL_SHA256:
        raise InfrastructureError("authoritative CMOS model is missing or altered")
    artifact_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODEL_PATH, artifact_root / "cmos018-s112b.lib")
    deck = f"""Open-feedback CMOS amplifier private open-feedback op-amp fixture
.include cmos018-s112b.lib
{candidate.source}
VDD vdd 0 1
VSS vss 0 -1
VIN in 0 DC 0 AC 1 SIN(0 {TRANSIENT_INPUT_AMPLITUDE_V} {TRANSIENT_FREQUENCY_HZ})
XDUT in out vdd vss candidate
.temp 27
.options method=gear reltol=1e-5 abstol=1e-12 vntol=1e-8 trtol=7
.control
set wr_vecnames
set wr_singlescale
op
let first_branch_a = abs(@m.xdut.{candidate.first_branch_device_a}[id])
let first_branch_b = abs(@m.xdut.{candidate.first_branch_device_b}[id])
let tail_branch = abs(@m.xdut.{candidate.tail_branch_device}[id])
let second_branch_a = abs(@m.xdut.{candidate.second_branch_device_a}[id])
let second_branch_b = abs(@m.xdut.{candidate.second_branch_device_b}[id])
let bias_branch = abs(@m.xdut.{candidate.bias_branch_device}[id])
wrdata bias.dat first_branch_a first_branch_b tail_branch second_branch_a second_branch_b bias_branch
ac dec {AC_POINTS_PER_DECADE} {AC_START_HZ} {AC_STOP_HZ}
wrdata ac.dat v(out)
tran {TRANSIENT_STEP_SECONDS} {TRANSIENT_STOP_SECONDS} {TRANSIENT_START_SECONDS}
wrdata tran.dat v(in) v(out)
quit
.endc
.end
"""
    deck_path = artifact_root / "test.cir"
    log_path = artifact_root / "ngspice.log"
    outputs = [artifact_root / name for name in ("bias.dat", "ac.dat", "tran.dat")]
    for path in outputs:
        path.unlink(missing_ok=True)
    deck_path.write_text(deck, encoding="utf-8")
    try:
        completed = subprocess.run(["ngspice", "-b", "-o", str(log_path), str(deck_path)], cwd=artifact_root, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SimulationError("Ngspice exceeded the 120 second limit") from exc
    if completed.returncode != 0 or not all(path.is_file() for path in outputs):
        log = log_path.read_text(errors="replace") if log_path.is_file() else completed.stderr
        raise SimulationError(f"Ngspice failed: {log.strip()[-2000:]}")

    bias = read_table(outputs[0], 7, 1)[-1]
    ac = read_table(outputs[1], 3, 1_400)
    frequency = [row[0] for row in ac]
    values = [complex(row[1], row[2]) for row in ac]
    gain_index = min(range(len(frequency)), key=lambda index: abs(frequency[index] - GAIN_FREQUENCY_HZ))
    gain = abs(values[gain_index])
    low_frequency_gain = abs(values[0])
    threshold = low_frequency_gain / math.sqrt(2.0)
    upper = None
    for index in range(gain_index + 1, len(frequency)):
        left, right = abs(values[index - 1]), abs(values[index])
        if left >= threshold > right:
            upper = interpolate_log_x(frequency[index - 1], left, frequency[index], right, threshold)
            break
    if upper is None:
        raise SimulationError("output has no descending upper 3 dB crossing")

    transient = [row for row in read_table(outputs[2], 3, 4_900) if row[0] < TRANSIENT_STOP_SECONDS - 0.5e-9]
    if len(transient) < 4_900:
        raise SimulationError("Ngspice produced too few settled transient samples")
    time = [row[0] for row in transient]
    inputs = [row[1] for row in transient]
    outputs_v = [row[2] for row in transient]
    mean = sum(outputs_v) / len(outputs_v)
    centered = [value - mean for value in outputs_v]
    input_fundamental, input_phase = harmonic(time, inputs, 1)
    harmonics = [harmonic(time, centered, number) for number in range(1, 6)]
    if input_fundamental <= 0.0 or harmonics[0][0] <= 0.0:
        raise SimulationError("transient fundamental amplitude is zero")
    phase = (harmonics[0][1] - input_phase + 180.0) % 360.0 - 180.0
    return {
        "gain_10mhz_v_per_v": gain,
        "low_frequency_gain_v_per_v": low_frequency_gain,
        "upper_3db_hz": upper,
        "transient_gain_v_per_v": harmonics[0][0] / input_fundamental,
        "transient_phase_degrees": phase,
        "thd_percent": 100.0 * math.sqrt(sum(item[0] ** 2 for item in harmonics[1:])) / harmonics[0][0],
        "loaded_to_unloaded_gain_ratio": gain / UNLOADED_GAIN_REFERENCE,
        "first_stage_branch_a_current_a": bias[1],
        "first_stage_branch_b_current_a": bias[2],
        "tail_branch_current_a": bias[3],
        "second_stage_branch_a_current_a": bias[4],
        "second_stage_branch_b_current_a": bias[5],
        "bias_branch_current_a": bias[6],
    }


def distance_reward(distance: float) -> float:
    if distance <= 0.25:
        return 1.0
    if distance >= 1.0:
        return 0.0
    return (1.0 - distance) / 0.75


def central_reward(value: float, target: float) -> float:
    return distance_reward(abs(value - target) / abs(target))


def higher_is_better_reward(value: float, limit: float) -> float:
    return distance_reward(max(0.0, (limit - value) / abs(limit)))


def lower_is_better_reward(value: float, limit: float) -> float:
    return distance_reward(max(0.0, (value - limit) / abs(limit)))


def interval_reward(value: float, lower: float, upper: float) -> float:
    if value < lower:
        distance = (lower - value) / abs(lower)
    elif value > upper:
        distance = (value - upper) / abs(upper)
    else:
        distance = 0.0
    return distance_reward(distance)


def metric_rewards(measurements: dict[str, float | bool]) -> dict[str, float]:
    return {
        "gain_10mhz": central_reward(float(measurements["gain_10mhz_v_per_v"]), GAIN_TARGET),
        "upper_3db": higher_is_better_reward(float(measurements["upper_3db_hz"]), UPPER_CUTOFF_LIMIT_HZ),
        "transient_gain": central_reward(float(measurements["transient_gain_v_per_v"]), TRANSIENT_GAIN_TARGET),
        "transient_thd": lower_is_better_reward(float(measurements["thd_percent"]), THD_LIMIT_PERCENT),
        "loaded_to_unloaded_gain_ratio": interval_reward(
            float(measurements["loaded_to_unloaded_gain_ratio"]),
            LOADED_RATIO_MINIMUM,
            LOADED_RATIO_MAXIMUM,
        ),
    }


def invalid_result(outcome: str, code: str, error: str) -> dict[str, object]:
    return {
        "outcome": outcome, "artifact_evaluable": False, "production_pass": False,
        "final_reward": 0.0, "failure_codes": [code], "error": error,
        "measurements": {}, "structural_rewards": {name: 0.0 for name in STRUCTURAL_CRITERIA},
        "metric_rewards": {},
    }


def grade_submission(candidate_path: Path, artifact_root: Path) -> dict[str, object]:
    try:
        candidate = parse_candidate(candidate_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, CandidateError) as exc:
        return invalid_result("candidate_invalid", "S112B-CANDIDATE-INVALID", str(exc))
    if shutil.which("ngspice") is None:
        return invalid_result("infrastructure_error", "S112B-NGSPICE-MISSING", "ngspice executable is unavailable")
    try:
        measurements = simulate(candidate, artifact_root)
    except InfrastructureError as exc:
        return invalid_result("infrastructure_error", "S112B-MODEL-INVALID", str(exc))
    except (OSError, SimulationError, subprocess.SubprocessError) as exc:
        return invalid_result("simulation_failed", "S112B-SIMULATION-FAILED", str(exc))
    structural = {name: 1.0 for name in STRUCTURAL_CRITERIA}
    metrics = metric_rewards(measurements)
    failure_codes = [f"S112B-{name.replace('_', '-').upper()}" for name, reward in metrics.items() if reward < 1.0]
    rewards = [*structural.values(), *metrics.values()]
    final_reward = sum(rewards) / len(rewards)
    production_pass = final_reward == 1.0
    return {
        "outcome": "passed" if production_pass else "requirements_failed",
        "artifact_evaluable": True, "production_pass": production_pass,
        "final_reward": final_reward, "failure_codes": failure_codes, "error": None,
        "measurements": measurements, "structural_rewards": structural,
        "metric_rewards": metrics,
        "targets": {
            "gain_10mhz_v_per_v": GAIN_TARGET,
            "upper_3db_limit_hz": UPPER_CUTOFF_LIMIT_HZ,
            "transient_gain_v_per_v": TRANSIENT_GAIN_TARGET,
            "thd_limit_percent": THD_LIMIT_PERCENT,
            "unloaded_gain_reference_v_per_v": UNLOADED_GAIN_REFERENCE,
            "loaded_ratio_minimum": LOADED_RATIO_MINIMUM,
            "loaded_ratio_maximum": LOADED_RATIO_MAXIMUM,
        },
    }
