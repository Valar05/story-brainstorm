#!/usr/bin/env python3
"""Merge explicit, sealed bibliography inputs without rewriting source records."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from story_brainstorm import _errors_works, atomic_write, write_json
from tools.audit_bibliography import norm

INPUTS = (("B1", "B1A", 40, 8), ("B2", "B2A", 30, 6), ("B3", "B3", 30, 6))
STRATA = ("adventure", "fantasy", "gothic", "social", "american", "poetry", "drama", "world", "modernist", "theory")
OUTPUTS = ("data/works.json", "data/reserve_works.json", "sources/manifests/bibliography_union.json")
CHECKS = {"creator_match", "evidence_exact", "first_year_ok", "item_match", "language_match", "rights_match", "stored_raw_fields", "title_match", "translation_rights"}

class MergeError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise MergeError(message)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def semantic_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())

def confined(root, relative):
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), "path escapes root: " + relative)
    return path

def read_input(root, relative, snapshots):
    raw = confined(root, relative).read_bytes()
    snapshots[relative] = raw
    return json.loads(raw)

def provenance(root, relative, raw):
    commit = subprocess.check_output(["git", "-C", str(root), "log", "-1", "--format=%H", "--", relative], text=True).strip()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "uncommitted input: " + relative)
    committed = subprocess.check_output(["git", "-C", str(root), "show", commit + ":" + relative])
    require(committed == raw, "input differs from committed provenance: " + relative)
    return {"path": relative, "sha256": digest(raw), "commit": commit}

def receipt_hashes(receipt):
    hashes = dict(receipt.get("artifact_sha256", {}))
    for check in receipt.get("checks", []):
        match = re.fullmatch(r"SHA256 ([^:]+): ([0-9a-f]{64})", check)
        if match:
            path, value = match.groups()
            require(path not in hashes or hashes[path] == value, "contradictory receipt hashes")
            hashes[path] = value
    return hashes

def assemble(root):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise MergeError("jsonschema dependency unavailable; no outputs written") from exc
    snapshots = {}
    work_schema = Draft202012Validator(read_input(root, "schemas/work_record.json", snapshots))
    shard_schema = Draft202012Validator(read_input(root, "schemas/bibliography_shard.json", snapshots))
    accepted, reserves, metadata, sources = [], [], {}, []
    for name, receipt_name, accepted_count, reserve_count in INPUTS:
        paths = {"shard": f"data/bibliography_shards/{name}.json", "audit": f"sources/manifests/audit_{name}.json", "manifest": f"sources/manifests/bibliography_{name}.json", "receipt": f"generated/receipts/{receipt_name}.json"}
        data = {kind: read_input(root, path, snapshots) for kind, path in paths.items()}
        shard, audit, manifest, receipt = (data[k] for k in ("shard", "audit", "manifest", "receipt"))
        shard_schema.validate(shard)
        require(shard["schema_version"] == "1.0", name + ": unsupported shard version")
        require(len(shard["works"]) == accepted_count and len(shard["reserves"]) == reserve_count, name + ": shard count mismatch")
        records = shard["works"] + shard["reserves"]
        require(receipt.get("status") == "complete" and not receipt.get("blockers") and name + "-ready" in receipt.get("dependencies_unlocked", []), name + ": receipt not ready")
        bound_hashes = receipt_hashes(receipt)
        for kind in ("shard", "audit", "manifest"):
            path = paths[kind]
            require(bound_hashes.get(path) == digest(snapshots[path]), name + ": stale/unbound " + kind)
            require(path in receipt.get("changed", []), name + ": receipt omits " + kind)
        require(audit.get("state") == "READY" and audit.get("records") == len(records) and audit.get("pass") == len(records) and audit.get("fail") == 0, name + ": audit not ready")
        audit_rows = audit.get("rows", [])
        require(len(audit_rows) == len(records), name + ": missing audit rows")
        by_id = {row["work_id"]: row for row in audit_rows}
        require(len(by_id) == len(records), name + ": duplicate audit IDs")
        manifest_rows = manifest.get("rows", [])
        meta_by_id = {row["work_id"]: row for row in manifest_rows}
        require(len(meta_by_id) == len(manifest_rows) == len(records), name + ": manifest row mismatch")
        ids = {w["work_id"] for w in records}
        require(ids == set(by_id) == set(meta_by_id), name + ": row joins differ")
        for position, work in enumerate(records):
            work_schema.validate(work)
            require(not _errors_works([work]), name + ": invalid WorkRecord " + work["work_id"])
            row = by_id[work["work_id"]]
            checks = row.get("checks", {})
            require(row.get("status") == "PASS" and not row.get("errors") and CHECKS <= checks.keys() and all(v is True for v in checks.values()), name + ": failed audit row")
            expected = {"title": work["title"], "author": work["author"], "first_publication_year": work["first_publication_year"], "source_item_id": work["source_edition"]["item_id"]}
            require(row.get("expected") == expected, name + ": stale row evidence")
            pub_checks = row.get("publication_catalog", {}).get("checks", {})
            require(bool(pub_checks) and all(v is True for v in pub_checks.values()), name + ": publication audit not green")
            meta = meta_by_id[work["work_id"]]
            selection = "accepted" if position < accepted_count else "reserve"
            require(meta.get("selection") == selection and meta.get("status") == "PASS", name + ": inconsistent manifest selection")
            require(work["work_id"] not in metadata, "duplicate work_id: " + work["work_id"])
            metadata[work["work_id"]] = (name, meta)
        accepted.extend(shard["works"])
        reserves.extend(shard["reserves"])
        sources.append({"shard": name, "accepted": accepted_count, "reserves": reserve_count, "receipt_commit_label": receipt["commit"], "files": {kind: provenance(root, path, snapshots[path]) for kind, path in paths.items()}})
    require(len(accepted) == 100 and len(reserves) == 20, "union requires 100 accepted and 20 reserves")
    all_records = accepted + reserves
    keys = {"work_id": lambda w: w["work_id"], "normalized_title": lambda w: norm(w["title"]), "item_id": lambda w: w["source_edition"]["item_id"], "source_url": lambda w: w["source_edition"]["url"]}
    for label, key in keys.items():
        counts = Counter(key(w) for w in all_records)
        duplicates = sorted(k for k, n in counts.items() if n > 1)
        require(not duplicates, "duplicate " + label + ": " + repr(duplicates))
    authors = Counter(norm(w["author"]) for w in all_records)
    require(max(authors.values()) <= 5, "global author cap exceeded")
    strata, women, non_novel, traditions = Counter(), 0, 0, 0
    classifications = []
    for work in sorted(accepted, key=lambda w: w["work_id"]):
        source, meta = metadata[work["work_id"]]
        woman = meta.get("women_authored", meta.get("woman_authored"))
        require(isinstance(woman, bool), "missing author breadth classification")
        hybrid = meta.get("non_novel_or_hybrid")
        if source == "B3":
            hybrid = meta["form"] not in ("novel", "novella")
        require(isinstance(hybrid, bool), "missing form breadth classification")
        tradition = meta.get("breadth_qualifies", False) if source == "B3" else False
        require(isinstance(tradition, bool), "invalid tradition classification")
        strata[meta["stratum"]] += 1
        women += woman
        non_novel += hybrid
        traditions += tradition
        classifications.append({"work_id": work["work_id"], "shard": source, "stratum": meta["stratum"], "women_authored": woman, "non_novel_or_hybrid": hybrid, "verified_tradition_floor": tradition})
    require(dict(strata) == {s: 10 for s in STRATA}, "stratum quota mismatch")
    require(women >= 20 and non_novel >= 25 and traditions >= 20, "global breadth floor unmet")
    accepted.sort(key=lambda w: w["work_id"])
    reserves.sort(key=lambda w: w["work_id"])
    works_output = {"schema_version": "1.0", "works": accepted}
    reserve_output = {"schema_version": "1.0", "works": reserves}
    manifest = {"schema_version": "1.0", "state": "READY", "sources": sources, "counts": {"accepted": 100, "reserves": 20, "unique_total": 120}, "quotas": {"accepted_by_stratum": dict(sorted(strata.items())), "women_authored_accepted": women, "non_novel_hybrid_conservative": non_novel, "non_anglo_diasporic_translated_verified_floor": traditions}, "classification_policy": "Use sealed per-row manifest flags; B3 non-novel floor excludes both novels and novellas. Non-Anglo/diasporic/translated floor counts only B3 explicitly verified flags. No WorkRecord fields are added or changed.", "classifications": classifications, "global_uniqueness": {k: 120 for k in keys}, "max_author_including_reserves": max(authors.values()), "normalized_author_counts": dict(sorted(authors.items())), "source_records_preserved": True, "record_semantic_sha256": {w["work_id"]: semantic_hash(w) for w in accepted + reserves}, "output_semantic_sha256": {OUTPUTS[0]: semantic_hash(works_output), OUTPUTS[1]: semantic_hash(reserve_output)}, "source_schemas": {p: digest(snapshots[p]) for p in ("schemas/work_record.json", "schemas/bibliography_shard.json")}, "merge_tool_sha256": digest(Path(__file__).read_bytes())}
    return dict(zip(OUTPUTS, (works_output, reserve_output, manifest))), snapshots

def publish(root, outputs, snapshots):
    for relative, raw in snapshots.items():
        require(confined(root, relative).read_bytes() == raw, "input changed before publication: " + relative)
    paths = [confined(root, relative) for relative in OUTPUTS]
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    changed = []
    written = {}
    try:
        for relative, path in zip(OUTPUTS, paths):
            require((path.read_bytes() if path.exists() else None) == before[path], "output changed before write: " + relative)
            if write_json(path, outputs[relative]):
                changed.append(path)
                written[path] = path.read_bytes()
            require(json.loads(path.read_text()) == outputs[relative], "output readback mismatch: " + relative)
    except BaseException:
        for path in reversed(changed):
            require(path.exists() and path.read_bytes() == written[path], "concurrent output change preserved; rollback requires review: " + str(path))
            if before[path] is None:
                path.unlink()
            else:
                atomic_write(path, before[path].decode("utf-8"))
        raise
    return [str(p.relative_to(root)) for p in changed]

def merge(root=ROOT):
    root = Path(root).resolve()
    lock = confined(root, "generated/.bibliography-merge.lock")
    # Portable atomic directory lock; a live or ambiguous prior lock fails closed.
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise MergeError("bibliography merge lock exists; no automatic stale recovery") from exc
    try:
        outputs, snapshots = assemble(root)
        changed = publish(root, outputs, snapshots)
        return {"state": "READY", "accepted": 100, "reserves": 20, "unique": 120, "changed": changed}
    finally:
        lock.rmdir()

def main():
    try:
        result = merge()
    except Exception as exc:
        print(json.dumps({"state": "NOT_READY", "error": type(exc).__name__ + ": " + str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
