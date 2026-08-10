from __future__ import annotations

import cmath
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MODEL_DIR = Path(os.environ.get("EESIM_MODEL_DIR", "/opt/eesim/models"))
MAX_CANDIDATE_BYTES = 50_000
EXPECTED_PORTS = ("vinp", "vinn", "vout", "vdd", "vb1", "vb2", "vss")
CORNERS = ("tt", "ff", "ss")
METRIC_DIRECTIONS = {
    "positive_slew_rate_v_per_s": "higher",
    "negative_slew_rate_v_per_s": "higher",
    "unity_gain_frequency_hz": "higher",
    "phase_margin_degrees": "higher",
    "quiescent_current_a": "lower",
}
REFERENCE_CORNER_MEASUREMENTS = {
    "TT": {
        "positive_slew_rate_v_per_s": 102.1468273604814e6,
        "negative_slew_rate_v_per_s": 106.0904078136638e6,
        "unity_gain_frequency_hz": 184.4537070617503e6,
        "phase_margin_degrees": 54.318910505911774,
        "quiescent_current_a": 396.113e-6,
    },
    "FF": {
        "positive_slew_rate_v_per_s": 100.73335533274125e6,
        "negative_slew_rate_v_per_s": 104.27404302345525e6,
        "unity_gain_frequency_hz": 172.16687627066273e6,
        "phase_margin_degrees": 47.77257207546759,
        "quiescent_current_a": 399.573e-6,
    },
    "SS": {
        "positive_slew_rate_v_per_s": 98.94801137660436e6,
        "negative_slew_rate_v_per_s": 101.90277753751182e6,
        "unity_gain_frequency_hz": 175.24476572938463e6,
        "phase_margin_degrees": 53.628344197769266,
        "quiescent_current_a": 395.474e-6,
    },
}
ZERO_CREDIT_SPREAD_FRACTION = 0.25
CIRCUIT_COLLAPSE_SPREAD_MULTIPLIER = 1.0


def derive_reference_scale() -> dict[str, dict[str, float | str]]:
    """Derive each metric's best and worst anchors from raw reference runs."""
    scale: dict[str, dict[str, float | str]] = {}
    for metric, direction in METRIC_DIRECTIONS.items():
        values = [corner[metric] for corner in REFERENCE_CORNER_MEASUREMENTS.values()]
        best = max(values) if direction == "higher" else min(values)
        worst = min(values) if direction == "higher" else max(values)
        scale[metric] = {"best": best, "worst": worst, "direction": direction}
    return scale


REFERENCE_SCALE = derive_reference_scale()
LIMITS = {metric: float(scale["worst"]) for metric, scale in REFERENCE_SCALE.items()}
SUFFIXES = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}
NODE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*|0)$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
NUMBER = re.compile(
    r"^([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?)(meg|[tgkmunpf])?$",
    re.IGNORECASE,
)


class CandidateError(ValueError):
    pass


class SimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Mos:
    name: str
    drain: str
    gate: str
    source: str
    body: str
    model: str
    width_m: float
    length_m: float


@dataclass(frozen=True)
class Candidate:
    source: str
    mos: tuple[Mos, ...]
    bias_current_a: float


def parse_value(raw: str) -> float:
    match = NUMBER.fullmatch(raw)
    if not match:
        raise CandidateError(f"invalid SPICE value: {raw}")
    value = float(match.group(1))
    suffix = (match.group(2) or "").casefold()
    if suffix:
        value *= SUFFIXES[suffix]
    if not math.isfinite(value):
        raise CandidateError(f"nonfinite SPICE value: {raw}")
    return value


def parse_candidate(source: str) -> Candidate:
    if not source.strip():
        raise CandidateError("submission is empty")
    if len(source.encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateError(f"submission exceeds {MAX_CANDIDATE_BYTES} bytes")
    logical = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("*")
    ]
    if len(logical) < 2:
        raise CandidateError("submission must contain the candidate subcircuit")
    header = [token.casefold() for token in logical[0].split()]
    if header != [".subckt", "candidate", *EXPECTED_PORTS]:
        raise CandidateError(
            "subcircuit header must be '.subckt candidate vinp vinn vout vdd vb1 vb2 vss'"
        )
    ending = [token.casefold() for token in logical[-1].split()]
    if ending not in ([".ends"], [".ends", "candidate"]):
        raise CandidateError("submission must end with '.ends candidate'")

    names: set[str] = set()
    mos: list[Mos] = []
    resistor_count = 0
    capacitor_count = 0
    bias_current: float | None = None
    for line in logical[1:-1]:
        tokens = line.split()
        instance = tokens[0]
        folded = instance.casefold()
        if not NAME.fullmatch(instance):
            raise CandidateError(f"invalid instance name: {instance}")
        if folded in names:
            raise CandidateError(f"duplicate instance name: {instance}")
        names.add(folded)
        kind = instance[0].casefold()
        if kind == "m":
            if len(tokens) != 8:
                raise CandidateError(
                    f"{instance} must have four nodes, a model, w, and l"
                )
            drain, gate, source_node, body = tokens[1:5]
            if not all(NODE.fullmatch(node) for node in (drain, gate, source_node, body)):
                raise CandidateError(f"{instance} contains an invalid node name")
            if any(node.casefold() in {"vb1", "vb2"} for node in (drain, source_node, body)):
                raise CandidateError("vb1 and vb2 may connect only to MOSFET gates")
            model = tokens[5].casefold()
            if model not in {"nmos", "pmos"}:
                raise CandidateError(f"{instance} must use model nmos or pmos")
            parameters: dict[str, float] = {}
            for token in tokens[6:]:
                if "=" not in token:
                    raise CandidateError(f"invalid parameter on {instance}: {token}")
                key, raw = token.split("=", 1)
                key = key.casefold()
                if key in parameters or key not in {"w", "l"}:
                    raise CandidateError(f"invalid parameter on {instance}: {token}")
                parameters[key] = parse_value(raw)
            if set(parameters) != {"w", "l"}:
                raise CandidateError(f"{instance} must specify w and l")
            width = parameters["w"]
            length = parameters["l"]
            if not 0.2e-6 <= width <= 1000e-6:
                raise CandidateError(f"{instance} width must be from 0.2u through 1000u")
            if not math.isclose(length, 0.4e-6, rel_tol=0.0, abs_tol=1e-15):
                raise CandidateError(f"{instance} length must equal 0.4u")
            mos.append(Mos(instance, drain, gate, source_node, body, model, width, length))
        elif kind in {"r", "c"}:
            if len(tokens) != 4:
                raise CandidateError(f"{instance} must have two nodes and one value")
            if not NODE.fullmatch(tokens[1]) or not NODE.fullmatch(tokens[2]):
                raise CandidateError(f"{instance} contains an invalid node name")
            if tokens[1].casefold() in {"vb1", "vb2"} or tokens[2].casefold() in {"vb1", "vb2"}:
                raise CandidateError("vb1 and vb2 may connect only to MOSFET gates")
            value = parse_value(tokens[3])
            if value <= 0.0:
                raise CandidateError(f"{instance} value must be positive")
            if kind == "r":
                resistor_count += 1
            else:
                capacitor_count += 1
        elif folded == "ibias":
            if len(tokens) != 4 or tokens[2].casefold() != "vss":
                raise CandidateError("IBIAS must have the form 'IBIAS <node> vss <value>'")
            if not NODE.fullmatch(tokens[1]):
                raise CandidateError("IBIAS contains an invalid node name")
            if tokens[1].casefold() in set(EXPECTED_PORTS):
                raise CandidateError("IBIAS positive terminal must be an internal node")
            bias_current = parse_value(tokens[3])
            if not 1e-6 <= bias_current <= 400e-6:
                raise CandidateError("IBIAS must be from 1u through 400u")
        else:
            raise CandidateError(f"unsupported element: {instance}")

    if not 4 <= len(mos) <= 64:
        raise CandidateError("submission must contain 4 through 64 MOSFETs")
    if resistor_count > 16 or capacitor_count > 16:
        raise CandidateError("submission exceeds the resistor or capacitor count limit")
    if bias_current is None:
        raise CandidateError("submission must contain one current source named IBIAS")
    # K=2 is an electrical relationship, not an instance-naming or exact-node
    # convention. Accept any same-type MOS pair with a shared mirror gate and a
    # 2:1 width ratio. Their sources may connect to the same supply through
    # proportionally scaled degeneration resistors, which is still a legal
    # implementation of the stated mirror ratio.
    mirror_pair_found = any(
        reference is not output
        and (
            reference.gate.casefold(),
            reference.body.casefold(),
            reference.model,
        )
        == (
            output.gate.casefold(),
            output.body.casefold(),
            output.model,
        )
        and math.isclose(output.width_m, 2.0 * reference.width_m, rel_tol=1e-9)
        for reference in mos
        for output in mos
    )
    if not mirror_pair_found:
        raise CandidateError(
            "submission must contain a K=2 MOS mirror pair sharing gate, body, and model"
        )
    return Candidate(source=source.rstrip() + "\n", mos=tuple(mos), bias_current_a=bias_current)


def run_ngspice(deck: str, run_dir: Path, expected: Sequence[str]) -> str:
    run_dir.mkdir(parents=True, exist_ok=True)
    for source in MODEL_DIR.glob("p18_*.inc"):
        shutil.copy2(source, run_dir / source.name)
    deck_path = run_dir / "test.cir"
    log_path = run_dir / "ngspice.log"
    deck_path.write_text(deck, encoding="utf-8")
    try:
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log_path), str(deck_path)],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulationError("Ngspice exceeded the 120 second job limit") from exc
    log = log_path.read_text(errors="replace") if log_path.is_file() else completed.stderr
    missing = [name for name in expected if not (run_dir / name).is_file()]
    if completed.returncode != 0 or missing:
        detail = log.strip()[-2000:]
        raise SimulationError(
            f"Ngspice failed with code {completed.returncode}; missing={missing}; {detail}"
        )
    return log


def fixture_prefix(candidate: Candidate, corner: str) -> str:
    return f"""Current-mirror op-amp private fixture
.include p18_cmos_models_{corner}.inc
{candidate.source}
VDD vdd 0 1.8
VB1 vb1 0 1.4
VB2 vb2 0 0.6
XDUT vinp vinn vout vdd vb1 vb2 0 candidate
CLOAD vout 0 2.5p
.temp 27
"""


def read_real_table(path: Path, vectors: int) -> tuple[list[float], list[list[float]]]:
    independent: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text().splitlines():
        fields = raw.split()
        if len(fields) < 1 + vectors:
            continue
        try:
            values = [float(value) for value in fields[: 1 + vectors]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in values):
            raise SimulationError(f"nonfinite value in {path.name}")
        independent.append(values[0])
        for index in range(vectors):
            outputs[index].append(values[index + 1])
    if not independent:
        raise SimulationError(f"no numeric data in {path.name}")
    return independent, outputs


def read_complex_table(path: Path, vectors: int) -> tuple[list[float], list[list[complex]]]:
    frequency: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text().splitlines():
        fields = raw.split()
        if len(fields) < 1 + 2 * vectors:
            continue
        try:
            values = [float(value) for value in fields[: 1 + 2 * vectors]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in values):
            raise SimulationError(f"nonfinite value in {path.name}")
        frequency.append(values[0])
        for index in range(vectors):
            outputs[index].append(complex(values[1 + 2 * index], values[2 + 2 * index]))
    if len(frequency) < 100:
        raise SimulationError(f"too few AC samples in {path.name}")
    return frequency, outputs


def interpolate_crossing(
    x0: float, y0: float, x1: float, y1: float, target: float, logarithmic_x: bool
) -> float:
    if y1 == y0:
        return x1
    fraction = (target - y0) / (y1 - y0)
    if logarithmic_x:
        return math.exp(math.log(x0) + fraction * (math.log(x1) - math.log(x0)))
    return x0 + fraction * (x1 - x0)


def loop_metrics(frequency: Sequence[float], values: Sequence[complex]) -> tuple[float, float]:
    magnitude_db = [20.0 * math.log10(max(abs(value), 1e-300)) for value in values]
    phase: list[float] = []
    for value in values:
        angle = cmath.phase(value)
        if phase:
            while angle - phase[-1] > math.pi:
                angle -= 2.0 * math.pi
            while angle - phase[-1] < -math.pi:
                angle += 2.0 * math.pi
        phase.append(angle)
    crossings: list[tuple[float, float]] = []
    for index in range(1, len(frequency)):
        if magnitude_db[index - 1] >= 0.0 > magnitude_db[index]:
            crossing = interpolate_crossing(
                frequency[index - 1],
                magnitude_db[index - 1],
                frequency[index],
                magnitude_db[index],
                0.0,
                True,
            )
            left = magnitude_db[index - 1]
            right = magnitude_db[index]
            fraction = 1.0 if left == right else left / (left - right)
            crossing_phase = phase[index - 1] + fraction * (phase[index] - phase[index - 1])
            crossings.append((crossing, 180.0 + math.degrees(crossing_phase)))
    if not crossings:
        raise SimulationError("loop gain has no descending 0 dB crossing")
    return crossings[0][0], min(margin for _, margin in crossings)


def threshold_time(
    time: Sequence[float], values: Sequence[float], threshold: float, start: float, stop: float, rising: bool
) -> float:
    for index in range(1, len(time)):
        if time[index] < start or time[index] > stop:
            continue
        left = values[index - 1]
        right = values[index]
        crossed = left <= threshold < right if rising else left >= threshold > right
        if crossed:
            return interpolate_crossing(time[index - 1], left, time[index], right, threshold, False)
    raise SimulationError(f"output did not cross {threshold:.3g} V")


def parse_print_values(log: str) -> dict[str, float]:
    values: dict[str, float] = {}
    pattern = re.compile(r"^\s*([^=\s]+)\s*=\s*([+-]?[0-9.]+(?:e[+-]?[0-9]+)?)\s*$", re.IGNORECASE)
    for line in log.splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1).casefold()] = float(match.group(2))
    return values


def simulate_corner(candidate: Candidate, corner: str, root: Path) -> dict[str, float | str]:
    corner_root = root / corner
    minimum_saturation = math.inf
    quiescent_current = 0.0
    worst_device = ""
    for input_voltage in (0.75, 1.0, 1.25):
        probes = ["v(vout)", "i(VDD)"]
        for device in candidate.mos:
            hierarchy = f"@m.xdut.{device.name.casefold()}"
            probes.extend((f"{hierarchy}[vds]", f"{hierarchy}[vdsat]"))
        deck = fixture_prefix(candidate, corner) + f"""VIN vinp 0 {input_voltage:.12g}
RFB vout vinn 1m
.control
op
print {' '.join(probes)}
quit
.endc
.end
"""
        log = run_ngspice(deck, corner_root / f"op-{input_voltage:.2f}", ())
        values = parse_print_values(log)
        if "i(vdd)" not in values or "v(vout)" not in values:
            raise SimulationError("operating-point probes were not produced")
        quiescent_current = max(quiescent_current, max(0.0, -values["i(vdd)"]))
        for device in candidate.mos:
            prefix = f"@m.xdut.{device.name.casefold()}"
            vds_key = f"{prefix}[vds]"
            vdsat_key = f"{prefix}[vdsat]"
            if vds_key not in values or vdsat_key not in values:
                raise SimulationError(f"missing saturation probes for {device.name}")
            margin = abs(values[vds_key]) - abs(values[vdsat_key])
            if margin < minimum_saturation:
                minimum_saturation = margin
                worst_device = f"{device.name}@{input_voltage:.2f}V"

    ac_deck = fixture_prefix(candidate, corner) + """VIN vinp 0 DC 1
VLOOP vinn vout DC 0 AC 1
.control
set wr_vecnames
set wr_singlescale
ac dec 100 1k 100G
wrdata ac.dat v(vout) v(vinn)
quit
.endc
.end
"""
    ac_dir = corner_root / "ac"
    run_ngspice(ac_deck, ac_dir, ("ac.dat",))
    frequency, vectors = read_complex_table(ac_dir / "ac.dat", 2)
    loop = [
        -output / input_node if abs(input_node) > 1e-300 else complex(math.inf)
        for output, input_node in zip(vectors[0], vectors[1], strict=True)
    ]
    unity_frequency, phase_margin = loop_metrics(frequency, loop)

    transient_deck = fixture_prefix(candidate, corner) + """VIN vinp 0 PULSE(0.75 1.25 50n 0.1n 0.1n 49.8n 100n)
RFB vout vinn 1m
.control
set wr_vecnames
set wr_singlescale
tran 25p 200n
wrdata transient.dat v(vinp) v(vout)
quit
.endc
.end
"""
    transient_dir = corner_root / "transient"
    run_ngspice(transient_deck, transient_dir, ("transient.dat",))
    time, transient = read_real_table(transient_dir / "transient.dat", 2)
    output = transient[1]
    rise_low = threshold_time(time, output, 0.85, 50e-9, 100e-9, True)
    rise_high = threshold_time(time, output, 1.15, 50e-9, 100e-9, True)
    fall_high = threshold_time(time, output, 1.15, 100e-9, 150e-9, False)
    fall_low = threshold_time(time, output, 0.85, 100e-9, 150e-9, False)
    positive_slew = 0.30 / (rise_high - rise_low)
    negative_slew = 0.30 / (fall_low - fall_high)
    if 0.0 < phase_margin < 90.0:
        equivalent_second_pole = unity_frequency / math.tan(math.radians(90.0 - phase_margin))
    else:
        equivalent_second_pole = 0.0
    return {
        "corner": corner.upper(),
        "positive_slew_rate_v_per_s": positive_slew,
        "negative_slew_rate_v_per_s": negative_slew,
        "unity_gain_frequency_hz": unity_frequency,
        "phase_margin_degrees": phase_margin,
        "quiescent_current_a": quiescent_current,
        "saturation_margin_v": minimum_saturation,
        "worst_saturation_device": worst_device,
        "equivalent_second_pole_hz": equivalent_second_pole,
    }


def criterion_passes(metric: str, value: float) -> bool:
    if metric in {"quiescent_current_a"}:
        return value <= LIMITS[metric] + 1e-12
    return value >= LIMITS[metric] - 1e-12


def reward_boundaries(name: str) -> tuple[float, float]:
    """Return the zero-credit and circuit-collapse boundaries for one metric.

    Let W be the reference's worst corner and S be the absolute spread from the
    reference's best corner to W. Higher-is-better metrics use W - 0.25*S for
    zero credit and W - 1.0*S for circuit collapse. Lower-is-better metrics use
    W + 0.25*S and W + 1.0*S instead.
    """
    scale = REFERENCE_SCALE[name]
    worst = float(scale["worst"])
    best = float(scale["best"])
    spread = abs(best - worst)
    sign = -1.0 if scale["direction"] == "higher" else 1.0
    zero_credit = worst + sign * ZERO_CREDIT_SPREAD_FRACTION * spread
    circuit_collapse = worst + sign * CIRCUIT_COLLAPSE_SPREAD_MULTIPLIER * spread
    return zero_credit, circuit_collapse


def metric_score(name: str, value: float) -> float:
    """Score one corner metric linearly from zero credit to the worst anchor."""
    scale = REFERENCE_SCALE[name]
    worst = float(scale["worst"])
    direction = str(scale["direction"])
    zero_credit, _ = reward_boundaries(name)
    if direction == "higher":
        score = (value - zero_credit) / (worst - zero_credit)
    else:
        score = (zero_credit - value) / (zero_credit - worst)
    return max(0.0, min(1.0, score))


def corner_score(metrics: dict[str, float | str]) -> float:
    scores = [metric_score(name, float(metrics[name])) for name in LIMITS]
    return sum(scores) / len(scores)


def reward_collapse_trigger(metrics: dict[str, float | str]) -> str | None:
    """Return the first metric that is a full reference spread beyond worst."""
    for name in LIMITS:
        value = float(metrics[name])
        scale = REFERENCE_SCALE[name]
        direction = str(scale["direction"])
        _, circuit_collapse = reward_boundaries(name)
        if direction == "higher" and value <= circuit_collapse:
            return name
        if direction == "lower" and value >= circuit_collapse:
            return name
    return None


def grade_submission(candidate_path: Path, artifact_root: Path) -> dict[str, object]:
    try:
        source = candidate_path.read_text(encoding="utf-8")
        candidate = parse_candidate(source)
    except (OSError, UnicodeError, CandidateError) as exc:
        return {
            "outcome": "candidate_invalid",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["CMOA-CANDIDATE-INVALID"],
            "error": str(exc),
            "corners": [],
        }
    if shutil.which("ngspice") is None:
        return {
            "outcome": "infrastructure_error",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["CMOA-NGSPICE-MISSING"],
            "error": "ngspice executable is unavailable",
            "corners": [],
        }
    artifact_root.mkdir(parents=True, exist_ok=True)
    try:
        corners = [simulate_corner(candidate, corner, artifact_root) for corner in CORNERS]
    except (OSError, SimulationError, subprocess.SubprocessError) as exc:
        return {
            "outcome": "simulation_failed",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["CMOA-SIMULATION-FAILED"],
            "error": str(exc),
            "corners": [],
        }

    failure_codes: list[str] = []
    code_names = {
        "positive_slew_rate_v_per_s": "CMOA-SR-RISE",
        "negative_slew_rate_v_per_s": "CMOA-SR-FALL",
        "unity_gain_frequency_hz": "CMOA-UGF",
        "phase_margin_degrees": "CMOA-PM",
        "quiescent_current_a": "CMOA-IQ",
    }
    for corner in corners:
        for name in LIMITS:
            if not criterion_passes(name, float(corner[name])):
                failure_codes.append(f"{code_names[name]}-{corner['corner']}")
    collapse = next(
        (
            f"{corner['corner']}:{metric}"
            for corner in corners
            if (metric := reward_collapse_trigger(corner)) is not None
        ),
        None,
    )
    score = 0.0 if collapse else sum(corner_score(corner) for corner in corners) / len(corners)
    production_pass = not failure_codes
    return {
        "outcome": "passed" if production_pass else "requirements_failed",
        "artifact_evaluable": True,
        "production_pass": production_pass,
        "final_reward": score,
        "failure_codes": failure_codes,
        "error": None,
        "limits": LIMITS,
        "reference_corner_measurements": REFERENCE_CORNER_MEASUREMENTS,
        "reference_scale": REFERENCE_SCALE,
        "reward_boundaries": {
            name: {
                "zero_credit": reward_boundaries(name)[0],
                "circuit_collapse": reward_boundaries(name)[1],
            }
            for name in LIMITS
        },
        "reward_collapse_trigger": collapse,
        "corner_scores": {
            str(corner["corner"]): corner_score(corner) for corner in corners
        },
        "bias_current_a": candidate.bias_current_a,
        "corners": corners,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--artifacts", type=Path)
    arguments = parser.parse_args()
    if arguments.artifacts is None:
        with tempfile.TemporaryDirectory(prefix="eesim-current-mirror-") as temporary:
            print(json.dumps(grade_submission(arguments.candidate, Path(temporary)), indent=2))
    else:
        print(json.dumps(grade_submission(arguments.candidate, arguments.artifacts), indent=2))
