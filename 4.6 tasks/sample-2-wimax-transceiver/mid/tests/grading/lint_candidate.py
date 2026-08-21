#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from contract import BLOCK_PORTS, MINIMUM_COUNTS, REQUIRED_FILES


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "grading" / "strict_sky130_allowlist.json"
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 10_000_000
FORBIDDEN_TEXT = re.compile(
    r"(?i)(verilog|s-?parameter|laplace|table\s*\(|poly\s*\(|behavioral|ideal\s+(opamp|mixer|filter|switch)|target_ledger|reference_snapshot|grader|fixture)"
)
DYNAMIC_VALUE = re.compile(r"(?i)(?:\bv\s*\(|\bi\s*\(|\btime\b|\bfreq\b|\btemper\b|\bwhite\s*\(|\bgauss\s*\(|\bagauss\s*\(|\bnoise\s*\()")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_lines(text: str) -> list[tuple[int, str]]:
    output: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*"):
            continue
        content = raw.split(";", 1)[0].strip()
        if not content:
            continue
        if content.startswith("+"):
            if not output:
                raise ValueError(f"line {number}: orphan continuation")
            old_number, prior = output[-1]
            output[-1] = (old_number, prior + " " + content[1:].strip())
        else:
            output.append((number, content))
    return output


def lint_file(path: Path, block: str, allowlist: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    try:
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"block": block, "path": str(path), "violations": [{"code": "FILE_READ", "detail": str(exc)}]}
    if len(raw_bytes) > MAX_FILE_BYTES:
        violations.append({"code": "FILE_TOO_LARGE", "detail": f"{len(raw_bytes)} bytes"})
    match = FORBIDDEN_TEXT.search(text)
    if match:
        violations.append({"code": "FORBIDDEN_TEXT", "detail": match.group(0)})
    try:
        lines = logical_lines(text)
    except ValueError as exc:
        return {"block": block, "path": str(path), "violations": [{"code": "PARSE", "detail": str(exc)}]}

    wrappers = allowlist["allowed_single_transistor_x_wrappers"]
    direct_m = set(allowlist["allowed_direct_m_models"])
    direct_q = set(allowlist["allowed_direct_q_models"])
    forbidden_prefixes = set(allowlist["forbidden_prefixes"])
    counts: Counter[str] = Counter()
    nodes_seen: set[str] = set()
    graph: dict[str, set[str]] = defaultdict(set)
    device_rows: list[dict[str, Any]] = []

    def connect(nodes: list[str]) -> None:
        for node in nodes:
            nodes_seen.add(node.lower())
        lowered = [node.lower() for node in nodes]
        for left in lowered:
            for right in lowered:
                if left != right:
                    graph[left].add(right)

    for line_number, line in lines:
        tokens = line.split()
        head = tokens[0]
        if head.startswith("."):
            directive = head.lower()
            if directive != ".param":
                violations.append({"code": "FORBIDDEN_DIRECTIVE", "line": line_number, "detail": directive})
            elif DYNAMIC_VALUE.search(line):
                violations.append({"code": "DYNAMIC_PARAMETER", "line": line_number, "detail": line})
            continue
        prefix = head[0].upper()
        if prefix in forbidden_prefixes:
            violations.append({"code": "FORBIDDEN_DEVICE", "line": line_number, "detail": head})
            continue
        if prefix in {"R", "L", "C"}:
            if len(tokens) < 4:
                violations.append({"code": "BAD_PASSIVE", "line": line_number, "detail": line})
                continue
            if DYNAMIC_VALUE.search(" ".join(tokens[3:])):
                violations.append({"code": "DYNAMIC_PASSIVE", "line": line_number, "detail": line})
            nodes = tokens[1:3]
            counts[prefix] += 1
            connect(nodes)
            device_rows.append({"name": head, "kind": prefix, "nodes": [node.lower() for node in nodes]})
            continue
        if prefix == "X":
            if len(tokens) < 6:
                violations.append({"code": "BAD_X", "line": line_number, "detail": line})
                continue
            model_index = next((index for index, token in enumerate(tokens[1:], 1) if token in wrappers), None)
            if model_index is None:
                violations.append({"code": "ILLEGAL_X_MODEL", "line": line_number, "detail": line})
                continue
            nodes = tokens[1:model_index]
            model = tokens[model_index]
            if len(nodes) != int(wrappers[model]["terminals"]):
                violations.append({"code": "BAD_X_TERMINALS", "line": line_number, "detail": line})
            parameters = {token.split("=", 1)[0].lower() for token in tokens[model_index + 1:] if "=" in token}
            if not {"l", "w"}.issubset(parameters):
                violations.append({"code": "MISSING_GEOMETRY", "line": line_number, "detail": line})
            if model != "sky130_fd_pr__nfet_g5v0d10v5" and any(node.lower() == "vdd5" for node in nodes):
                violations.append({"code": "STATIC_OVERSTRESS", "line": line_number, "detail": f"{model} touches vdd5"})
            counts["X"] += 1
            counts["active"] += 1
            counts[f"model:{model}"] += 1
            connect(nodes)
            device_rows.append({"name": head, "kind": "X", "model": model, "nodes": [node.lower() for node in nodes]})
            continue
        if prefix == "M":
            if len(tokens) < 6 or tokens[5] not in direct_m:
                violations.append({"code": "ILLEGAL_M_MODEL", "line": line_number, "detail": line})
                continue
            counts["M"] += 1
            counts["active"] += 1
            connect(tokens[1:5])
            device_rows.append({"name": head, "kind": "M", "model": tokens[5], "nodes": [node.lower() for node in tokens[1:5]]})
            continue
        if prefix == "Q":
            if len(tokens) < 5 or tokens[-1] not in direct_q:
                violations.append({"code": "ILLEGAL_Q_MODEL", "line": line_number, "detail": line})
                continue
            counts["Q"] += 1
            counts["active"] += 1
            connect(tokens[1:-1])
            device_rows.append({"name": head, "kind": "Q", "model": tokens[-1], "nodes": [node.lower() for node in tokens[1:-1]]})
            continue
        violations.append({"code": "UNKNOWN_ELEMENT", "line": line_number, "detail": line})

    required_ports = {node.lower() for node in BLOCK_PORTS[block]}
    for port in sorted((required_ports - {"0"}) - nodes_seen):
        violations.append({"code": "MISSING_PORT", "detail": port})

    seen: set[str] = set()
    for node in sorted(nodes_seen):
        if node in seen:
            continue
        queue = deque([node])
        component: set[str] = set()
        while queue:
            current = queue.popleft()
            if current in component:
                continue
            component.add(current)
            queue.extend(graph.get(current, ()))
        seen.update(component)
        if not component.intersection(required_ports):
            violations.append({"code": "DISCONNECTED_COMPONENT", "detail": sorted(component)[:12]})

    minima = MINIMUM_COUNTS.get(block, MINIMUM_COUNTS["default"])
    for kind, minimum in minima.items():
        if counts[kind] < minimum:
            violations.append({"code": "TOO_FEW_DEVICES", "detail": f"{kind}={counts[kind]}, minimum={minimum}"})
    return {
        "block": block,
        "path": str(path),
        "sha256": sha256(path),
        "bytes": len(raw_bytes),
        "counts": dict(sorted(counts.items())),
        "nodes": len(nodes_seen),
        "devices": len(device_rows),
        "violations": violations,
    }


def lint_submission(submission: Path) -> dict[str, Any]:
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    manifest_path = submission / "manifest.json"
    if not manifest_path.is_file():
        return {"eligible": False, "violations": [{"code": "MISSING_MANIFEST", "detail": str(manifest_path)}], "files": []}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"eligible": False, "violations": [{"code": "BAD_MANIFEST", "detail": str(exc)}], "files": []}
    if manifest.get("schema_version") != 1:
        violations.append({"code": "BAD_MANIFEST_SCHEMA", "detail": manifest.get("schema_version")})
    declared = manifest.get("blocks", {})
    if declared != REQUIRED_FILES:
        violations.append({"code": "BLOCK_MAP_MISMATCH", "detail": "manifest blocks must exactly match the public contract"})
    pdk = manifest.get("pdk", {})
    if pdk.get("commit") != allowlist["pdk_commit"] or pdk.get("corner") != "TT":
        violations.append({"code": "PDK_MISMATCH", "detail": pdk})

    file_results = []
    total_bytes = 0
    for block, relative in REQUIRED_FILES.items():
        path = submission / relative
        if not path.is_file():
            violations.append({"code": "MISSING_BLOCK_FILE", "block": block, "detail": relative})
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(submission.resolve())
        except ValueError:
            violations.append({"code": "PATH_ESCAPE", "block": block, "detail": relative})
            continue
        result = lint_file(path, block, allowlist)
        total_bytes += result.get("bytes", 0)
        file_results.append(result)
        for item in result["violations"]:
            violations.append({"block": block, **item})
    if total_bytes > MAX_TOTAL_BYTES:
        violations.append({"code": "SUBMISSION_TOO_LARGE", "detail": f"{total_bytes} bytes"})
    return {
        "eligible": not violations,
        "violations": violations,
        "total_bytes": total_bytes,
        "required_block_count": len(REQUIRED_FILES),
        "present_block_count": len(file_results),
        "files": file_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = lint_submission(args.submission)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["eligible"] else 2)


if __name__ == "__main__":
    main()
