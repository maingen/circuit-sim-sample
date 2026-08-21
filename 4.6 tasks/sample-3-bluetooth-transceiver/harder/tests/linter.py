#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_CANDIDATE_BYTES = 10_000_000
TRUSTED_INCLUDE = "/opt/sky130-pdk/models/sky130_27v_tt.spice"
TRANSISTOR_WRAPPERS = {
    "sky130_fd_pr__nfet_g5v0d10v5": (4, "nfet"),
    "sky130_fd_pr__pfet_g5v0d10v5": (4, "pfet"),
    "sky130_fd_pr__pnp_05v5_w0p68l0p68": (3, "pnp"),
}
REQUIRED_BLOCKS = {
    "bias_reference",
    "rc_calibration",
    "reference_divider",
    "pfd_charge_pump_loop_filter",
    "vco",
    "prescaler_frontend",
    "program_counter_159",
    "program_counter_150",
    "swallow_counter",
    "programmable_divider_control",
    "synthesizer_interconnect",
    "clock_generator",
    "tdd_switch",
    "lna",
    "rx_iq_mixer",
    "complex_bpf",
    "limiter_rssi",
    "if_demodulator",
    "tx_fsk_modulator",
    "gaussian_filters",
    "tx_ssb_mixer",
    "power_amplifier",
    "top_interconnect",
}
MIN_TRANSISTORS = {
    "bias_reference": 5,
    "rc_calibration": 15,
    "reference_divider": 30,
    "pfd_charge_pump_loop_filter": 30,
    "vco": 20,
    "prescaler_frontend": 40,
    "program_counter_159": 30,
    "program_counter_150": 30,
    "swallow_counter": 20,
    "programmable_divider_control": 30,
    "synthesizer_interconnect": 5,
    "clock_generator": 20,
    "tdd_switch": 8,
    "lna": 8,
    "rx_iq_mixer": 20,
    "complex_bpf": 20,
    "limiter_rssi": 30,
    "if_demodulator": 30,
    "tx_fsk_modulator": 20,
    "gaussian_filters": 16,
    "tx_ssb_mixer": 20,
    "power_amplifier": 8,
    "top_interconnect": 0,
}
EXTERNAL_PORTS = {
    "antp", "antn", "txdata", "txen", "rxdata", "rssi", "g2", "g1", "g0",
    "ref12", "vdd", "0",
}
REQUIRED_OBSERVATION_NODES = {
    "bias_vref", "bias_vbn", "bias_vbp", "rcclk", "cal0", "cal1", "cal2", "cal3",
    "cal4", "cal5", "vcop", "vcon", "vctrl", "divout", "loip", "loin", "loqp",
    "loqn", "divip", "divin", "divqp", "divqn", "lna_outp", "lna_outn",
    "rx_mix_ip", "rx_mix_in", "rx_mix_qp", "rx_mix_qn", "bpf_ip", "bpf_in",
    "bpf_qp", "bpf_qn", "limitp", "limitn", "limitqp", "limitqn", "demod_discr", "fsk_ip", "fsk_in",
    "fsk_qp", "fsk_qn", "gauss_ip", "gauss_in", "gauss_qp", "gauss_qn",
    "tx_mixp", "tx_mixn", "txp", "txn", "ref667", "prescaler_clk", "mod16_ctl",
    "prescaler_div15", "prescaler_div16", "prescaler_rf16", "program_frame159",
    "program_frame150", "swallow_done", "divider_frame", "modsel", "sdone", "up", "down",
    "cp", "vco_limited_clk", "chan_s0", "chan_s1", "chan_s2", "chan_s3", "chan_s4",
    "chan_s5", "chan_s6", "bias_vbana", "bias_vbrf", "bias_vbpa", "bias_vcas", "rxp", "rxn",
}
PATHS = (
    ("txdata", "fsk_ip", "gauss_ip", "tx_mixp", "txp", "antp"),
    ("antp", "lna_outp", "rx_mix_ip", "bpf_ip", "limitp", "rxdata"),
    ("ref12", "divout", "vctrl", "vcop", "loip"),
)
FORBIDDEN_TEXT = re.compile(
    r"(?i)\b(verilog-a|verilog-ams|s-parameter|laplace|table|poly|agauss|gauss|unif|random|rand)\b|\bv\s*\(|\bi\s*\("
)


@dataclass(frozen=True)
class Element:
    name: str
    kind: str
    nodes: tuple[str, ...]
    model: str | None
    line: int
    raw: str


class CandidateError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_trusted_pdk(pdk_root: Path, allowlist_path: Path) -> dict[str, Any]:
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    expected = {record["path"]: record["sha256"] for record in allowlist["model_files"]}
    observed = {
        relative: file_sha256(pdk_root / relative)
        for relative in expected
        if (pdk_root / relative).is_file()
    }
    actual_paths = {
        path.relative_to(pdk_root).as_posix()
        for path in (pdk_root / "models").rglob("*")
        if path.is_file()
    }
    if expected != observed:
        missing = sorted(set(expected) - set(observed))
        added = sorted(actual_paths - set(expected))
        changed = sorted(path for path in expected.keys() & observed.keys() if expected[path] != observed[path])
        raise CandidateError(
            f"trusted PDK tree mismatch: missing={missing}, added={added}, changed={changed}"
        )
    include_pattern = re.compile(r"(?i)^\s*\.include\s+[\"']?([^\"'\s]+)")
    visited = set()
    stack = [pdk_root / "models/sky130_27v_tt.spice"]
    edges = []
    while stack:
        path = stack.pop()
        relative = path.relative_to(pdk_root).as_posix()
        if relative in visited:
            continue
        if relative not in expected:
            raise CandidateError(f"trusted include leaves pinned tree: {relative}")
        visited.add(relative)
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = include_pattern.match(raw)
            if not match:
                continue
            include = match.group(1)
            child = (pdk_root / include).resolve()
            try:
                child.relative_to(pdk_root.resolve())
            except ValueError as exc:
                raise CandidateError(f"trusted include escapes PDK root: {include}") from exc
            if not child.is_file():
                raise CandidateError(f"trusted include is missing: {include}")
            edges.append([relative, child.relative_to(pdk_root).as_posix()])
            stack.append(child)
    return {
        "pdk_revision": allowlist["open_pdks_revision"],
        "verified_file_count": len(observed),
        "reachable_include_file_count": len(visited),
        "include_edges": edges,
    }


def logical_lines(source: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if line.startswith("+"):
            if not result:
                raise CandidateError(f"line {number}: orphan continuation")
            original, previous = result[-1]
            result[-1] = (original, previous + " " + line[1:].strip())
        else:
            result.append((number, line))
    return result


def parse_candidate(path: Path) -> tuple[list[Element], set[str], list[str]]:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_CANDIDATE_BYTES:
        raise CandidateError("candidate is empty or exceeds 10 MB")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateError("candidate must be UTF-8") from exc
    elements = []
    nodes: set[str] = set()
    includes = []
    names = set()
    ended = False
    for number, line in logical_lines(source):
        if not line or line.startswith(("*", ";")):
            continue
        if ended:
            raise CandidateError(f"line {number}: content after .end")
        tokens = line.split()
        head = tokens[0]
        lower = head.casefold()
        if line.startswith("."):
            if lower == ".end":
                ended = True
                continue
            if lower == ".include" and len(tokens) == 2:
                include = tokens[1].strip("\"'")
                if include != TRUSTED_INCLUDE:
                    raise CandidateError(f"line {number}: untrusted include {include}")
                includes.append(include)
                continue
            if lower == ".param":
                if FORBIDDEN_TEXT.search(line):
                    raise CandidateError(f"line {number}: behavioral parameter expression")
                continue
            raise CandidateError(f"line {number}: forbidden directive {head}")
        name_key = head.casefold()
        if name_key in names:
            raise CandidateError(f"line {number}: duplicate element name {head}")
        names.add(name_key)
        prefix = head[0].upper()
        if prefix in {"R", "L", "C"}:
            if len(tokens) < 4:
                raise CandidateError(f"line {number}: incomplete {prefix} element")
            if FORBIDDEN_TEXT.search(" ".join(tokens[3:])):
                raise CandidateError(f"line {number}: behavioral passive value")
            element_nodes = tuple(token.casefold() for token in tokens[1:3])
            element = Element(head, prefix, element_nodes, None, number, line)
        elif prefix == "X":
            parameter_index = next(
                (index for index, token in enumerate(tokens[1:], 1) if "=" in token),
                len(tokens),
            )
            model_index = parameter_index - 1
            if model_index < 2:
                raise CandidateError(f"line {number}: malformed X instance")
            model = tokens[model_index].casefold()
            if model not in TRANSISTOR_WRAPPERS:
                raise CandidateError(f"line {number}: X does not resolve to an allow-listed transistor")
            expected_nodes, device_kind = TRANSISTOR_WRAPPERS[model]
            element_nodes = tuple(token.casefold() for token in tokens[1:model_index])
            if len(element_nodes) != expected_nodes:
                raise CandidateError(
                    f"line {number}: {model} requires {expected_nodes} terminals, got {len(element_nodes)}"
                )
            allowed_parameters = {"l", "w", "nf", "m", "mult"}
            for token in tokens[parameter_index:]:
                if "=" not in token or token.split("=", 1)[0].casefold() not in allowed_parameters:
                    raise CandidateError(f"line {number}: forbidden transistor parameter {token}")
            if device_kind == "nfet" and element_nodes[3] not in {"0", "vss"}:
                raise CandidateError(f"line {number}: NFET bulk must be ground")
            if device_kind == "pfet" and element_nodes[3] != "vdd":
                raise CandidateError(f"line {number}: PFET bulk must be vdd")
            element = Element(head, "TRANSISTOR", element_nodes, model, number, line)
        else:
            raise CandidateError(f"line {number}: forbidden element {head}")
        elements.append(element)
        nodes.update(element.nodes)
    if not ended:
        raise CandidateError("candidate must end with .end")
    if includes.count(TRUSTED_INCLUDE) > 1:
        raise CandidateError("trusted PDK include may appear at most once")
    return elements, nodes, includes


def graph_for(elements: list[Element]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for element in elements:
        active = [node for node in element.nodes if node not in {"0", "vss", "vdd"}]
        for node in active:
            graph[node]
        for left in active:
            for right in active:
                if left != right:
                    graph[left].add(right)
    return graph


def has_path(graph: dict[str, set[str]], left: str, right: str) -> bool:
    queue = deque([left])
    seen = {left}
    while queue:
        node = queue.popleft()
        if node == right:
            return True
        for neighbor in graph.get(node, set()):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return False


def validate_manifest(
    path: Path, elements: list[Element], nodes: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateError(f"invalid architecture manifest: {exc}") from exc
    findings = []
    if manifest.get("schema_version") != 1:
        findings.append({"code": "MANIFEST_SCHEMA", "detail": "schema_version must be 1"})
    top = manifest.get("top", {})
    if set(map(str.casefold, top.get("external_ports", []))) != EXTERNAL_PORTS:
        findings.append({"code": "PORT_CONTRACT", "detail": "external port set is incomplete or changed"})
    modes = {str(item).casefold() for item in manifest.get("operating_modes", [])}
    if modes != {"transmit", "receive"}:
        findings.append({"code": "MODE_CONTRACT", "detail": "both transmit and receive modes are required"})
    blocks = manifest.get("blocks", {})
    if not isinstance(blocks, dict) or set(blocks) != REQUIRED_BLOCKS:
        findings.append({"code": "BLOCK_INVENTORY", "detail": "required block inventory is incomplete or changed"})
        blocks = blocks if isinstance(blocks, dict) else {}
    element_names = {element.name.casefold(): element for element in elements}
    ownership = Counter()
    for block_name, block in blocks.items():
        if not isinstance(block, dict):
            findings.append({"code": "BLOCK_MANIFEST", "block": block_name, "detail": "block entry must be an object"})
            continue
        claimed = [str(name).casefold() for name in block.get("elements", [])]
        for name in claimed:
            ownership[name] += 1
            if name not in element_names:
                findings.append({"code": "UNKNOWN_ELEMENT", "block": block_name, "element": name})
        transistor_count = sum(
            1 for name in claimed if name in element_names and element_names[name].kind == "TRANSISTOR"
        )
        minimum = MIN_TRANSISTORS.get(block_name, 0)
        if transistor_count < minimum:
            findings.append(
                {
                    "code": "BLOCK_DEVICE_COUNT",
                    "block": block_name,
                    "detail": f"{transistor_count} transistors is below the private minimum {minimum}",
                }
            )
        interface = block.get("interface", {})
        if not isinstance(interface, dict) or not interface:
            findings.append({"code": "BLOCK_INTERFACE", "block": block_name, "detail": "interface mapping is missing"})
        else:
            for role, node in interface.items():
                if str(node).casefold() not in nodes:
                    findings.append(
                        {"code": "UNKNOWN_INTERFACE_NODE", "block": block_name, "role": role, "node": node}
                    )
        claimed_elements = [element_names[name] for name in claimed if name in element_names]
        block_graph = graph_for(claimed_elements)
        interface_nodes = {
            str(node).casefold()
            for node in interface.values()
            if str(node).casefold() not in {"0", "vss", "vdd"}
        } if isinstance(interface, dict) else set()
        for element in claimed_elements:
            active_nodes = [node for node in element.nodes if node not in {"0", "vss", "vdd"}]
            if not active_nodes:
                if element.kind != "C":
                    findings.append(
                        {"code": "POWER_ONLY_DECORATION", "block": block_name, "element": element.name}
                    )
                continue
            if interface_nodes and not any(
                has_path(block_graph, node, interface_node)
                for node in active_nodes
                for interface_node in interface_nodes
            ):
                findings.append(
                    {
                        "code": "DISCONNECTED_DECORATION",
                        "block": block_name,
                        "element": element.name,
                    }
                )
    for name in element_names:
        if ownership[name] != 1:
            findings.append(
                {
                    "code": "ELEMENT_OWNERSHIP",
                    "element": name,
                    "detail": f"element must belong to exactly one block, observed {ownership[name]}",
                }
            )
    return manifest, findings


def lint(candidate: Path, architecture: Path, starter_sha256: str | None = None) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    try:
        elements, nodes, includes = parse_candidate(candidate)
        manifest, manifest_findings = validate_manifest(architecture, elements, nodes)
        findings.extend(manifest_findings)
    except CandidateError as exc:
        return {
            "eligible": False,
            "mandatory_findings": [{"code": "PARSE_OR_POLICY", "detail": str(exc), "mandatory": True}],
        }
    if starter_sha256 and file_sha256(candidate) == starter_sha256:
        findings.append({"code": "UNCHANGED_STARTER", "detail": "candidate matches the starter artifact"})
    if not EXTERNAL_PORTS.issubset(nodes):
        findings.append({"code": "MISSING_EXTERNAL_NODE", "detail": sorted(EXTERNAL_PORTS - nodes)})
    if not REQUIRED_OBSERVATION_NODES.issubset(nodes):
        findings.append(
            {"code": "MISSING_OBSERVATION_NODE", "detail": sorted(REQUIRED_OBSERVATION_NODES - nodes)}
        )
    counts = Counter(element.kind for element in elements)
    if counts["TRANSISTOR"] < 350 or counts["R"] < 20 or counts["C"] < 20 or counts["L"] < 4:
        findings.append(
            {
                "code": "GLOBAL_DEVICE_COUNT",
                "detail": {"observed": dict(counts), "required": {"TRANSISTOR": 350, "R": 20, "C": 20, "L": 4}},
            }
        )
    for element in elements:
        if element.kind == "R" and set(element.nodes) in ({"vdd", "0"}, {"vdd", "vss"}):
            findings.append(
                {"code": "SUPPLY_CURRENT_PADDING", "element": element.name, "detail": "direct rail resistor is forbidden"}
            )
    graph = graph_for(elements)
    for sequence in PATHS:
        for left, right in zip(sequence, sequence[1:]):
            if not has_path(graph, left, right):
                findings.append(
                    {"code": "SIGNAL_PATH", "detail": f"no device-level path between {left} and {right}"}
                )
    normalized = []
    for finding in findings:
        item = dict(finding)
        item["mandatory"] = True
        normalized.append(item)
    return {
        "eligible": not normalized,
        "candidate_sha256": file_sha256(candidate),
        "architecture_sha256": file_sha256(architecture),
        "trusted_includes": includes,
        "element_counts": dict(sorted(counts.items())),
        "node_count": len(nodes),
        "manifest_submission_id": manifest.get("submission_id"),
        "mandatory_findings": normalized,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("architecture", type=Path)
    parser.add_argument("--starter-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = lint(args.candidate, args.architecture, args.starter_sha256)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    raise SystemExit(0 if result["eligible"] else 1)


if __name__ == "__main__":
    main()
