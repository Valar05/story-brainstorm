"""Deterministic primitive-card guardrails, not semantic or source certification."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from story_brainstorm import write_json

FAMILY_MATRIX = {"story": 3, "speech": 2, "character": 2,
                 "conflict": 1, "structure": 1, "contextual": 1}
SUBTYPES = {"setting", "institution", "object", "transformation", "tone_pressure"}
PATTERN_FIELDS = ("setup", "pressure", "turn", "residue")
# Calibration floors, not measures of literary merit. See the positive fixture.
MIN_WORDS = {"name": 3, "summary": 8, "observation": 10, "inference": 10,
             **{"pattern." + key: 6 for key in PATTERN_FIELDS}}
MIN_DISTINCT_WORDS = {"name": 3, "summary": 6, "observation": 7, "inference": 7,
                      **{"pattern." + key: 5 for key in PATTERN_FIELDS}}
TEXT_FIELDS = tuple(MIN_WORDS)
BOILERPLATE = re.compile(
    r"\b(?:gutenberg|e\s*book|licen[cs]e|transcrib\w*|proofread\w*)\b"
    r"|\bproduced by\b|\brelease date\b|\bmost recently updated\b"
    r"|\bat no cost and with almost no restrictions\b"
    r"|\byou may copy it\b|\bcheck the laws of the country\b"
    r"|\bfor the use of anyone anywhere\b", re.I)
METADATA_LINE = re.compile(r"^\s*(?:title|author|illustrator|language|encoding|release date|credits)\s*:", re.I)
TEMPLATE = re.compile(
    r"\bthis passage supports\b|\bsource specific\b.*\bgrounded\b"
    r"|\bpressure accumulates through (?:the )?observed condition\b"
    r"|\b(?:the )?observed condition changes\b"
    r"|\b(?:the )?consequence remains available\b"
    r"|\bsource situation in\b", re.I)
PLACEHOLDER = re.compile(r"\b(?:mechanisms?|primitives?)\b")
NUMERIC_SUFFIX = re.compile(r"\d+[\s.)\]]*$")
WORK_ID_SHAPE = re.compile(r"\b[a-z][a-z0-9]*[-_][a-z][a-z0-9_-]*[-_]\d+\b", re.I)
LIMITATION = ("READY means only deterministic structural and anti-template guardrails passed. "
              "It does not certify source truth, accurate locators, interpretation, cultural "
              "specificity, rights, or freedom from voice imitation. Independent semantic "
              "review, schema validation, and the source-evidence audit remain mandatory.")


def tokens(value):
    """NFKC/casefold lexical tokens: punctuation and underscore are separators."""
    if not isinstance(value, str):
        return []
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold())


def normalized(value):
    return " ".join(tokens(value))


def template_key(value, work_ids):
    value = normalized(value)
    for work_id in sorted(work_ids, key=lambda v: (-len(normalized(v)), v)):
        key = normalized(work_id)
        if key:
            value = re.sub(r"(?<!\w)" + re.escape(key) + r"(?!\w)", "workslot", value)
    return re.sub(r"\b\d+\b", "numberslot", value)


def audit_data(payload, expected_works):
    """Pure audit: stable zero-based rows and coded errors, no network or writes."""
    global_errors = []
    rows = []

    def global_error(code, detail):
        global_errors.append({"code": code, "detail": detail})

    if type(expected_works) is not int or expected_works < 1:
        global_error("EXPECTED_WORKS", "expected_works must be a positive integer")
    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list):
        global_error("CARDS_SHAPE", "input must be an object with a cards array")
        cards = []
    if type(expected_works) is int and expected_works > 0 and len(cards) != expected_works * 10:
        global_error("CARD_COUNT", f"expected {expected_works * 10} cards; found {len(cards)}")

    work_ids = set()
    for card in cards:
        if isinstance(card, dict) and isinstance(card.get("evidence"), list):
            for ref in card["evidence"]:
                if isinstance(ref, dict) and isinstance(ref.get("work_id"), str) and ref["work_id"].strip():
                    work_ids.add(ref["work_id"])
    work_matrix = {wid: Counter() for wid in sorted(work_ids)}
    duplicates = defaultdict(list)
    templates = defaultdict(list)
    contextual = []

    def error(index, code, field, detail):
        item = {"code": code, "field": field, "detail": detail}
        if item not in rows[index]["errors"]:
            rows[index]["errors"].append(item)

    def register(category, value, index, field):
        if value:
            duplicates[(category, value)].append((index, field))

    for index, card in enumerate(cards):
        rows.append({"card_index": index, "primitive_id": card.get("primitive_id") if isinstance(card, dict) else None,
                     "work_id": None, "status": "PASS", "errors": []})
        if not isinstance(card, dict):
            error(index, "CARD_SHAPE", "card", "card must be an object")
            continue
        family = card.get("family")
        if not isinstance(family, str) or family not in FAMILY_MATRIX:
            error(index, "FAMILY", "family", "unknown or missing primitive family")
        evidence = card.get("evidence")
        local_ids = set()
        if not isinstance(evidence, list) or not evidence:
            error(index, "EVIDENCE", "evidence", "at least one evidence reference is required")
            evidence = []
        for eidx, ref in enumerate(evidence):
            field = f"evidence.{eidx}"
            if not isinstance(ref, dict):
                error(index, "EVIDENCE", field, "evidence must be an object")
                continue
            for key in ("work_id", "edition_url", "location", "short_excerpt"):
                if not isinstance(ref.get(key), str) or not ref[key].strip():
                    error(index, "EVIDENCE", field + "." + key, "nonempty string required")
            wid = ref.get("work_id")
            if isinstance(wid, str) and wid.strip():
                local_ids.add(wid)
            excerpt = ref.get("short_excerpt")
            if isinstance(excerpt, str):
                if BOILERPLATE.search(normalized(excerpt)) or METADATA_LINE.search(excerpt):
                    error(index, "BOILERPLATE", field + ".short_excerpt", "publication/license/credit boilerplate is not body evidence")
                if normalized(excerpt) and normalized(excerpt) == normalized(card.get("observation")):
                    error(index, "OBSERVATION_IS_EXCERPT", "observation", "observation must describe the source action, not copy its excerpt")
            if all(isinstance(ref.get(k), str) and ref[k].strip() for k in ("work_id", "edition_url", "location", "short_excerpt")):
                key = tuple(normalized(ref[k]) for k in ("work_id", "edition_url", "location", "short_excerpt"))
                register("EVIDENCE_REF", key, index, field)
                # A renamed locator must not disguise reuse of the same passage.
                register("EVIDENCE_PASSAGE", (key[0], key[1], key[3]), index, field)
        if len(local_ids) != 1:
            error(index, "WORK_ASSIGNMENT", "evidence", "each extracted card must reference exactly one work")
        else:
            wid = next(iter(local_ids))
            rows[index]["work_id"] = wid
            if isinstance(family, str):
                work_matrix[wid][family] += 1

        pattern = card.get("pattern")
        if not isinstance(pattern, dict) or set(pattern) != set(PATTERN_FIELDS):
            error(index, "PATTERN_SHAPE", "pattern", "pattern must contain exactly setup, pressure, turn, residue")
            pattern = pattern if isinstance(pattern, dict) else {}
        for field in TEXT_FIELDS:
            value = pattern.get(field.split(".")[1]) if field.startswith("pattern.") else card.get(field)
            words = [word for word in tokens(value) if any(char.isalpha() for char in word)]
            if not isinstance(value, str) or len(words) < MIN_WORDS[field] or len(set(words)) < MIN_DISTINCT_WORDS[field]:
                error(index, "SHORT_TEXT", field, f"requires at least {MIN_WORDS[field]} lexical words and {MIN_DISTINCT_WORDS[field]} distinct words")
            if not isinstance(value, str):
                continue
            norm = normalized(value)
            if BOILERPLATE.search(norm) or METADATA_LINE.search(value):
                error(index, "BOILERPLATE", field, "publication/license/credit boilerplate is not an extracted mechanism")
            if TEMPLATE.search(norm):
                error(index, "TEMPLATE_PROSE", field, "known generic extraction template")
                if field.startswith("pattern."):
                    error(index, "PATTERN_GENERIC", field, "known generic pattern component")
            register("PATTERN_COMPONENT" if field.startswith("pattern.") else field.upper(), norm, index, field)
            key = template_key(value, work_ids)
            if key:
                templates[("PATTERN_COMPONENT" if field.startswith("pattern.") else field.upper(), key)].append((index, field))
        name = card.get("name")
        if isinstance(name, str):
            norm = normalized(name)
            if PLACEHOLDER.search(norm):
                error(index, "NAME_PLACEHOLDER", "name", "mechanism/primitive placeholder names are forbidden")
            if NUMERIC_SUFFIX.search(unicodedata.normalize("NFKC", name)):
                error(index, "NAME_NUMERIC_SUFFIX", "name", "numeric placeholder suffix is forbidden")
            if WORK_ID_SHAPE.search(name) or any(re.search(r"(?<!\w)" + re.escape(normalized(wid)) + r"(?!\w)", norm) for wid in work_ids):
                error(index, "NAME_WORK_ID", "name", "work identifiers must not be used as mechanism names")
        composite = tuple(normalized(pattern.get(k)) for k in PATTERN_FIELDS)
        if all(composite):
            register("PATTERN_COMPOSITE", composite, index, "pattern")
        if family == "contextual":
            subtype = card.get("subtype")
            if not isinstance(subtype, str) or subtype not in SUBTYPES:
                error(index, "CONTEXTUAL_SUBTYPE", "subtype", "contextual cards require a taxonomy subtype")
            else:
                contextual.append((index, subtype))
        elif "subtype" in card:
            error(index, "SUBTYPE_NON_CONTEXTUAL", "subtype", "only contextual cards may have subtype")

    for (category, _), members in sorted(duplicates.items(), key=lambda item: repr(item[0])):
        if len(members) > 1:
            first = min(members)
            for index, field in members:
                error(index, "DUPLICATE_" + category, field, f"normalized value reused; first occurrence card {first[0]} field {first[1]}")
    for _key, members in sorted(templates.items(), key=lambda item: repr(item[0])):
        if len(members) > 1:
            first = min(members)
            for index, field in members:
                error(index, "TEMPLATE_REPETITION", field, f"repeated wording after punctuation/case/work-ID/numeric-slot normalization; first occurrence card {first[0]} field {first[1]}")
    if type(expected_works) is int and len(work_ids) != expected_works:
        global_error("WORK_COUNT", f"expected {expected_works} evidence works; found {len(work_ids)}")
    for wid, counts in work_matrix.items():
        if sum(counts.values()) != 10:
            global_error("WORK_CARD_COUNT", f"{wid}: expected 10 cards; found {sum(counts.values())}")
        if dict(counts) != FAMILY_MATRIX:
            global_error("WORK_FAMILY_MATRIX", f"{wid}: expected {FAMILY_MATRIX}; found {dict(sorted(counts.items()))}")
    subtype_counts = Counter(subtype for _, subtype in contextual)
    if len(work_ids) > 1:
        if len(subtype_counts) < 3:
            global_error("CONTEXTUAL_DIVERSITY", "multi-work shard requires at least three distinct contextual subtypes")
            for index, _ in contextual:
                error(index, "CONTEXTUAL_DIVERSITY", "subtype", "shard has fewer than three contextual subtypes")
        if subtype_counts and 10 * max(subtype_counts.values()) > 7 * len(contextual):
            dominant = sorted(k for k, v in subtype_counts.items() if 10 * v > 7 * len(contextual))
            global_error("CONTEXTUAL_DOMINANCE", f"subtypes exceed 70 percent of contextual cards: {dominant}")
            for index, subtype in contextual:
                if subtype in dominant:
                    error(index, "CONTEXTUAL_DOMINANCE", "subtype", "subtype exceeds 70 percent shard ceiling")
    for row in rows:
        row["errors"].sort(key=lambda e: (e["code"], e["field"], e["detail"]))
        row["status"] = "FAIL" if row["errors"] else "PASS"
    global_errors.sort(key=lambda e: (e["code"], e["detail"]))
    error_counts = Counter(e["code"] for e in global_errors)
    error_counts.update(e["code"] for row in rows for e in row["errors"])
    return {"schema_version": "1.0", "auditor": "primitive-quality-guardrails-v1",
            "state": "NOT_READY" if error_counts else "READY", "semantic_review": "REQUIRED",
            "limitation": LIMITATION, "expected_works": expected_works, "cards": len(cards),
            "works": len(work_ids), "cards_with_errors": sum(r["status"] == "FAIL" for r in rows),
            "error_counts": dict(sorted(error_counts.items())), "global_errors": global_errors,
            "work_family_counts": {wid: dict(sorted(counts.items())) for wid, counts in work_matrix.items()},
            "contextual_subtype_counts": dict(sorted(subtype_counts.items())),
            "thresholds": {"minimum_words": MIN_WORDS, "minimum_distinct_words": MIN_DISTINCT_WORDS,
                           "contextual_minimum_subtypes_multi_work": 3, "contextual_maximum_percent": 70},
            "rows": rows}


def audit(cards_path, out_path, expected_works):
    cards_path, out_path = Path(cards_path), Path(out_path)
    if cards_path.resolve() == out_path.resolve():
        raise ValueError("audit output must not overwrite input cards")
    try:
        raw = cards_path.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeError, ValueError) as exc:
        result = audit_data(None, expected_works)
        result["global_errors"].append({"code": "INPUT_READ", "detail": type(exc).__name__})
        result["error_counts"]["INPUT_READ"] = 1
        result["input_sha256"] = None
    else:
        result = audit_data(payload, expected_works)
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(out_path, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-works", type=int, required=True,
                        help="positive expected distinct evidence-work count; ten cards per work")
    args = parser.parse_args(argv)
    if args.expected_works < 1:
        parser.error("--expected-works must be positive")
    try:
        result = audit(args.cards, args.out, args.expected_works)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"quality audit cannot write output: {exc}\n")
    print(json.dumps({k: result[k] for k in ("state", "cards", "works", "cards_with_errors", "error_counts", "semantic_review")}, sort_keys=True))
    return 0 if result["state"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
