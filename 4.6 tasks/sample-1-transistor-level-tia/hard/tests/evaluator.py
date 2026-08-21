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
from typing import Callable, Iterable, Sequence


EXPECTED_CRITERIA = 28
R_ZERO = 3.545e-3
FULL_REWARD_ERROR = 0.05
ZERO_REWARD_ERROR = 0.20
REWARD_RAMP_WIDTH = ZERO_REWARD_ERROR - FULL_REWARD_ERROR
REFERENCE_RESULT_PATH = Path(__file__).resolve().with_name("reference_calibration.json")
REQUIRED_NODES = {
    "vcc", "mc", "mgc", "oa", "inp", "inn", "finalp", "finaln", "gc", "agc",
    "bufinp", "bufinn", "outp", "outn", "pkdinp", "pkdinn", "detp", "detn",
}
IHP_PDK_REVISION = "22f2a25f1734796de3debbbf29cf697cbbc54081"
OPENVAF_REVISION = "3369a83f9c626f6d298f9f881379f561ce432e27"
DEFAULT_IHP_PDK_ROOT = (
    Path.home() / ".cache/eesimbench-pdks" / f"IHP-Open-PDK-{IHP_PDK_REVISION}"
)
IHP_PDK_ROOT = Path(os.environ.get("EESIM_IHP_PDK_ROOT", DEFAULT_IHP_PDK_ROOT))
IHP_NGSPICE = IHP_PDK_ROOT / "ihp-sg13g2/libs.tech/ngspice"
IHP_MODELS = IHP_NGSPICE / "models"
IHP_WRAPPERS = {
    "sg13_hv_nmos": 4,
    "sg13_hv_pmos": 4,
    "npn13g2": 4,
    "npn13g2v": 4,
    "pnpmpa": 3,
}
REMOVED_FIXTURE_SOURCES = {"vcc", "vmgc", "vmc", "voa", "iinp", "iinn"}
FORBIDDEN_DIRECTIVES = {
    ".ac", ".control", ".endc", ".four", ".func", ".include", ".lib", ".meas",
    ".noise", ".op", ".options", ".param", ".save", ".step", ".tran",
}
ALLOWED_ELEMENT_PREFIXES = {"r", "c", "l", "x", "v", "i"}


def load_reference_criteria() -> dict[tuple[str, str], dict[str, object]]:
    try:
        data = json.loads(REFERENCE_RESULT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"reference calibration is unavailable: {REFERENCE_RESULT_PATH}"
        ) from exc
    criteria = data.get("criteria", [])
    by_key = {(item["test"], item["name"]): item for item in criteria}
    if len(criteria) != EXPECTED_CRITERIA or len(by_key) != EXPECTED_CRITERIA:
        raise RuntimeError(
            "reference calibration must contain exactly "
            f"{EXPECTED_CRITERIA} uniquely named criteria"
        )
    return by_key


REFERENCE_CRITERIA = load_reference_criteria()


class CandidateError(ValueError):
    pass


class SimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    source: str
    simulation_core: str
    structural_failures: tuple[str, ...]
    element_names: frozenset[str]


@dataclass(frozen=True)
class Criterion:
    test: str
    name: str
    value: float | bool
    target: float | bool
    unit: str
    criterion_type: str
    target_range: float | None
    normalized_error: float
    reward: float
    status: str
    scoring_domain: str = "linear"

    def as_dict(self) -> dict[str, object]:
        return {
            "test": self.test,
            "name": self.name,
            "value": self.value,
            "target": self.target,
            "unit": self.unit,
            "criterion_type": self.criterion_type,
            "target_range": self.target_range,
            "normalized_error": self.normalized_error,
            "reward": self.reward,
            "status": self.status,
            "scoring_domain": self.scoring_domain,
        }


def clamp_reward(value: float) -> float:
    return max(0.0, min(1.0, value))


def status_for(reward: float) -> str:
    if math.isclose(reward, 1.0, abs_tol=1e-12):
        return "Pass"
    if reward <= 0.0:
        return "Fail"
    return "Partial"


def reference_criterion(
    test: str,
    name: str,
    criterion_type: str,
    unit: str,
    scoring_domain: str,
) -> dict[str, object]:
    try:
        reference = REFERENCE_CRITERIA[(test, name)]
    except KeyError as exc:
        raise ValueError(f"criterion is absent from reference calibration: {test}/{name}") from exc
    expected = (
        reference["criterion_type"],
        reference["unit"],
        reference["scoring_domain"],
    )
    observed = (criterion_type, unit, scoring_domain)
    if observed != expected:
        raise ValueError(
            f"criterion metadata differs from reference calibration for {test}/{name}: "
            f"expected={expected}, observed={observed}"
        )
    return reference


def central_reward(value: float, target: float, target_range: float) -> tuple[float, float]:
    error = abs(value - target) / target_range
    if error <= FULL_REWARD_ERROR:
        reward = 1.0
    elif error >= ZERO_REWARD_ERROR:
        reward = 0.0
    else:
        reward = (ZERO_REWARD_ERROR - error) / REWARD_RAMP_WIDTH
    return error, clamp_reward(reward)


def maximum_reward(value: float, fixed: float) -> tuple[float, float]:
    error = (value - fixed) / abs(fixed)
    if error <= FULL_REWARD_ERROR:
        reward = 1.0
    elif error >= ZERO_REWARD_ERROR:
        reward = 0.0
    else:
        reward = (ZERO_REWARD_ERROR - error) / REWARD_RAMP_WIDTH
    return error, clamp_reward(reward)


def minimum_reward(value: float, fixed: float) -> tuple[float, float]:
    error = (fixed - value) / abs(fixed)
    if error <= FULL_REWARD_ERROR:
        reward = 1.0
    elif error >= ZERO_REWARD_ERROR:
        reward = 0.0
    else:
        reward = (ZERO_REWARD_ERROR - error) / REWARD_RAMP_WIDTH
    return error, clamp_reward(reward)


def central(
    test: str,
    name: str,
    value: float,
    target: float,
    unit: str,
    target_range: float | None = None,
    logarithmic_db: bool = False,
) -> Criterion:
    domain = "linear magnitude converted from dB" if logarithmic_db else "linear"
    reference = reference_criterion(test, name, "central", unit, domain)
    target = float(reference["value"])
    if logarithmic_db:
        score_value = 10.0 ** (value / 20.0)
        score_target = 10.0 ** (target / 20.0)
        actual_range = score_target
        error, reward = central_reward(score_value, score_target, actual_range)
    else:
        actual_range = R_ZERO if target == 0.0 else abs(target)
        if actual_range <= 0.0:
            raise ValueError(f"central target range must be positive for {name}")
        error, reward = central_reward(value, target, actual_range)
    return Criterion(
        test, name, value, target, unit, "central", actual_range, error, reward,
        status_for(reward), domain,
    )


def maximum(test: str, name: str, value: float, fixed: float, unit: str) -> Criterion:
    reference = reference_criterion(test, name, "maximum", unit, "linear")
    fixed = float(reference["value"])
    error, reward = maximum_reward(value, fixed)
    return Criterion(
        test, name, value, fixed, unit, "maximum", None, error, reward,
        status_for(reward),
    )


def minimum(test: str, name: str, value: float, fixed: float, unit: str) -> Criterion:
    reference = reference_criterion(test, name, "minimum", unit, "linear")
    fixed = float(reference["value"])
    error, reward = minimum_reward(value, fixed)
    return Criterion(
        test, name, value, fixed, unit, "minimum", None, error, reward,
        status_for(reward),
    )


def boolean(test: str, name: str, value: bool) -> Criterion:
    reference = reference_criterion(test, name, "boolean", "boolean", "linear")
    target = bool(reference["value"])
    reward = 1.0 if value == target else 0.0
    return Criterion(
        test, name, value, target, "boolean", "boolean", None,
        0.0 if value == target else 1.0, reward, status_for(reward),
    )


def normalized(line: str) -> str:
    return " ".join(line.split()).casefold()


def parse_candidate(source: str) -> Candidate:
    if not source.strip():
        raise CandidateError("submission is empty")
    if "\x00" in source:
        raise CandidateError("submission contains a NUL byte")

    logical = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("*")
    ]
    if not logical or logical[-1].casefold() != ".end":
        raise CandidateError("submission must end with .end")
    if sum(1 for line in logical if line.casefold() == ".end") != 1:
        raise CandidateError("submission must contain exactly one .end")
    if any(line.casefold().startswith((".subckt", ".ends")) for line in logical):
        raise CandidateError("submission must be flattened and may not contain subcircuits")

    names: set[str] = set()
    nodes: set[str] = set()
    structural_failures: list[str] = []
    internal_sources: list[str] = []
    simulation_lines: list[str] = []

    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            simulation_lines.append(raw)
            continue
        if normalized(line) == ".options ngbehavior=ltpsa":
            # This option only requests LTspice parser compatibility in Ngspice.
            # The private fixtures do not need it, so accept and omit it while
            # continuing to reject every other candidate-supplied .options line.
            continue
        tokens = line.split()
        head = tokens[0].casefold()
        if head == ".end":
            continue
        if head.startswith("."):
            if head in FORBIDDEN_DIRECTIVES:
                raise CandidateError(f"analysis or file-access directive is forbidden: {tokens[0]}")
            raise CandidateError(f"unsupported directive: {tokens[0]}")
        kind = head[0]
        if kind not in ALLOWED_ELEMENT_PREFIXES:
            raise CandidateError(f"unsupported or non-elementary device: {tokens[0]}")
        if head in names:
            raise CandidateError(f"duplicate element name: {tokens[0]}")
        names.add(head)

        if kind == "x":
            wrapper_index = next(
                (index for index, token in enumerate(tokens[1:], start=1) if token.casefold() in IHP_WRAPPERS),
                None,
            )
            if wrapper_index is None:
                raise CandidateError(f"unsupported IHP SG13G2 primitive: {tokens[0]}")
            wrapper = tokens[wrapper_index].casefold()
            node_count = IHP_WRAPPERS[wrapper]
            if wrapper_index != node_count + 1:
                raise CandidateError(f"wrong terminal count for {tokens[0]} using {tokens[wrapper_index]}")
        else:
            node_count = 2
        if len(tokens) < node_count + 2:
            raise CandidateError(f"malformed element: {tokens[0]}")
        nodes.update(token.casefold() for token in tokens[1 : 1 + node_count])

        remove_as_fixture = head in REMOVED_FIXTURE_SOURCES
        if kind in {"v", "i"}:
            first_node = tokens[1].casefold()
            second_node = tokens[2].casefold()
            external_pair = (
                kind == "v"
                and "0" in {first_node, second_node}
                and bool({first_node, second_node} & {"vcc", "mc", "mgc", "oa"})
            )
            input_fixture = (
                kind == "i"
                and "0" in {first_node, second_node}
                and bool({first_node, second_node} & {"inp", "inn"})
            )
            remove_as_fixture = remove_as_fixture or external_pair or input_fixture
            if not external_pair and not input_fixture:
                internal_sources.append(tokens[0])
        if not remove_as_fixture:
            simulation_lines.append(raw)

    missing = sorted(REQUIRED_NODES - nodes)
    if missing:
        structural_failures.append("missing required nodes: " + ", ".join(missing))
    if internal_sources:
        structural_failures.append(
            "independent sources are not limited to external supply/control pins: "
            + ", ".join(internal_sources)
        )
    return Candidate(
        source=source.rstrip() + "\n",
        simulation_core="\n".join(simulation_lines).rstrip() + "\n",
        structural_failures=tuple(structural_failures),
        element_names=frozenset(names),
    )


def run_ngspice(deck: str, run_dir: Path, expected: Sequence[str]) -> str:
    run_dir.mkdir(parents=True, exist_ok=True)
    deck_path = run_dir / "test.cir"
    log_path = run_dir / "ngspice.log"
    deck_path.write_text(deck, encoding="utf-8")
    try:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(IHP_NGSPICE),
                "PDK_ROOT": str(IHP_PDK_ROOT),
                "PDK": "ihp-sg13g2",
            }
        )
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log_path), str(deck_path)],
            cwd=run_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulationError("Ngspice exceeded the 300 second per-run limit") from exc
    log = log_path.read_text(errors="replace") if log_path.is_file() else completed.stderr
    missing = [name for name in expected if not (run_dir / name).is_file()]
    aborted = "simulation(s) aborted" in log.casefold()
    if completed.returncode != 0 or missing or aborted:
        raise SimulationError(
            f"Ngspice failed with code {completed.returncode}; missing={missing}; aborted={aborted}; "
            + log.strip()[-3000:]
        )
    return log


def fixture(
    candidate: Candidate,
    *,
    mc: float = 0.0,
    mgc: float = 1.4,
    oa: float = 1.2,
    extra: str = "",
) -> str:
    return f"""Transistor-level TIA private fixture
.lib "{IHP_MODELS / 'cornerMOShv.lib'}" mos_tt
.lib "{IHP_MODELS / 'cornerHBT.lib'}" hbt_typ
.options method=gear maxord=2 reltol=1e-3 abstol=1e-12 vntol=1e-6 itl4=500 rshunt=1e12
{candidate.simulation_core}
V_TB_VCC vcc 0 3.3
V_TB_MC mc 0 {mc:.12g}
V_TB_MGC mgc 0 {mgc:.12g}
V_TB_OA oa 0 {oa:.12g}
{extra}
"""


def parse_print_values(log: str) -> dict[str, float]:
    values: dict[str, float] = {}
    pattern = re.compile(
        r"^\s*([^=\s]+)\s*=\s*([+-]?(?:[0-9.]+)(?:e[+-]?[0-9]+)?)\s*$",
        re.IGNORECASE,
    )
    for line in log.splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1).casefold()] = float(match.group(2))
    return values


def read_real_table(path: Path, vectors: int) -> tuple[list[float], list[list[float]]]:
    independent: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text(errors="replace").splitlines():
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
    independent: list[float] = []
    outputs = [[] for _ in range(vectors)]
    for raw in path.read_text(errors="replace").splitlines():
        fields = raw.split()
        if len(fields) < 1 + 2 * vectors:
            continue
        try:
            values = [float(value) for value in fields[: 1 + 2 * vectors]]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in values):
            raise SimulationError(f"nonfinite value in {path.name}")
        independent.append(values[0])
        for index in range(vectors):
            outputs[index].append(complex(values[1 + 2 * index], values[2 + 2 * index]))
    if len(independent) < 100:
        raise SimulationError(f"too few AC samples in {path.name}")
    return independent, outputs


def interpolate(x: Sequence[float], y: Sequence[float], target: float, logarithmic_x: bool = False) -> float:
    if target <= x[0]:
        return y[0]
    if target >= x[-1]:
        return y[-1]
    for index in range(1, len(x)):
        if x[index] >= target:
            if logarithmic_x:
                fraction = (
                    math.log(target) - math.log(x[index - 1])
                ) / (math.log(x[index]) - math.log(x[index - 1]))
            else:
                fraction = (target - x[index - 1]) / (x[index] - x[index - 1])
            return y[index - 1] + fraction * (y[index] - y[index - 1])
    return y[-1]


def interpolate_complex(
    x: Sequence[float], y: Sequence[complex], target: float
) -> complex:
    real = interpolate(x, [value.real for value in y], target, True)
    imag = interpolate(x, [value.imag for value in y], target, True)
    return complex(real, imag)


def differential(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [a - b for a, b in zip(left, right, strict=True)]


def unwrap_phase(values: Sequence[complex]) -> list[float]:
    phase: list[float] = []
    for value in values:
        angle = cmath.phase(value)
        if phase:
            while angle - phase[-1] > math.pi:
                angle -= 2.0 * math.pi
            while angle - phase[-1] < -math.pi:
                angle += 2.0 * math.pi
        phase.append(angle)
    return phase


def percentile(values: Sequence[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise SimulationError("percentile requested from an empty sequence")
    position = (len(ordered) - 1) * percent / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def four_clusters(samples: Sequence[float]) -> tuple[list[float], list[list[float]]]:
    centers = [percentile(samples, p) for p in (12.5, 37.5, 62.5, 87.5)]
    for _ in range(100):
        groups = [[] for _ in range(4)]
        for sample in samples:
            index = min(range(4), key=lambda item: abs(sample - centers[item]))
            groups[index].append(sample)
        updated = [
            sum(group) / len(group) if group else centers[index]
            for index, group in enumerate(groups)
        ]
        if max(abs(a - b) for a, b in zip(updated, centers, strict=True)) < 1e-12:
            centers = updated
            break
        centers = updated
    ordered = sorted(zip(centers, groups, strict=True), key=lambda item: item[0])
    return [item[0] for item in ordered], [item[1] for item in ordered]


def nominal_test(candidate: Candidate, root: Path) -> list[Criterion]:
    probes = ["v(inp)", "v(inn)", "v(finalp)", "v(finaln)", "i(V_TB_VCC)"]
    deck = fixture(
        candidate,
        extra="I_TB_P 0 inp DC 0\nI_TB_N inn 0 DC 0",
    ) + f""".control
op
print {' '.join(probes)}
quit
.endc
.end
"""
    values = parse_print_values(run_ngspice(deck, root / "nominal-op", ()))
    missing = [probe.casefold() for probe in probes if probe.casefold() not in values]
    if missing:
        raise SimulationError("missing nominal probes: " + ", ".join(missing))
    inp = values["v(inp)"]
    inn = values["v(inn)"]
    finalp = values["v(finalp)"]
    finaln = values["v(finaln)"]
    current = abs(values["i(v_tb_vcc)"])
    return [
        central("nominal-op", "input common mode", 0.5 * (inp + inn), 0.7594, "V"),
        maximum("nominal-op", "input voltage mismatch", abs(inp - inn), 1e-3, "V"),
        central("nominal-op", "output common mode", 0.5 * (finalp + finaln), 2.781, "V"),
        maximum("nominal-op", "differential output offset", abs(finalp - finaln), 1e-3, "V"),
        central("nominal-op", "supply power", 3.3 * current, 214.9e-3, "W"),
    ]


def ac_test(candidate: Candidate, root: Path) -> list[Criterion]:
    targets = {1.25: None, 1.30: None, 1.35: None, 1.40: None}
    results: dict[float, dict[str, object]] = {}
    for mgc in targets:
        extra = "I_TB_P 0 inp DC 0 AC 1\nI_TB_N inn 0 DC 0 AC 1"
        deck = fixture(candidate, mgc=mgc, extra=extra) + """.control
set wr_vecnames
set wr_singlescale
ac dec 100 1Meg 100G
wrdata ac.dat v(finalp,finaln)
quit
.endc
.end
"""
        run_dir = root / f"ac-mgc-{mgc:.2f}"
        run_ngspice(deck, run_dir, ("ac.dat",))
        frequency, vectors = read_complex_table(run_dir / "ac.dat", 1)
        output = vectors[0]
        magnitude = [abs(value) for value in output]
        low = abs(interpolate_complex(frequency, output, 10e6))
        at_33 = abs(interpolate_complex(frequency, output, 33e9))
        threshold = low / math.sqrt(2.0)
        bandwidth = frequency[-1]
        for index in range(1, len(frequency)):
            if frequency[index] >= 10e6 and magnitude[index - 1] >= threshold > magnitude[index]:
                bandwidth = math.exp(
                    math.log(frequency[index - 1])
                    + (threshold - magnitude[index - 1])
                    / (magnitude[index] - magnitude[index - 1])
                    * (math.log(frequency[index]) - math.log(frequency[index - 1]))
                )
                break
        results[mgc] = {
            "frequency": frequency,
            "vectors": vectors,
            "low_db": 20.0 * math.log10(max(low, 1e-300)),
            "at_33_db": 20.0 * math.log10(max(at_33, 1e-300)),
            "bandwidth": bandwidth,
        }

    low_gains = [float(results[mgc]["low_db"]) for mgc in targets]
    criteria: list[Criterion] = [
        central("ac-mgc-1.25", "minimum-setting transimpedance at 10 MHz", low_gains[0], 72.21, "dB ohm", logarithmic_db=True),
        central("ac-mgc-1.40", "maximum-setting transimpedance at 10 MHz", low_gains[-1], 73.95, "dB ohm", logarithmic_db=True),
        central("ac-sweep", "gain tuning span", low_gains[-1] - low_gains[0], 1.732, "dB"),
        boolean("ac-sweep", "monotonic gain tuning", all(b > a for a, b in zip(low_gains, low_gains[1:]))),
        central("ac-mgc-1.40", "transimpedance at 33 GHz", float(results[1.40]["at_33_db"]), 71.75, "dB ohm", logarithmic_db=True),
    ]
    bandwidths = [float(results[mgc]["bandwidth"]) for mgc in targets]
    criteria.append(minimum("ac-sweep", "minimum 3 dB bandwidth", min(bandwidths), 33.60e9, "Hz"))

    maximum_gain = results[1.40]
    frequency = maximum_gain["frequency"]
    vectors = maximum_gain["vectors"]
    assert isinstance(frequency, list) and isinstance(vectors, list)
    index = min(range(1, len(frequency) - 1), key=lambda item: abs(frequency[item] - 10e9))
    phase = unwrap_phase(vectors[0])
    group_delay = -(phase[index + 1] - phase[index - 1]) / (
        2.0 * math.pi * (frequency[index + 1] - frequency[index - 1])
    )
    criteria.append(central("ac-mgc-1.40", "group delay near 10 GHz", group_delay, 27.48e-12, "s"))

    return criteria


def overload_test(candidate: Candidate, root: Path) -> list[Criterion]:
    probes = ["v(inp)", "v(inn)", "v(finalp)", "v(finaln)"]
    deck = fixture(
        candidate,
        # Both photodiode overload currents are injected into their respective
        # input nodes.  Reversing the negative-side source would require a
        # sourcing cancellation device, contradicting the specified matched
        # NMOS sink topology.
        extra="I_TB_P 0 inp DC 500u\nI_TB_N 0 inn DC 375u",
    ) + f""".control
op
print {' '.join(probes)}
quit
.endc
.end
"""
    values = parse_print_values(run_ngspice(deck, root / "dc-overload", ()))
    if any(probe.casefold() not in values for probe in probes):
        raise SimulationError("missing DC-overload voltage probes")
    inp = values["v(inp)"]
    inn = values["v(inn)"]
    finalp = values["v(finalp)"]
    finaln = values["v(finaln)"]
    return [
        maximum("dc-overload", "maximum input voltage", max(inp, inn), 0.8042, "V"),
        maximum("dc-overload", "input voltage mismatch", abs(inp - inn), 7.967e-3, "V"),
        maximum("dc-overload", "final differential offset", abs(finalp - finaln), 1e-3, "V"),
    ]


def harmonic_distortion(
    time: Sequence[float], values: Sequence[float], start: float, stop: float
) -> float:
    count = 4096
    sample_times = [start + (stop - start) * index / count for index in range(count)]
    samples = [interpolate(time, values, point) for point in sample_times]
    mean = sum(samples) / count
    samples = [value - mean for value in samples]
    amplitudes: list[float] = []
    for harmonic in range(1, 10):
        cosine = sum(
            value * math.cos(2.0 * math.pi * harmonic * index / count)
            for index, value in enumerate(samples)
        )
        sine = sum(
            value * math.sin(2.0 * math.pi * harmonic * index / count)
            for index, value in enumerate(samples)
        )
        amplitudes.append(2.0 * math.hypot(cosine, sine) / count)
    if amplitudes[0] <= 1e-15:
        raise SimulationError("buffer fundamental amplitude is zero")
    return 100.0 * math.sqrt(sum(value * value for value in amplitudes[1:])) / amplitudes[0]


def buffer_test(candidate: Candidate, root: Path) -> list[Criterion]:
    targets = {0.445: (0.5967, 0.5043), 0.735: (0.9274, None)}
    criteria: list[Criterion] = []
    for input_pp, (output_target, thd_target) in targets.items():
        # Each leg contributes half of the requested differential waveform.
        # A per-leg sine amplitude of input_pp/4 therefore produces the stated
        # differential peak-to-peak voltage.
        amplitude = input_pp / 4.0
        extra = f"""I_TB_P 0 inp DC 0
I_TB_N inn 0 DC 0
V_TB_BUFP bufinp 0 SIN(2.235 {amplitude:.12g} 1G)
V_TB_BUFN bufinn 0 SIN(2.235 {amplitude:.12g} 1G 0 0 180)
"""
        deck = fixture(candidate, extra=extra) + """.control
set wr_vecnames
set wr_singlescale
tran 2p 2n 0 2p
wrdata transient.dat v(bufinp) v(bufinn) v(outp) v(outn)
quit
.endc
.end
"""
        run_dir = root / f"buffer-{int(round(input_pp * 1000))}mVpp"
        run_ngspice(deck, run_dir, ("transient.dat",))
        time, vectors = read_real_table(run_dir / "transient.dat", 4)
        input_diff = differential(vectors[0], vectors[1])
        output_diff = differential(vectors[2], vectors[3])
        selected = [index for index, point in enumerate(time) if point >= 1e-9]
        if len(selected) < 100:
            raise SimulationError("too few settled output-buffer samples")
        input_pp_measured = max(input_diff[index] for index in selected) - min(input_diff[index] for index in selected)
        output_pp = max(output_diff[index] for index in selected) - min(output_diff[index] for index in selected)
        gain_db = 20.0 * math.log10(max(output_pp / max(input_pp_measured, 1e-300), 1e-300))
        common_mode = sum(0.5 * (vectors[2][index] + vectors[3][index]) for index in selected) / len(selected)
        thd = harmonic_distortion(time, output_diff, 1e-9, 2e-9)
        test = f"buffer-{int(round(input_pp * 1000))}mVpp"
        criteria.append(central(test, "output peak-to-peak", output_pp, output_target, "V"))
        if thd_target is not None:
            criteria.append(maximum(test, "total harmonic distortion", thd, thd_target, "percent"))
    return criteria


def detector_test(candidate: Candidate, root: Path) -> list[Criterion]:
    targets = {
        0.050: 25.50e-3,
        0.200: 92.03e-3,
        0.400: 158.9e-3,
        0.550: 526.9e-3,
    }
    outputs: list[float] = []
    criteria: list[Criterion] = []
    for input_pp, target in targets.items():
        amplitude = input_pp / 2.0
        # A small differential DC input keeps the x86 VBIC state initialization
        # away from its exact-zero singularity.  The detector ports are driven
        # directly, and its AC-coupled signal tap rejects this DC condition.
        extra = f"""I_TB_P 0 inp DC 33.3333333u
I_TB_N inn 0 DC 33.3333333u
V_TB_PKDP pkdinp 0 SIN(2.092 {amplitude:.12g} 33.5G)
V_TB_PKDN pkdinn 0 SIN(2.092 {amplitude:.12g} 33.5G 0 0 180)
"""
        deck = fixture(candidate, extra=extra) + """.control
set wr_vecnames
set wr_singlescale
tran 1p 1n 0 1p
wrdata detector.dat v(detp) v(detn)
quit
.endc
.end
"""
        run_dir = root / f"detector-{int(round(input_pp * 1000))}mVpp"
        run_ngspice(deck, run_dir, ("detector.dat",))
        time, vectors = read_real_table(run_dir / "detector.dat", 2)
        selected = [index for index, point in enumerate(time) if point >= 0.5e-9]
        value = abs(sum(vectors[0][index] - vectors[1][index] for index in selected) / len(selected))
        outputs.append(value)
        if input_pp in (0.050, 0.550):
            criteria.append(central(run_dir.name, "average differential detector output", value, target, "V"))
    criteria.append(boolean("peak-detector", "strictly monotonic detector response", all(b > a for a, b in zip(outputs, outputs[1:]))))
    return criteria


def op_value(candidate: Candidate, root: Path, name: str, extra: str, probe: str, mc: float = 0.0, mgc: float = 1.4) -> float:
    deck = fixture(candidate, mc=mc, mgc=mgc, extra=extra) + f""".control
op
print {probe}
quit
.endc
.end
"""
    values = parse_print_values(run_ngspice(deck, root / name, ()))
    key = probe.casefold()
    if key not in values:
        raise SimulationError(f"missing operating-point probe {probe}")
    return values[key]


def agc_test(candidate: Candidate, root: Path) -> list[Criterion]:
    nominal_extra = "I_TB_P 0 inp DC 0\nI_TB_N inn 0 DC 0"
    detector_common_mode = 0.5 * (
        op_value(candidate, root, "agc-common-detp", nominal_extra, "v(detp)")
        + op_value(candidate, root, "agc-common-detn", nominal_extra, "v(detn)")
    )
    agc_values: list[float] = []
    for difference in (0.020, 0.050):
        extra = f"""I_TB_P 0 inp DC 0
I_TB_N inn 0 DC 0
V_TB_DETP detp 0 {detector_common_mode + difference / 2.0:.12g}
V_TB_DETN detn 0 {detector_common_mode - difference / 2.0:.12g}
"""
        agc_values.append(op_value(candidate, root, f"agc-{int(difference * 1000)}mV", extra, "v(agc)"))
    gain = abs(agc_values[1] - agc_values[0]) / 0.030
    criteria = [central("agc-amplifier", "AGC gain", gain, 15.03, "V/V")]

    for mgc in (1.25, 1.40):
        extra = "I_TB_P 0 inp DC 0\nI_TB_N inn 0 DC 0"
        gc = op_value(candidate, root, f"selector-manual-{mgc:.2f}", extra, "v(gc)", mc=0.0, mgc=mgc)
        criteria.append(central(f"selector-manual-{mgc:.2f}", "manual selector output", gc, mgc, "V"))
    applied_agc = 1.30
    extra = f"""I_TB_P 0 inp DC 0
I_TB_N inn 0 DC 0
V_TB_AGC agc 0 {applied_agc}
"""
    gc = op_value(candidate, root, "selector-agc", extra, "v(gc)", mc=3.3)
    criteria.append(central("selector-agc", "AGC selector output", gc, applied_agc, "V"))
    return criteria


def pwl_source(name: str, positive: str, negative: str, values: Sequence[float], ui: float) -> str:
    pairs: list[tuple[float, float]] = [(0.0, values[0])]
    epsilon = 1e-12
    for index in range(1, len(values)):
        boundary = index * ui
        pairs.append((boundary - epsilon, values[index - 1]))
        pairs.append((boundary, values[index]))
    pairs.append((len(values) * ui, values[-1]))
    lines = [f"{name} {positive} {negative} PWL("]
    chunk: list[str] = []
    for time, value in pairs:
        chunk.extend((f"{time:.12g}", f"{value:.12g}"))
        if len(chunk) >= 16:
            lines.append("+ " + " ".join(chunk))
            chunk = []
    if chunk:
        lines.append("+ " + " ".join(chunk))
    lines.append("+ )")
    return "\n".join(lines)


def write_eye_svg(time: Sequence[float], output: Sequence[float], path: Path) -> None:
    ui = 40e-12
    start_symbol = math.ceil(1e-9 / ui)
    traces: list[list[tuple[float, float]]] = []
    for symbol in range(start_symbol, min(start_symbol + 100, math.floor(time[-1] / ui) - 1)):
        t0 = symbol * ui
        points = [
            ((point - t0) / ui, value)
            for point, value in zip(time, output, strict=True)
            if t0 <= point <= t0 + 2.0 * ui
        ]
        if len(points) > 4:
            traces.append(points[:: max(1, len(points) // 250)])
    settled = [value for point, value in zip(time, output, strict=True) if point >= 1e-9]
    low, high = min(settled), max(settled)
    span = max(high - low, 1e-9)
    polylines: list[str] = []
    for trace in traces:
        coords = " ".join(
            f"{50 + 700 * x / 2.0:.2f},{360 - 300 * (y - low) / span:.2f}"
            for x, y in trace
        )
        polylines.append(f'<polyline points="{coords}" fill="none" stroke="#2463a2" stroke-opacity="0.16" stroke-width="1"/>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="420" viewBox="0 0 800 420">
<rect width="800" height="420" fill="white"/>
<text x="400" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">25-Gbaud PAM4 eye</text>
<line x1="50" y1="360" x2="750" y2="360" stroke="black"/>
<line x1="50" y1="60" x2="50" y2="360" stroke="black"/>
{''.join(polylines)}
<text x="400" y="402" text-anchor="middle" font-family="sans-serif">Time, 0 to 2 UI</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def pam4_test(candidate: Candidate, root: Path) -> list[Criterion]:
    ui = 40e-12
    sequence = [1, 1, 1, 3, 1, -3, -1, -3, 3, 3, -3, 1, 3, 3, -1, 3, -1, 1, -3, -3, -1, -1, 1, -1, -1, 3, -3, 3, 1, -1, -3]
    symbol_count = 100
    levels = [sequence[index % len(sequence)] * 33.3333333e-6 for index in range(symbol_count)]
    extra = pwl_source("I_TB_P", "0", "inp", levels, ui) + "\n" + pwl_source("I_TB_N", "inn", "0", levels, ui)
    deck = fixture(candidate, extra=extra) + """.control
set wr_vecnames
set wr_singlescale
tran 1p 4n 0 1p
wrdata pam4.dat v(finalp) v(finaln)
quit
.endc
.end
"""
    run_dir = root / "pam4-25gbaud"
    run_ngspice(deck, run_dir, ("pam4.dat",))
    time, vectors = read_real_table(run_dir / "pam4.dat", 2)
    output = differential(vectors[0], vectors[1])
    settled = [value for point, value in zip(time, output, strict=True) if point >= 0.5e-9]
    output_pp = max(settled) - min(settled)

    first = math.ceil(0.5e-9 / ui)
    last = math.floor(time[-1] / ui) - 1
    best_openings: list[float] | None = None
    best_score = -math.inf
    for step in range(181):
        phase = 0.05 + 0.90 * step / 180.0
        samples = [
            interpolate(time, output, (symbol + phase) * ui)
            for symbol in range(first, last)
        ]
        centers, groups = four_clusters(samples)
        if any(len(group) < 3 for group in groups):
            continue
        openings = [
            percentile(groups[index + 1], 10.0) - percentile(groups[index], 90.0)
            for index in range(3)
        ]
        score = min(openings)
        if score > best_score:
            best_score = score
            best_openings = openings
    if best_openings is None:
        raise SimulationError("PAM4 samples could not be clustered into four rails")
    write_eye_svg(time, output, run_dir / "pam4-eye.svg")
    return [
        central("pam4-eye", "differential output peak-to-peak", output_pp, 1.020, "V"),
        minimum("pam4-eye", "minimum vertical eye opening", min(best_openings), 0.1436, "V"),
        boolean("pam4-eye", "three positive eye openings", all(value > 0.0 for value in best_openings)),
    ]


TESTS: tuple[tuple[str, Callable[[Candidate, Path], list[Criterion]]], ...] = (
    ("nominal-op", nominal_test),
    ("ac-and-local-gain", ac_test),
    ("dc-overload", overload_test),
    ("output-buffer", buffer_test),
    ("peak-detector", detector_test),
    ("agc-and-selector", agc_test),
    ("pam4-eye", pam4_test),
)


def result_from_criteria(
    criteria: Sequence[Criterion],
    structural_failures: Sequence[str],
    simulation_failures: Sequence[dict[str, str]],
) -> dict[str, object]:
    coverage = min(1.0, len(criteria) / EXPECTED_CRITERIA)
    measured_score = (
        sum(item.reward for item in criteria) / EXPECTED_CRITERIA
        if criteria
        else 0.0
    )
    structural_ok = not structural_failures
    final_reward = measured_score if structural_ok else 0.0
    production_pass = (
        structural_ok
        and not simulation_failures
        and len(criteria) == EXPECTED_CRITERIA
        and all(math.isclose(item.reward, 1.0, abs_tol=1e-12) for item in criteria)
    )
    failure_codes = [
        "TIA-STRUCTURAL-GATE" for _ in structural_failures
    ] + [
        "TIA-SIMULATION-FAILED-" + failure["test"].upper()
        for failure in simulation_failures
    ]
    failure_codes.extend(
        "TIA-REQUIREMENT-" + re.sub(r"[^A-Z0-9]+", "-", item.name.upper()).strip("-")
        for item in criteria
        if item.reward < 1.0
    )
    artifact_evaluable = bool(criteria)
    if not artifact_evaluable:
        outcome = "simulation_failed"
    elif production_pass:
        outcome = "passed"
    else:
        outcome = "requirements_failed"
    return {
        "outcome": outcome,
        "artifact_evaluable": artifact_evaluable,
        "production_pass": production_pass,
        "final_reward": final_reward,
        "diagnostic_score_before_structural_gate": measured_score,
        "criterion_coverage": coverage,
        "criteria_observed": len(criteria),
        "criteria_expected": EXPECTED_CRITERIA,
        "failure_codes": failure_codes,
        "structural_failures": list(structural_failures),
        "simulation_failures": list(simulation_failures),
        "criteria": [item.as_dict() for item in criteria],
        "not_verifiable": [
            "12.2 pA/sqrt(Hz) input-referred noise",
            "30 dB worst-case CMRR at 25 GHz",
            "4.2 mVpp BER sensitivity at 32 Gb/s",
            "fabrication yield and Monte Carlo mismatch",
            "post-layout and extracted-parasitic behavior",
            "measured 25 Gbaud PAM4 eye statistics",
            "process, voltage, and temperature corners beyond the pinned nominal case",
        ],
        "model_limit": (
            "The pinned IHP SG13G2 SiGe BiCMOS models support pre-layout simulation; "
            "this task does not validate the paper's fabricated silicon or extracted layout."
        ),
    }


def rescore_cached_result(cached: dict[str, object]) -> dict[str, object]:
    cached_criteria = cached.get("criteria", [])
    if len(cached_criteria) != EXPECTED_CRITERIA:
        raise ValueError(
            f"cached result has {len(cached_criteria)} criteria; expected {EXPECTED_CRITERIA}"
        )
    rescored: list[Criterion] = []
    for item in cached_criteria:
        test = str(item["test"])
        name = str(item["name"])
        unit = str(item["unit"])
        criterion_type = str(item["criterion_type"])
        value = item["value"]
        if criterion_type == "central":
            rescored.append(
                central(
                    test,
                    name,
                    float(value),
                    float(item["target"]),
                    unit,
                    logarithmic_db=(
                        item["scoring_domain"] == "linear magnitude converted from dB"
                    ),
                )
            )
        elif criterion_type == "maximum":
            rescored.append(maximum(test, name, float(value), float(item["target"]), unit))
        elif criterion_type == "minimum":
            rescored.append(minimum(test, name, float(value), float(item["target"]), unit))
        elif criterion_type == "boolean":
            rescored.append(boolean(test, name, bool(value)))
        else:
            raise ValueError(f"unsupported cached criterion type: {criterion_type}")
    return result_from_criteria(
        rescored,
        cached.get("structural_failures", []),
        cached.get("simulation_failures", []),
    )


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
            "failure_codes": ["TIA-CANDIDATE-INVALID"],
            "error": str(exc),
            "criteria": [],
        }
    if shutil.which("ngspice") is None:
        return {
            "outcome": "infrastructure_error",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["TIA-NGSPICE-MISSING"],
            "error": "ngspice executable is unavailable",
            "criteria": [],
        }

    artifact_root.mkdir(parents=True, exist_ok=True)
    criteria: list[Criterion] = []
    simulation_failures: list[dict[str, str]] = []
    for test_name, function in TESTS:
        try:
            criteria.extend(function(candidate, artifact_root))
        except (OSError, SimulationError, subprocess.SubprocessError, ValueError, ZeroDivisionError) as exc:
            simulation_failures.append({"test": test_name, "error": str(exc)})

    return result_from_criteria(
        criteria,
        candidate.structural_failures,
        simulation_failures,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--artifacts", type=Path)
    arguments = parser.parse_args()
    if arguments.artifacts is None:
        with tempfile.TemporaryDirectory(prefix="eesim-tia-") as temporary:
            print(json.dumps(grade_submission(arguments.candidate, Path(temporary)), indent=2))
    else:
        print(json.dumps(grade_submission(arguments.candidate, arguments.artifacts), indent=2))
