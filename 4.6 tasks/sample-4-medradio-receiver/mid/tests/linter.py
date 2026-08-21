from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_TOTAL_BYTES = 5_000_000
TAG_PATTERN = re.compile(r"^[RLCMQX](BIAS|LNA|MIX|CBPF|TUNE|LIM|XTAL|PFD|CP|DIV|COUNT|MASH|POR|QVCO)_", re.I)
PARAM_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass
class Finding:
    code: str
    severity: str
    file: str
    line: int
    message: str


class CandidateRejected(ValueError):
    pass


def _logical_lines(text: str) -> list[tuple[int, str]]:
    logical: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(("*", ";")):
            continue
        if stripped.startswith("+"):
            if not logical:
                raise CandidateRejected(f"line {number}: orphan continuation")
            start, prior = logical[-1]
            logical[-1] = (start, prior + " " + stripped[1:].strip())
        else:
            logical.append((number, stripped))
    return logical


def _instance_nodes(tokens: list[str], prefix: str, wrappers: set[str]) -> list[str]:
    if prefix in {"R", "L", "C"}:
        return tokens[1:3]
    if prefix == "M":
        return tokens[1:5]
    if prefix == "Q":
        return tokens[1:5]
    if prefix == "X":
        nonparams = [token for token in tokens[1:] if not PARAM_TOKEN.match(token)]
        if len(nonparams) < 2 or nonparams[-1].casefold() not in wrappers:
            return []
        return nonparams[:-1]
    return []


def _canonical_instances(path: Path, config: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    wrappers = {item.casefold() for item in config["allowed_transistor_wrappers"]}
    records: dict[str, tuple[str, ...]] = {}
    for _, line in _logical_lines(path.read_text(encoding="utf-8")):
        if line.startswith("."):
            continue
        tokens = tuple(line.split())
        if tokens[0].casefold() in records:
            raise CandidateRejected(f"duplicate instance name {tokens[0]} in {path.name}")
        prefix = tokens[0][0].upper()
        if prefix == "X":
            nonparams = [token for token in tokens[1:] if not PARAM_TOKEN.match(token)]
            if not nonparams or nonparams[-1].casefold() not in wrappers:
                raise CandidateRejected(f"illegal X wrapper in {path.name}: {tokens[0]}")
        records[tokens[0].casefold()] = tuple(token.casefold() for token in tokens)
    return records


def lint_candidate(root: Path, config_path: Path, trusted_pdk_root: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text())
    findings: list[Finding] = []
    required = [root / item for item in config["required_files"]]
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    if missing:
        return {"eligible": False, "findings": [{"code": "MISSING_ARTIFACT", "severity": "gate", "file": item, "line": 0, "message": "required flattened artifact is missing"} for item in missing]}
    total = sum(path.stat().st_size for path in required)
    if total <= 0 or total > MAX_TOTAL_BYTES:
        return {"eligible": False, "findings": [{"code": "ARTIFACT_SIZE", "severity": "gate", "file": ".", "line": 0, "message": f"artifact bytes {total} outside allowed range"}]}

    allowed_directives = {item.casefold() for item in config["allowed_directives"]}
    wrappers = {item.casefold() for item in config["allowed_transistor_wrappers"]}
    direct_m_models = {item.casefold() for item in config["allowed_direct_m_models"]}
    expected_include = config["allowed_pdk_include"]
    tag_counts: Counter[str] = Counter()
    tag_transistors: Counter[str] = Counter()
    graph: dict[str, set[str]] = defaultdict(set)
    top_nodes: set[str] = set()

    for path in required:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            findings.append(Finding("NON_UTF8", "gate", relative, 0, "artifact must be UTF-8"))
            continue
        include_count = 0
        names: set[str] = set()
        for number, line in _logical_lines(text):
            tokens = line.split()
            token = tokens[0]
            lower = token.casefold()
            if line.startswith("."):
                if lower not in allowed_directives:
                    findings.append(Finding("FORBIDDEN_DIRECTIVE", "gate", relative, number, token))
                elif lower == ".include":
                    match = re.match(r'(?i)^\.include\s+["\']?([^"\']+)["\']?$', line)
                    included = match.group(1) if match else ""
                    if included != expected_include:
                        findings.append(Finding("ILLEGAL_INCLUDE", "gate", relative, number, included or line))
                    else:
                        include_count += 1
                continue
            prefix = token[0].upper()
            if prefix not in config["legal_physical_prefixes"]:
                findings.append(Finding("FORBIDDEN_ELEMENT", "gate", relative, number, token))
                continue
            key = token.casefold()
            if key in names:
                findings.append(Finding("DUPLICATE_INSTANCE", "gate", relative, number, token))
            names.add(key)
            match = TAG_PATTERN.match(token)
            if not match:
                findings.append(Finding("UNTAGGED_INSTANCE", "gate", relative, number, token))
                continue
            tag = match.group(1).upper()
            if relative == "candidate.cir":
                tag_counts[tag] += 1
                if prefix in {"M", "Q", "X"}:
                    tag_transistors[tag] += 1
            if prefix == "X":
                nonparams = [item for item in tokens[1:] if not PARAM_TOKEN.match(item)]
                wrapper = nonparams[-1].casefold() if nonparams else ""
                if wrapper not in wrappers:
                    findings.append(Finding("ILLEGAL_X", "gate", relative, number, wrapper or token))
                elif len(nonparams) != 5:
                    findings.append(Finding("ILLEGAL_X_TERMINALS", "gate", relative, number, f"{token} must have exactly four transistor terminals"))
            nodes = [node.casefold() for node in _instance_nodes(tokens, prefix, wrappers)]
            if relative == "candidate.cir":
                top_nodes.update(nodes)
                for left in nodes:
                    for right in nodes:
                        if left != right:
                            graph[left].add(right)
            if prefix == "M" and len(tokens) >= 6:
                model = tokens[5].casefold()
                if model not in direct_m_models:
                    findings.append(Finding("NON_SKY130_M", "gate", relative, number, model))
            elif prefix == "M":
                findings.append(Finding("M_TERMINALS", "gate", relative, number, f"{token} lacks four terminals and an approved model"))
            if prefix == "Q":
                findings.append(Finding("UNAPPROVED_Q_MODEL", "gate", relative, number, "No BJT wrapper is allow-listed in this reference PDK subset"))
        if include_count != 1:
            findings.append(Finding("INCLUDE_COUNT", "gate", relative, 0, f"expected one trusted PDK include, found {include_count}"))

    for tag, minimum in config["required_tags"].items():
        if tag_counts[tag] < minimum:
            findings.append(Finding("BLOCK_DEVICE_COUNT", "gate", "candidate.cir", 0, f"{tag} has {tag_counts[tag]} physical instances, requires at least {minimum}"))
        transistor_minimum = max(2, minimum // 2)
        if tag_transistors[tag] < transistor_minimum:
            findings.append(Finding("BLOCK_TRANSISTOR_COUNT", "gate", "candidate.cir", 0, f"{tag} has {tag_transistors[tag]} transistors, requires at least {transistor_minimum}"))

    missing_nodes = sorted(set(item.casefold() for item in config["required_top_nodes"]) - top_nodes)
    if missing_nodes:
        findings.append(Finding("MISSING_TOP_NODE", "gate", "candidate.cir", 0, ", ".join(missing_nodes)))
    else:
        start = "rfin"
        seen = {start}
        queue: deque[str] = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in graph[node] - seen:
                seen.add(neighbor)
                queue.append(neighbor)
        for required_node in ("vo", "rssi", "rfout"):
            if required_node not in seen:
                findings.append(Finding("DISCONNECTED_SIGNAL_PATH", "gate", "candidate.cir", 0, f"rfin cannot reach {required_node}"))

    parent_map = {
        "blocks/bias.cir": "blocks/receiver.cir",
        "blocks/lna.cir": "blocks/receiver.cir",
        "blocks/mixer.cir": "blocks/receiver.cir",
        "blocks/cbpf.cir": "blocks/receiver.cir",
        "blocks/limiter.cir": "blocks/receiver.cir",
        "blocks/crystal.cir": "blocks/synth.cir",
        "blocks/pfd_cp.cir": "blocks/synth.cir",
        "blocks/por.cir": "blocks/synth.cir",
        "blocks/prescaler.cir": "blocks/synth.cir",
        "blocks/counter.cir": "blocks/synth.cir",
        "blocks/swallow.cir": "blocks/synth.cir",
        "blocks/mash.cir": "blocks/synth.cir",
        "blocks/qvco.cir": "blocks/synth.cir",
        "blocks/receiver.cir": "candidate.cir",
        "blocks/synth.cir": "candidate.cir",
        "blocks/tuning.cir": "candidate.cir",
    }
    for child_name, parent_name in parent_map.items():
        try:
            child = _canonical_instances(root / child_name, config)
            parent = _canonical_instances(root / parent_name, config)
        except CandidateRejected as error:
            findings.append(Finding("SUBSET_PARSE", "gate", child_name, 0, str(error)))
            continue
        for name, tokens in child.items():
            if parent.get(name) != tokens:
                findings.append(Finding("BLOCK_NOT_IN_PARENT", "gate", child_name, 0, f"{name} is absent or changed in {parent_name}"))

    pdk_shim = trusted_pdk_root / "sky130_tt.inc"
    if not pdk_shim.is_file():
        findings.append(Finding("PDK_MISSING", "gate", str(pdk_shim), 0, "trusted PDK shim is unavailable"))
    else:
        digest = hashlib.sha256(pdk_shim.read_bytes()).hexdigest()
        if len(digest) != 64:
            findings.append(Finding("PDK_HASH", "gate", str(pdk_shim), 0, "trusted PDK hash failed"))

    serialized = [finding.__dict__ for finding in findings]
    return {
        "eligible": not any(item["severity"] == "gate" for item in serialized),
        "total_bytes": total,
        "tag_counts": dict(tag_counts),
        "tag_transistor_counts": dict(tag_transistors),
        "findings": serialized,
    }
