"""C9 guardrail tests; synthetic fixtures are not source or semantic evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import jsonschema
from story_brainstorm import _card_errors, primitive_id
from tools import audit_primitive_quality as quality

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/primitive_quality/positive.json"


class PrimitiveQualityTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())

    def result(self, expected=3):
        return quality.audit_data(self.payload, expected)

    def reject(self, code, expected=3):
        result = self.result(expected)
        self.assertEqual(result["state"], "NOT_READY")
        self.assertGreater(result["error_counts"].get(code, 0), 0, result["error_counts"])
        return result

    def set_field(self, index, field, value):
        owner = self.payload["cards"][index]
        if field.startswith("pattern."):
            owner = owner["pattern"]
            field = field.split(".")[1]
        owner[field] = value

    def get_field(self, index, field):
        card = self.payload["cards"][index]
        return card["pattern"][field.split(".")[1]] if field.startswith("pattern.") else card[field]

    def test_hand_authored_positive_schema_engine_and_guardrails(self):
        result = self.result()
        self.assertEqual(result["state"], "READY", result["error_counts"])
        self.assertEqual(result["cards"], 30)
        self.assertEqual(result["works"], 3)
        self.assertEqual(result["semantic_review"], "REQUIRED")
        self.assertIn("does not certify", result["limitation"])
        schema = json.loads((ROOT / "schemas/primitive_card.json").read_text())
        for card in self.payload["cards"]:
            jsonschema.validate(card, schema)
            self.assertEqual(card["primitive_id"], primitive_id(card))
        errors, counts = _card_errors(self.payload["cards"], 30,
                                      {key: value * 3 for key, value in quality.FAMILY_MATRIX.items()})
        self.assertEqual(errors, [])
        self.assertEqual(counts, {key: value * 3 for key, value in quality.FAMILY_MATRIX.items()})

    def test_normalization_unicode_punctuation_case_and_spacing(self):
        self.assertEqual(quality.normalized("Ｃａｒｇｏ—BECOMES__ballast!"), "cargo becomes ballast")
        self.payload["cards"][0]["name"] = "  FLOODGATE—Bargain_Reversed! "
        self.assertEqual(self.result()["state"], "READY")

    def test_all_unique_prose_fields_reject_normalized_duplicate(self):
        baseline = copy.deepcopy(self.payload)
        for field in quality.TEXT_FIELDS:
            with self.subTest(field=field):
                self.payload = copy.deepcopy(baseline)
                self.set_field(1, field, " -- ".join(quality.tokens(self.get_field(0, field))).upper())
                category = "PATTERN_COMPONENT" if field.startswith("pattern.") else field.upper()
                result = self.reject("DUPLICATE_" + category)
                self.assertTrue(any(e["code"] == "DUPLICATE_" + category for e in result["rows"][0]["errors"]))
                self.assertTrue(any(e["code"] == "DUPLICATE_" + category for e in result["rows"][1]["errors"]))

    def test_pattern_component_cross_field_duplicate(self):
        self.payload["cards"][1]["pattern"]["turn"] = self.payload["cards"][0]["pattern"]["setup"]
        self.reject("DUPLICATE_PATTERN_COMPONENT")

    def test_pattern_component_within_card_duplicate(self):
        self.payload["cards"][0]["pattern"]["turn"] = self.payload["cards"][0]["pattern"]["setup"]
        self.reject("DUPLICATE_PATTERN_COMPONENT")

    def test_composite_pattern_duplicate(self):
        self.payload["cards"][1]["pattern"] = copy.deepcopy(self.payload["cards"][0]["pattern"])
        self.reject("DUPLICATE_PATTERN_COMPOSITE")

    def test_template_slot_repetition_with_different_work_ids_and_numbers(self):
        self.payload["cards"][0]["summary"] = "The keeper of fixture-harbor carries 12 sealed parcels across the river."
        self.payload["cards"][10]["summary"] = "The keeper of fixture-orchard carries 43 sealed parcels across the river."
        result = self.reject("TEMPLATE_REPETITION")
        self.assertNotIn("DUPLICATE_SUMMARY", result["error_counts"])

    def test_pattern_template_slot_repetition(self):
        self.payload["cards"][0]["pattern"]["pressure"] = "There are 12 passengers waiting beneath the narrow bridge."
        self.payload["cards"][1]["pattern"]["pressure"] = "There are 19 passengers waiting beneath the narrow bridge."
        self.reject("TEMPLATE_REPETITION")

    def test_name_placeholders(self):
        for name in ("Rescue mechanism under siege", "Rescue primitive under siege", "Rescue mechanisms under siege"):
            with self.subTest(name=name):
                self.payload["cards"][0]["name"] = name
                self.reject("NAME_PLACEHOLDER")

    def test_name_numeric_suffixes(self):
        for name in ("Cargo Becomes Ballast 12", "Cargo Becomes Ballast_12", "Cargo Becomes Ballast #１２", "Cargo Becomes Ballast 12)", "Cargo Becomes Ballast12"):
            with self.subTest(name=name):
                self.payload["cards"][0]["name"] = name
                self.reject("NAME_NUMERIC_SUFFIX")

    def test_name_work_ids_exact_normalized_and_foreign_shape(self):
        for name in ("Floodgate fixture-harbor Bargain", "Floodgate FIXTURE HARBOR Bargain", "Floodgate b1-adventure-001 Bargain"):
            with self.subTest(name=name):
                self.payload["cards"][0]["name"] = name
                self.reject("NAME_WORK_ID")

    def test_each_minimum_word_floor_and_exact_boundary(self):
        baseline = copy.deepcopy(self.payload)
        vocabulary = "Copper lanterns guide tired visitors beneath narrow bridges while patient pilots wait quietly offshore tonight".split()
        for field, minimum in quality.MIN_WORDS.items():
            with self.subTest(field=field):
                self.payload = copy.deepcopy(baseline)
                self.set_field(0, field, " ".join(vocabulary[:minimum - 1]))
                self.reject("SHORT_TEXT")
                self.set_field(0, field, " ".join(vocabulary[:minimum]))
                self.assertEqual(self.result()["state"], "READY")

    def test_padding_with_repeated_words_does_not_meet_substance_floor(self):
        baseline = copy.deepcopy(self.payload)
        for field, minimum in quality.MIN_WORDS.items():
            with self.subTest(field=field):
                self.payload = copy.deepcopy(baseline)
                self.set_field(0, field, " ".join(["repeated"] * (minimum + 20)))
                self.reject("SHORT_TEXT")

    def test_numeric_padding_does_not_count_as_substantive_words(self):
        baseline = copy.deepcopy(self.payload)
        for field in quality.TEXT_FIELDS:
            with self.subTest(field=field):
                self.payload = copy.deepcopy(baseline)
                self.set_field(0, field, "Lanterns " + " ".join(str(n) for n in range(50)) + " drift")
                self.reject("SHORT_TEXT")

    def test_observation_must_not_copy_excerpt(self):
        card = self.payload["cards"][0]
        card["observation"] = " -- ".join(quality.tokens(card["evidence"][0]["short_excerpt"])).upper()
        self.reject("OBSERVATION_IS_EXCERPT")

    def test_boilerplate_all_prose_fields_and_excerpt(self):
        baseline = copy.deepcopy(self.payload)
        for field in quality.TEXT_FIELDS + ("excerpt",):
            with self.subTest(field=field):
                self.payload = copy.deepcopy(baseline)
                text = "This Gutenberg publication is provided for the use of anyone anywhere."
                if field == "excerpt":
                    self.payload["cards"][0]["evidence"][0]["short_excerpt"] = text
                else:
                    self.set_field(0, field, text)
                self.reject("BOILERPLATE")

    def test_publication_boilerplate_variants(self):
        for phrase in ("This eBook is for the use of anyone anywhere", "The license applies to redistribution of this electronic edition", "Credits: A reader and several volunteers", "Produced by the Distributed Proofreaders team", "Transcriber's note correcting the typography", "Title: The Night Harbor", "Author: A Fictional Writer", "Illustrator: A Fictional Painter", "Release date: September 1, 2026", "Most recently updated: yesterday", "at no cost and with almost no restrictions", "You may copy it and give it away", "check the laws of the country where you are located"):
            with self.subTest(phrase=phrase):
                self.payload["cards"][0]["evidence"][0]["short_excerpt"] = phrase
                self.reject("BOILERPLATE")

    def test_narrative_credit_and_production_are_not_publication_boilerplate(self):
        self.payload["cards"][0]["summary"] = "The captain produced the receipt and gave credit to its keeper."
        self.assertEqual(self.result()["state"], "READY")

    def test_known_template_phrases(self):
        for phrase in ("This passage supports a reusable story move with a distinct constraint.", "Source-specific character mechanism grounded in the selected passage.", "The pressure accumulates through observed condition in a reusable scene.", "The pressure accumulates through the observed condition in a reusable scene.", "The observed condition changes the available response for every participant.", "The consequence remains available for later action in the selected narrative.", "Source situation in a newly chosen novel with several named participants."):
            with self.subTest(phrase=phrase):
                self.payload["cards"][0]["inference"] = phrase
                self.reject("TEMPLATE_PROSE")

    def test_generic_patterns_report_separately(self):
        self.payload["cards"][0]["pattern"]["pressure"] = "Pressure accumulates through observed condition in the selected scene."
        self.reject("PATTERN_GENERIC")

    def test_evidence_reference_duplicate_normalized(self):
        ref = copy.deepcopy(self.payload["cards"][0]["evidence"][0])
        ref["location"] = ref["location"].upper().replace(" ", "--")
        ref["short_excerpt"] = ref["short_excerpt"].upper()
        self.payload["cards"][1]["evidence"] = [ref]
        self.reject("DUPLICATE_EVIDENCE_REF")

    def test_renaming_locator_does_not_hide_reused_passage(self):
        ref = copy.deepcopy(self.payload["cards"][0]["evidence"][0])
        ref["location"] = "Invented alternate locator 99"
        self.payload["cards"][1]["evidence"] = [ref]
        result = self.reject("DUPLICATE_EVIDENCE_PASSAGE")
        self.assertNotIn("DUPLICATE_EVIDENCE_REF", result["error_counts"])

    def test_evidence_duplicate_within_card(self):
        self.payload["cards"][0]["evidence"] *= 2
        self.reject("DUPLICATE_EVIDENCE_REF")

    def test_multiple_distinct_evidence_refs_same_work_are_allowed(self):
        self.payload["cards"][0]["evidence"].append({"work_id": "fixture-harbor", "edition_url": "https://example.invalid/quality/fixture-harbor", "location": "Synthetic scene alternative angle", "short_excerpt": "The keeper reached for the gate after watching her hands.", "excerpt_words": 11})
        self.assertEqual(self.result()["state"], "READY")

    def test_evidence_missing_empty_and_malformed(self):
        for evidence in (None, [], "not a list", [None], [{}], [{"work_id": []}]):
            with self.subTest(evidence=evidence):
                self.payload["cards"][0]["evidence"] = evidence
                self.reject("EVIDENCE")

    def test_multiple_works_in_one_card_is_not_an_extraction(self):
        self.payload["cards"][0]["evidence"].append(copy.deepcopy(self.payload["cards"][10]["evidence"][0]))
        self.reject("WORK_ASSIGNMENT")

    def test_expected_distinct_work_count(self):
        self.reject("WORK_COUNT", expected=4)

    def test_card_total_count(self):
        self.payload["cards"].pop()
        self.reject("CARD_COUNT")

    def test_exact_ten_per_work_even_when_global_total_matches(self):
        self.payload["cards"][0]["evidence"][0]["work_id"] = "fixture-orchard"
        self.reject("WORK_CARD_COUNT")

    def test_per_work_family_matrix_even_when_global_quotas_match(self):
        self.payload["cards"][0]["family"], self.payload["cards"][13]["family"] = "speech", "story"
        result = self.reject("WORK_FAMILY_MATRIX")
        self.assertNotIn("CARD_COUNT", result["error_counts"])
        self.assertNotIn("WORK_CARD_COUNT", result["error_counts"])

    def test_family_missing_unknown_and_wrong_type(self):
        for family in (None, "unknown", []):
            self.payload["cards"][0]["family"] = family
            self.reject("FAMILY")

    def test_pattern_wrong_shape(self):
        baseline = copy.deepcopy(self.payload)
        for value in (None, [], {}, {"setup": "Only one field is present in this broken pattern."}, {**baseline["cards"][0]["pattern"], "extra": "forbidden"}):
            with self.subTest(value=value):
                self.payload = copy.deepcopy(baseline)
                self.payload["cards"][0]["pattern"] = value
                self.reject("PATTERN_SHAPE")

    def test_text_wrong_types_fail_closed(self):
        for field in quality.TEXT_FIELDS:
            with self.subTest(field=field):
                self.set_field(0, field, {"unexpected": "object"})
                self.reject("SHORT_TEXT")

    def test_contextual_subtype_required_and_valid(self):
        for subtype in (None, "unknown", []):
            self.payload["cards"][9]["subtype"] = subtype
            self.reject("CONTEXTUAL_SUBTYPE")

    def test_subtype_forbidden_on_other_families(self):
        for index in (0, 3, 5, 7, 8):
            with self.subTest(family=self.payload["cards"][index]["family"]):
                self.payload["cards"][index]["subtype"] = "setting"
                self.reject("SUBTYPE_NON_CONTEXTUAL")

    def test_contextual_diversity_at_least_three(self):
        self.payload["cards"][29]["subtype"] = "object"
        result = self.reject("CONTEXTUAL_DIVERSITY")
        self.assertNotIn("CONTEXTUAL_DOMINANCE", result["error_counts"])

    def test_contextual_collapse_reports_dominance(self):
        for index in (9, 19, 29):
            self.payload["cards"][index]["subtype"] = "setting"
        self.reject("CONTEXTUAL_DOMINANCE")

    def test_contextual_ceiling_exact_boundary_and_above_with_three_subtypes(self):
        # Duplicate unrelated prose is intentionally red; this focused ablation
        # isolates whether the independently reported dominance gate is correct.
        self.payload["cards"] = [copy.deepcopy(self.payload["cards"][9]) for _ in range(10)]
        for index, card in enumerate(self.payload["cards"]):
            card["evidence"][0]["work_id"] = "work-" + str(index)
            card["subtype"] = "setting" if index < 7 else ("object" if index < 9 else "institution")
        self.assertNotIn("CONTEXTUAL_DOMINANCE", self.result(10)["error_counts"])
        self.payload["cards"][8]["subtype"] = "setting"
        result = self.reject("CONTEXTUAL_DOMINANCE", expected=10)
        self.assertEqual(len(result["contextual_subtype_counts"]), 3)

    def test_single_work_does_not_require_three_subtypes(self):
        self.payload["cards"] = self.payload["cards"][:10]
        self.assertEqual(self.result(1)["state"], "READY")

    def test_malformed_top_level_and_expected_count(self):
        for payload in (None, [], {}, {"cards": None}, {"cards": "bad"}):
            with self.subTest(payload=payload):
                self.assertEqual(quality.audit_data(payload, 3)["state"], "NOT_READY")
        for expected in (0, -1, True, None, "3"):
            with self.subTest(expected=expected):
                self.assertIn("EXPECTED_WORKS", quality.audit_data(self.payload, expected)["error_counts"])
        self.payload["cards"][0] = None
        self.reject("CARD_SHAPE")

    def test_deterministic_report_and_native_writer_noop(self):
        self.assertEqual(self.result(), self.result())
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "audit.json"
            first = quality.audit(FIXTURE, out, 3)
            before = out.read_bytes(), out.stat().st_mtime_ns, out.stat().st_ino
            second = quality.audit(FIXTURE, out, 3)
            self.assertEqual(first, second)
            self.assertEqual(before, (out.read_bytes(), out.stat().st_mtime_ns, out.stat().st_ino))
            self.assertEqual(first["input_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())

    def test_native_atomic_failure_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "audit.json"
            quality.audit(FIXTURE, out, 3)
            before = out.read_bytes()
            with patch.object(Path, "replace", side_effect=OSError("injected pre-replace failure")):
                with self.assertRaises(OSError):
                    quality.audit(FIXTURE, out, 4)
            self.assertEqual(out.read_bytes(), before)

    def test_input_output_alias_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.json"
            path.write_bytes(FIXTURE.read_bytes())
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                quality.audit(path, path, 3)
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_and_missing_input_produce_not_ready_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path, out = Path(directory) / "cards.json", Path(directory) / "audit.json"
            for raw in (b"{", b"\xff", None):
                if raw is not None:
                    path.write_bytes(raw)
                elif path.exists():
                    path.unlink()
                result = quality.audit(path, out, 3)
                self.assertEqual(result["state"], "NOT_READY")
                self.assertIn("INPUT_READ", result["error_counts"])
                self.assertEqual(json.loads(out.read_bytes()), result)

    def test_production_cli_ready_red_invalid_count_and_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "audit.json"
            command = [sys.executable, str(ROOT / "tools/audit_primitive_quality.py"), "--cards", str(FIXTURE), "--out", str(out), "--expected-works", "3"]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(first.stdout)["state"], "READY")
            before = out.read_bytes(), out.stat().st_mtime_ns
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(before, (out.read_bytes(), out.stat().st_mtime_ns))
            command[-1] = "4"
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            self.assertEqual(json.loads(out.read_bytes())["state"], "NOT_READY")
            command[-1] = "0"
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_combined_e_shape_rejected_through_production_cli(self):
        # Self-contained regression ablation. The independent exact E blob run
        # is sealed in rejected_E_expected.json and C9's receipt, not replaced
        # by this synthetic test or required as an unmerged Git dependency.
        for index, card in enumerate(self.payload["cards"]):
            wid = card["evidence"][0]["work_id"]
            card["name"] = f"{card['family']} mechanism {wid} {index + 1}"
            card["summary"] = f"Source-specific {card['family']} mechanism grounded in the selected passage."
            card["observation"] = "This eBook is for the use of anyone anywhere in the United States and"
            card["evidence"][0]["short_excerpt"] = card["observation"]
            card["evidence"][0]["excerpt_words"] = len(card["observation"].split())
            card["inference"] = f"This passage supports a reusable {card['family']} move with a distinct source constraint."
            card["pattern"] = {"setup": f"Source situation in {wid}",
                               "pressure": f"{card['family']} pressure accumulates through the observed condition",
                               "turn": "The observed condition changes the available response",
                               "residue": "The consequence remains available for later action"}
            if card["family"] == "contextual":
                card["subtype"] = "setting"
        with tempfile.TemporaryDirectory() as directory:
            cards, out = Path(directory) / "synthetic-E-shape.json", Path(directory) / "audit.json"
            cards.write_text(json.dumps(self.payload))
            command = [sys.executable, str(ROOT / "tools/audit_primitive_quality.py"), "--cards", str(cards), "--out", str(out), "--expected-works", "3"]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads(out.read_bytes())
            self.assertEqual(result["state"], "NOT_READY")
            self.assertEqual(result["cards_with_errors"], 30)
            for code, minimum in {"NAME_PLACEHOLDER": 30, "NAME_WORK_ID": 30,
                                  "NAME_NUMERIC_SUFFIX": 30, "BOILERPLATE": 60,
                                  "TEMPLATE_PROSE": 180, "TEMPLATE_REPETITION": 180,
                                  "PATTERN_GENERIC": 120, "OBSERVATION_IS_EXCERPT": 30,
                                  "CONTEXTUAL_DIVERSITY": 4, "CONTEXTUAL_DOMINANCE": 4}.items():
                with self.subTest(code=code):
                    self.assertGreaterEqual(result["error_counts"].get(code, 0), minimum)


if __name__ == "__main__":
    unittest.main()
