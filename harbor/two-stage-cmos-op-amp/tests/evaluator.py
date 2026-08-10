from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


MODEL_PATH = Path(os.environ.get("EESIM_CMOS_MODEL", "/opt/eesim/models/cmos018.lib"))
MODEL_SHA256 = "02094fb8acf1927012eda6dc59941cbf236ef8f7544bd39e166b3e202f2bb8ec"
EXPECTED_PORTS = ("inp", "inn", "out", "vdd", "vss")
MAX_CANDIDATE_BYTES = 100_000
MAX_ELEMENTS = 256
AC_POINTS_PER_DECADE = 400
AC_START_HZ = 1.0
AC_STOP_HZ = 100.0e6
TRANSIENT_STEP_SECONDS = 1.0e-6
TRANSIENT_STOP_SECONDS = 20.0e-3
TRANSIENT_START_SECONDS = 15.0e-3
TRANSIENT_INPUT_AMPLITUDE_V = 1.0e-3
TRANSIENT_FREQUENCY_HZ = 1_000.0
CM_OUTPUT_NEG1_TARGET_V = -0.883971454
CM_OUTPUT_ZERO_TARGET_V = -0.524603301
CM_OUTPUT_POS1_TARGET_V = -0.180306539
GAIN_TARGET = 3079.2830706475884
UPPER_CUTOFF_LIMIT_HZ = 6_252_390.225087503
OUTPUT_SWING_TARGET_VPP = 1.775361339
THD_LIMIT_PERCENT = 35.301701522402794
STRUCTURAL_CRITERIA = (
    "exact_interface",
    "accepted_bounded_netlist",
    "required_cmos_topology_and_bias",
    "allowed_elements_and_models",
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


def parse_value(raw: str) -> float:
    match = NUMBER.fullmatch(raw)
    if not match:
        raise CandidateError(f"invalid SPICE value: {raw}")
    value = float(match.group(1))
    suffix = (match.group(2) or "").casefold()
    if suffix:
        value *= SUFFIXES[suffix]
    if not math.isfinite(value) or abs(value) > 1e12:
        raise CandidateError(f"SPICE value is out of range: {raw}")
    return value


def validate_node(raw: str) -> str:
    if not NODE.fullmatch(raw):
        raise CandidateError(f"invalid node name: {raw}")
    return raw.casefold()


def validate_connectivity(elements: list[Element]) -> None:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for element in elements:
        for node in element.nodes:
            find(node)
        for node in element.nodes[1:]:
            union(element.nodes[0], node)
    for port in EXPECTED_PORTS:
        if port not in parent:
            raise CandidateError(f"port {port} is not connected")
    root = find("inp")
    if any(find(port) != root for port in EXPECTED_PORTS):
        raise CandidateError("all candidate ports must belong to one connected circuit")
    orphaned = sorted(node for node in parent if find(node) != root)
    if orphaned:
        raise CandidateError(f"disconnected internal node: {orphaned[0]}")


def require_topology(elements: list[Element]) -> None:
    mos = [element for element in elements if element.kind == "m"]
    resistors = [element for element in elements if element.kind == "r"]

    def reaches_output(drain: str) -> bool:
        if drain == "out":
            return True
        return any(set(resistor.nodes) == {drain, "out"} for resistor in resistors)

    if len(mos) < 8:
        raise CandidateError("the two-stage op amp must contain at least eight MOSFETs")
    nmos = [element for element in mos if element.model == "nmos4"]
    pmos = [element for element in mos if element.model == "pmos4"]
    pairs: list[tuple[Element, Element]] = []
    for left in nmos:
        for right in nmos:
            if left.nodes[1] == "inn" and right.nodes[1] == "inp" and left.nodes[2] == right.nodes[2]:
                pairs.append((left, right))
    if not pairs:
        raise CandidateError("an NMOS differential input pair with a shared source is required")
    for left, right in pairs:
        left_drain, right_drain = left.nodes[0], right.nodes[0]
        common_source = left.nodes[2]
        for diode in pmos:
            if diode.nodes[0] != diode.nodes[1] or diode.nodes[2:] != ("vdd", "vdd"):
                continue
            for mirror in pmos:
                if mirror is diode or mirror.nodes[1] != diode.nodes[1] or mirror.nodes[2:] != ("vdd", "vdd"):
                    continue
                if {diode.nodes[0], mirror.nodes[0]} != {left_drain, right_drain}:
                    continue
                first_output = mirror.nodes[0]
                second = [m for m in pmos if reaches_output(m.nodes[0]) and m.nodes[1] == first_output and m.nodes[2:] == ("vdd", "vdd")]
                output_loads = [m for m in nmos if reaches_output(m.nodes[0]) and m.nodes[2] == "vss"]
                tail = [m for m in nmos if m.nodes[0] == common_source and m.nodes[2] == "vss"]
                if not second or not output_loads or not tail:
                    continue
                bias_nodes = {m.nodes[1] for m in [*output_loads, *tail]}
                for bias in nmos:
                    if bias.nodes[0] == bias.nodes[1] and bias.nodes[2] == "vss" and bias.nodes[1] in bias_nodes:
                        return
    raise CandidateError("required active-load, common-source, and current-mirror bias topology is missing")


def parse_candidate(source: str) -> Candidate:
    if not source.strip():
        raise CandidateError("submission is empty")
    if len(source.encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateError(f"submission exceeds {MAX_CANDIDATE_BYTES} bytes")
    logical = [line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith("*")]
    if len(logical) < 2:
        raise CandidateError("submission must contain the candidate subcircuit")
    if [token.casefold() for token in logical[0].split()] != [".subckt", "candidate", *EXPECTED_PORTS]:
        raise CandidateError("header must be '.subckt candidate inp inn out vdd vss'")
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
            nodes = tuple(validate_node(node) for node in tokens[1:5])
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
            nodes = tuple(validate_node(node) for node in tokens[1:3])
            value = parse_value(tokens[3])
            if value <= 0.0 or nodes[0] == nodes[1]:
                raise CandidateError(f"{instance} must have a positive value and distinct nodes")
            elements.append(Element(instance, kind, nodes, value=value))
        elif kind == "i":
            if instance.casefold() != "iref":
                raise CandidateError("the only current source must be named IREF")
            if len(tokens) == 4:
                raw = tokens[3]
            elif len(tokens) == 5 and tokens[3].casefold() == "dc":
                raw = tokens[4]
            else:
                raise CandidateError("IREF must be an independent DC current source")
            nodes = tuple(validate_node(node) for node in tokens[1:3])
            value = parse_value(raw)
            if nodes[0] != "vdd" or nodes[1] in EXPECTED_PORTS or not math.isclose(value, 200e-6, rel_tol=1e-12):
                raise CandidateError("IREF must supply 200 uA from vdd to an internal bias node")
            elements.append(Element(instance, kind, nodes, value=value))
        else:
            raise CandidateError(f"unsupported element: {instance}")
    if not elements or len(elements) > MAX_ELEMENTS:
        raise CandidateError("submission has no elements or exceeds the element limit")
    if sum(element.kind == "i" for element in elements) != 1:
        raise CandidateError("exactly one 200 uA IREF source is required")
    require_topology(elements)
    validate_connectivity(elements)
    return Candidate(source=source.rstrip() + "\n", elements=tuple(elements))


def read_table(path: Path, columns: int, minimum_rows: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if len(fields) < columns:
            continue
        try:
            row = [float(value) for value in fields[:columns]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in row):
            raise SimulationError("Ngspice produced a nonfinite value")
        rows.append(row)
    if len(rows) < minimum_rows:
        raise SimulationError(f"Ngspice produced too few rows in {path.name}")
    return rows


def interpolate_log_x(x0: float, y0: float, x1: float, y1: float, target: float) -> float:
    if y1 == y0:
        return x1
    fraction = (target - y0) / (y1 - y0)
    return math.exp(math.log(x0) + fraction * (math.log(x1) - math.log(x0)))


def harmonic_amplitude(time: list[float], values: list[float], harmonic: int) -> tuple[float, float]:
    angular = 2.0 * math.pi * TRANSIENT_FREQUENCY_HZ * harmonic
    count = len(time)
    sine = sum(value * math.sin(angular * sample) for sample, value in zip(time, values, strict=True)) * 2.0 / count
    cosine = sum(value * math.cos(angular * sample) for sample, value in zip(time, values, strict=True)) * 2.0 / count
    return math.hypot(sine, cosine), math.degrees(math.atan2(cosine, sine))


def simulate(candidate: Candidate, artifact_root: Path) -> dict[str, float]:
    if not MODEL_PATH.is_file():
        raise InfrastructureError(f"authoritative model is missing: {MODEL_PATH}")
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != MODEL_SHA256:
        raise InfrastructureError("authoritative CMOS model hash does not match")
    artifact_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODEL_PATH, artifact_root / "cmos018.lib")
    deck = f"""Two-stage CMOS op amp two-stage CMOS op amp private fixture
.include cmos018.lib
{candidate.source}
VDD vdd 0 1
VSS vss 0 -1
VCM vcm 0 0
VINP inp vcm DC 0 AC 1 SIN(0 {TRANSIENT_INPUT_AMPLITUDE_V} {TRANSIENT_FREQUENCY_HZ})
VINN inn vcm DC 0 AC -1 SIN(0 {-TRANSIENT_INPUT_AMPLITUDE_V} {TRANSIENT_FREQUENCY_HZ})
XDUT inp inn out vdd vss candidate
.temp 27
.control
set wr_vecnames
set wr_singlescale
dc VCM -1 1 0.001
wrdata cm.dat v(out)
ac dec {AC_POINTS_PER_DECADE} {AC_START_HZ} {AC_STOP_HZ}
wrdata ac.dat v(out)
tran {TRANSIENT_STEP_SECONDS} {TRANSIENT_STOP_SECONDS} {TRANSIENT_START_SECONDS}
wrdata tran.dat v(inp) v(inn) v(out)
quit
.endc
.end
"""
    deck_path = artifact_root / "test.cir"
    log_path = artifact_root / "ngspice.log"
    outputs = [artifact_root / name for name in ("cm.dat", "ac.dat", "tran.dat")]
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

    common_mode = read_table(outputs[0], 2, 2_000)
    common = {target: min(common_mode, key=lambda row: abs(row[0] - target))[1] for target in (-1.0, 0.0, 1.0)}
    ac = read_table(outputs[1], 3, 3_000)
    frequency = [row[0] for row in ac]
    values = [complex(row[1], row[2]) / 2.0 for row in ac]
    index_1khz = min(range(len(frequency)), key=lambda index: abs(frequency[index] - 1_000.0))
    gain = abs(values[index_1khz])
    threshold = gain / math.sqrt(2.0)
    upper: float | None = None
    for index in range(index_1khz + 1, len(frequency)):
        left, right = abs(values[index - 1]), abs(values[index])
        if left >= threshold > right:
            upper = interpolate_log_x(frequency[index - 1], left, frequency[index], right, threshold)
            break
    if upper is None:
        raise SimulationError("output has no falling upper 3 dB crossing")

    transient = [row for row in read_table(outputs[2], 4, 4_900) if row[0] < TRANSIENT_STOP_SECONDS - 0.5e-9]
    if len(transient) < 4_900:
        raise SimulationError("Ngspice produced too few settled transient samples")
    time = [row[0] for row in transient]
    differential_input = [row[1] - row[2] for row in transient]
    output = [row[3] for row in transient]
    output_mean = sum(output) / len(output)
    centered_output = [value - output_mean for value in output]
    input_fundamental = harmonic_amplitude(time, differential_input, 1)[0]
    harmonics = [harmonic_amplitude(time, centered_output, harmonic)[0] for harmonic in range(1, 6)]
    if input_fundamental <= 0.0 or harmonics[0] <= 0.0:
        raise SimulationError("transient fundamental amplitude is zero")
    return {
        "output_at_vcm_neg1_v": common[-1.0],
        "output_at_vcm_zero_v": common[0.0],
        "output_at_vcm_pos1_v": common[1.0],
        "differential_gain_1khz_v_per_v": gain,
        "upper_3db_hz": upper,
        "transient_gain_v_per_v": harmonics[0] / input_fundamental,
        "output_swing_peak_to_peak_v": max(output) - min(output),
        "thd_percent": 100.0 * math.sqrt(sum(value * value for value in harmonics[1:])) / harmonics[0],
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


def metric_rewards(measurements: dict[str, float]) -> dict[str, float]:
    return {
        "output_at_vcm_neg1": central_reward(measurements["output_at_vcm_neg1_v"], CM_OUTPUT_NEG1_TARGET_V),
        "output_at_vcm_zero": central_reward(measurements["output_at_vcm_zero_v"], CM_OUTPUT_ZERO_TARGET_V),
        "output_at_vcm_pos1": central_reward(measurements["output_at_vcm_pos1_v"], CM_OUTPUT_POS1_TARGET_V),
        "differential_gain_1khz": central_reward(measurements["differential_gain_1khz_v_per_v"], GAIN_TARGET),
        "upper_3db": higher_is_better_reward(measurements["upper_3db_hz"], UPPER_CUTOFF_LIMIT_HZ),
        "transient_output_swing": central_reward(measurements["output_swing_peak_to_peak_v"], OUTPUT_SWING_TARGET_VPP),
        "transient_thd": lower_is_better_reward(measurements["thd_percent"], THD_LIMIT_PERCENT),
    }


def invalid_result(outcome: str, code: str, error: str) -> dict[str, object]:
    return {
        "outcome": outcome, "artifact_evaluable": False, "production_pass": False,
        "final_reward": 0.0, "failure_codes": [code], "error": error,
        "measurements": {}, "structural_rewards": {criterion: 0.0 for criterion in STRUCTURAL_CRITERIA},
        "metric_rewards": {},
    }


def grade_submission(candidate_path: Path, artifact_root: Path) -> dict[str, object]:
    try:
        candidate = parse_candidate(candidate_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, CandidateError) as exc:
        return invalid_result("candidate_invalid", "S92-CANDIDATE-INVALID", str(exc))
    if shutil.which("ngspice") is None:
        return invalid_result("infrastructure_error", "S92-NGSPICE-MISSING", "ngspice executable is unavailable")
    try:
        measurements = simulate(candidate, artifact_root)
    except InfrastructureError as exc:
        return invalid_result("infrastructure_error", "S92-MODEL-INVALID", str(exc))
    except (OSError, SimulationError, subprocess.SubprocessError) as exc:
        return invalid_result("simulation_failed", "S92-SIMULATION-FAILED", str(exc))
    structural = {criterion: 1.0 for criterion in STRUCTURAL_CRITERIA}
    metrics = metric_rewards(measurements)
    failure_codes = [f"S92-{name.replace('_', '-').upper()}" for name, reward in metrics.items() if reward < 1.0]
    all_rewards = [*structural.values(), *metrics.values()]
    final_reward = sum(all_rewards) / len(all_rewards)
    production_pass = math.isclose(final_reward, 1.0, rel_tol=0.0, abs_tol=1e-12)
    return {
        "outcome": "passed" if production_pass else "requirements_failed",
        "artifact_evaluable": True, "production_pass": production_pass,
        "final_reward": final_reward, "failure_codes": failure_codes, "error": None,
        "measurements": measurements, "structural_rewards": structural,
        "metric_rewards": metrics,
        "targets": {
            "output_at_vcm_neg1_v": CM_OUTPUT_NEG1_TARGET_V,
            "output_at_vcm_zero_v": CM_OUTPUT_ZERO_TARGET_V,
            "output_at_vcm_pos1_v": CM_OUTPUT_POS1_TARGET_V,
            "differential_gain_1khz_v_per_v": GAIN_TARGET,
            "upper_3db_limit_hz": UPPER_CUTOFF_LIMIT_HZ,
            "output_swing_peak_to_peak_v": OUTPUT_SWING_TARGET_VPP,
            "thd_limit_percent": THD_LIMIT_PERCENT,
        },
    }
