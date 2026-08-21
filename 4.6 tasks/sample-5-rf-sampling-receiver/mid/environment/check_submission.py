#!/usr/bin/env python3
"""Strict static eligibility linter for sample 5 SKY130 submissions."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path


MAX_TOTAL_BYTES = 16_000_000
ALLOWED_X_WRAPPERS = {
    "sky130_fd_pr__nfet_01v8",
    "sky130_fd_pr__pfet_01v8",
    "sky130_fd_pr__npn_05v5_W1p00L1p00",
    "sky130_fd_pr__pnp_05v5_W3p40L3p40",
}
ALLOWED_M_MODELS = re.compile(
    r"^sky130_fd_pr__(?:n|p)fet_01v8__model(?:\.\d+)?$", re.IGNORECASE
)
ALLOWED_Q_MODELS = {
    "sky130_fd_pr__npn_05v5_W1p00L1p00__model": 4,
    "sky130_fd_pr__pnp_05v5_W3p40L3p40__model": 3,
}
FORBIDDEN_DIRECTIVES = {
    ".ac", ".control", ".csparam", ".dc", ".endc", ".func", ".four",
    ".if", ".include", ".lib", ".meas", ".model", ".noise", ".op",
    ".plot", ".print", ".probe", ".save", ".step", ".temp", ".tran",
    ".width", ".option",
}
REQUIRED_FILES = {
    "clock_bias.spice": ("CLOCK_BIAS_3MA", ["VDD", "VSS", "NBIAS"]),
    "clock_slicer.spice": ("CLOCK_SLICER", ["INP", "INN", "NBIAS", "VDD", "VSS", "OUT"]),
    "phase24.spice": ("PHASE24", ["CLK", "CLKB", "RESET", "VDD", "VSS"] + [f"P{i}" for i in range(1, 25)]),
    "dtg.spice": ("DTG", ["CLKB", "CLKC", "EDGE_PREV", "EDGE", "VDD", "VSS", "OUT"]),
    "clock_path.spice": ("CLOCK_PATH", ["LOP", "LON", "RESET", "VDD", "VSS", "CLK", "CLKB"] + [f"P{i}" for i in range(1, 25)] + ["ADCCLK", "ADCCLKB"]),
    "sh_mixer.spice": ("SH_MIXER", ["IN", "CLK", "VBSH", "VDD", "VSS", "OUT"]),
    "fir23.spice": ("FIR23", ["IN"] + [f"P{i}" for i in range(2, 25, 2)] + ["OUTP", "OUTN", "VSS"]),
    "output_buffer.spice": ("OUTBUF", ["IN", "VBTAIL", "VBSF", "VDD", "VSS", "OUT"]),
    "rf_frontend.spice": ("RF_FRONTEND", ["ANT", "VDD", "VSS", "OUT"]),
    "adc1bit.spice": ("ADC1BIT", ["INP", "INN", "CLK", "CLKB", "VDD", "VSS", "BIT", "BITB"]),
    "rfsd_core.spice": ("RFSD_CORE", ["IN", "LOP", "LON", "RESET", "VDD", "VSS", "IOUTP", "IOUTN", "QOUTP", "QOUTN", "ADCCLK", "ADCCLKB"]),
    "full_receiver.spice": ("FULL_RECEIVER", ["ANT", "LOP", "LON", "RESET", "VDD", "VSS", "IOUTP", "IOUTN", "QOUTP", "QOUTN", "IBIT", "IBITB", "QBIT", "QBITB", "ADCCLK"]),
}


@dataclass
class Finding:
    severity: str
    code: str
    file: str
    line: int
    detail: str


class LintError(ValueError):
    pass


def logical_lines(source: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for number, raw in enumerate(source.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith(";"):
            continue
        if stripped.startswith("+"):
            if not result:
                raise LintError(f"line {number}: orphan continuation")
            old_number, old = result[-1]
            result[-1] = (old_number, old + " " + stripped[1:].strip())
        else:
            result.append((number, stripped))
    return result


def strip_inline_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def nodes_for_device(tokens: list[str]) -> tuple[list[str], str | None]:
    prefix = tokens[0][0].upper()
    if prefix in {"R", "L", "C"}:
        if len(tokens) < 4:
            raise LintError("passive requires two nodes and a value")
        return tokens[1:3], None
    if prefix == "M":
        if len(tokens) < 6:
            raise LintError("MOSFET requires four terminals and a model")
        if not ALLOWED_M_MODELS.fullmatch(tokens[5]):
            raise LintError(f"direct MOS model is not allow-listed: {tokens[5]}")
        return tokens[1:5], tokens[5]
    if prefix == "Q":
        for model, terminal_count in ALLOWED_Q_MODELS.items():
            model_index = 1 + terminal_count
            if len(tokens) > model_index and tokens[model_index].casefold() == model.casefold():
                return tokens[1:model_index], tokens[model_index]
        raise LintError("direct BJT model is not allow-listed or has the wrong terminal count")
    if prefix == "X":
        if len(tokens) < 6:
            raise LintError("SKY130 wrapper requires four terminals and a wrapper name")
        wrapper_index = next((i for i, token in enumerate(tokens[1:], 1) if "=" in token), len(tokens)) - 1
        wrapper = tokens[wrapper_index]
        if wrapper.casefold() not in {item.casefold() for item in ALLOWED_X_WRAPPERS}:
            raise LintError(f"X instance does not resolve to an allow-listed one-transistor wrapper: {wrapper}")
        nodes = tokens[1:wrapper_index]
        required_terminals = 3 if "pnp_05v5" in wrapper.casefold() else 4
        if len(nodes) != required_terminals:
            raise LintError(f"wrapper {wrapper} requires exactly {required_terminals} terminals")
        return nodes, wrapper
    raise LintError(f"forbidden DUT element prefix {prefix}")


def lint_file(path: Path, expected_subckt: str, expected_ports: list[str]) -> tuple[list[Finding], dict[str, int]]:
    findings: list[Finding] = []
    counts: defaultdict[str, int] = defaultdict(int)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [Finding("fatal", "missing_file", path.name, 0, str(exc))], dict(counts)
    if len(raw) > 2_000_000:
        findings.append(Finding("fatal", "file_too_large", path.name, 0, f"{len(raw)} bytes"))
        return findings, dict(counts)
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [Finding("fatal", "non_utf8", path.name, 0, "candidate must be UTF-8")], dict(counts)

    try:
        lines = logical_lines(source)
    except LintError as exc:
        return [Finding("fatal", "syntax", path.name, 0, str(exc))], dict(counts)

    subckts: list[tuple[int, list[str]]] = []
    ends = 0
    inside = False
    port_set = {port.casefold() for port in expected_ports}
    graph: defaultdict[str, set[str]] = defaultdict(set)
    device_nodes: list[tuple[int, list[str]]] = []

    for number, original in lines:
        line = strip_inline_comment(original)
        if not line:
            continue
        tokens = line.split()
        token = tokens[0]
        lower = token.casefold()
        if lower == ".subckt":
            subckts.append((number, tokens[1:]))
            if inside:
                findings.append(Finding("fatal", "nested_subckt", path.name, number, "nested or multiple subcircuits are forbidden"))
            inside = True
            continue
        if lower == ".ends":
            ends += 1
            inside = False
            continue
        if lower == ".end":
            continue
        if token.startswith("."):
            code = "forbidden_directive" if lower in FORBIDDEN_DIRECTIVES else "unapproved_directive"
            findings.append(Finding("fatal", code, path.name, number, token))
            continue
        if not inside:
            findings.append(Finding("fatal", "device_outside_subckt", path.name, number, token))
            continue
        prefix = token[0].upper()
        try:
            nodes, _model = nodes_for_device(tokens)
        except LintError as exc:
            findings.append(Finding("fatal", "illegal_element", path.name, number, str(exc)))
            continue
        counts[prefix] += 1
        device_nodes.append((number, nodes))
        unique = [node.casefold() for node in nodes]
        for left in unique:
            for right in unique:
                if left != right:
                    graph[left].add(right)

    if len(subckts) != 1 or ends != 1:
        findings.append(Finding("fatal", "subckt_count", path.name, 0, f"expected one .subckt/.ends pair, found {len(subckts)}/{ends}"))
    elif subckts:
        number, declaration = subckts[0]
        actual_name = declaration[0] if declaration else ""
        actual_ports = declaration[1:]
        if actual_name.casefold() != expected_subckt.casefold():
            findings.append(Finding("fatal", "wrong_subckt", path.name, number, f"expected {expected_subckt}, found {actual_name}"))
        if [p.casefold() for p in actual_ports] != [p.casefold() for p in expected_ports]:
            findings.append(Finding("fatal", "wrong_ports", path.name, number, f"expected {' '.join(expected_ports)}, found {' '.join(actual_ports)}"))

    device_count = sum(counts.values())
    if device_count == 0:
        findings.append(Finding("fatal", "empty_circuit", path.name, 0, "no physical devices"))

    reachable: set[str] = set()
    queue = deque(node for node in port_set if node in graph)
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        queue.extend(graph[node] - reachable)
    for number, nodes in device_nodes:
        if not any(node.casefold() in reachable for node in nodes):
            findings.append(Finding("fatal", "disconnected_island", path.name, number, "device belongs to an island disconnected from every declared port"))

    return findings, dict(counts)


def lint_submission(directory: Path) -> dict[str, object]:
    findings: list[Finding] = []
    counts: defaultdict[str, int] = defaultdict(int)
    if not directory.is_dir():
        findings.append(Finding("fatal", "missing_submission", str(directory), 0, "submission directory does not exist"))
    else:
        files = {item.name for item in directory.iterdir() if item.is_file()}
        unexpected = sorted(files - set(REQUIRED_FILES))
        for name in unexpected:
            findings.append(Finding("fatal", "unexpected_file", name, 0, "only contract artifacts are allowed"))
        total_bytes = sum(item.stat().st_size for item in directory.iterdir() if item.is_file())
        if total_bytes > MAX_TOTAL_BYTES:
            findings.append(Finding("fatal", "submission_too_large", str(directory), 0, f"{total_bytes} bytes"))
        for name, (subckt, ports) in REQUIRED_FILES.items():
            local_findings, local_counts = lint_file(directory / name, subckt, ports)
            findings.extend(local_findings)
            for prefix, count in local_counts.items():
                counts[prefix] += count
    eligible = not any(item.severity == "fatal" for item in findings)
    return {
        "eligible": eligible,
        "device_counts": dict(sorted(counts.items())),
        "findings": [asdict(item) for item in findings],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = lint_submission(args.submission)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("PASS" if result["eligible"] else "FAIL")
        for item in result["findings"]:
            print(f"{item['severity']} {item['code']} {item['file']}:{item['line']} {item['detail']}")
    raise SystemExit(0 if result["eligible"] else 2)


if __name__ == "__main__":
    main()
