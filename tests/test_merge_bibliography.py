import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import merge_bibliography as merger

class BibliographyMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.relative = ["schemas/work_record.json", "schemas/bibliography_shard.json"]
        for name, receipt, _, _ in merger.INPUTS:
            cls.relative += [f"data/bibliography_shards/{name}.json", f"sources/manifests/audit_{name}.json", f"sources/manifests/bibliography_{name}.json", f"generated/receipts/{receipt}.json"]
        cls.original = {p: (merger.ROOT / p).read_bytes() for p in cls.relative}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.STDOUT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bibliography-merge-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative, raw in self.original.items():
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Bibliography fixture")
        self.commit()
        self.old_outputs = {}
        for relative in merger.OUTPUTS:
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"old_output": true}\n')
            self.old_outputs[relative] = p.read_bytes()

    def commit(self):
        self.git("add", "--", *self.relative)
        self.git("commit", "-qm", "Seal explicit fixture inputs", "--allow-empty")

    def load(self, relative):
        return json.loads((self.root / relative).read_text())

    def put(self, relative, obj):
        (self.root / relative).write_text(json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n")

    def reseal(self, name):
        receipt_name = {n: r for n, r, _, _ in merger.INPUTS}[name]
        rp = f"generated/receipts/{receipt_name}.json"
        receipt = self.load(rp)
        paths = [f"data/bibliography_shards/{name}.json", f"sources/manifests/audit_{name}.json", f"sources/manifests/bibliography_{name}.json"]
        hashes = {p: merger.digest((self.root / p).read_bytes()) for p in paths}
        receipt["checks"] = [v for v in receipt["checks"] if not v.startswith("SHA256 ")] + ["SHA256 " + p + ": " + h for p, h in hashes.items()]
        if "artifact_sha256" in receipt:
            receipt["artifact_sha256"] = hashes
        self.put(rp, receipt)
        self.commit()

    def unchanged(self):
        self.assertEqual(self.old_outputs, {p: (self.root / p).read_bytes() for p in merger.OUTPUTS})
        self.assertFalse((self.root / "generated/.bibliography-merge.lock").exists())

    def reject(self, expression=None):
        with self.assertRaisesRegex(Exception, expression or ".+"):
            merger.merge(self.root)
        self.unchanged()

    def edit_record(self, kind, value):
        sp = "data/bibliography_shards/B2.json"
        data = self.load(sp)
        w = data["works"][0]
        old_id = w["work_id"]
        if kind in ("item_id", "url"):
            w["source_edition"][kind] = value
        else:
            w[kind] = value
        ap = "sources/manifests/audit_B2.json"
        audit = self.load(ap)
        ar = next(r for r in audit["rows"] if r["work_id"] == old_id)
        ar["work_id"] = w["work_id"]
        ar["expected"] = {"title": w["title"], "author": w["author"], "first_publication_year": w["first_publication_year"], "source_item_id": w["source_edition"]["item_id"]}
        mp = "sources/manifests/bibliography_B2.json"
        metadata = self.load(mp)
        next(r for r in metadata["rows"] if r["work_id"] == old_id)["work_id"] = w["work_id"]
        self.put(sp, data)
        self.put(ap, audit)
        self.put(mp, metadata)
        self.reseal("B2")

    def test_happy_path_preserves_records_and_noop(self):
        result = merger.merge(self.root)
        self.assertEqual((result["accepted"], result["reserves"], result["unique"]), (100, 20, 120))
        original_works, original_reserves = [], []
        for n, _, _, _ in merger.INPUTS:
            source = self.load(f"data/bibliography_shards/{n}.json")
            original_works += source["works"]
            original_reserves += source["reserves"]
        for path, expected in zip(merger.OUTPUTS, (original_works, original_reserves)):
            self.assertEqual(self.load(path)["works"], sorted(expected, key=lambda w: w["work_id"]))
        before = {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mtime_ns) for p in merger.OUTPUTS}
        self.assertEqual(merger.merge(self.root)["changed"], [])
        self.assertEqual(before, {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mtime_ns) for p in merger.OUTPUTS})
        self.assertEqual(self.original, {p: (self.root / p).read_bytes() for p in self.relative})

    def test_duplicate_id(self):
        self.edit_record("work_id", self.load("data/bibliography_shards/B1.json")["works"][0]["work_id"])
        self.reject("duplicate work_id")

    def test_duplicate_normalized_title(self):
        self.edit_record("title", self.load("data/bibliography_shards/B1.json")["works"][0]["title"].upper() + "!!!")
        self.reject("duplicate normalized_title")

    def test_duplicate_item(self):
        self.edit_record("item_id", self.load("data/bibliography_shards/B1.json")["reserves"][0]["source_edition"]["item_id"])
        self.reject("duplicate item_id")

    def test_duplicate_url(self):
        self.edit_record("url", self.load("data/bibliography_shards/B3.json")["reserves"][0]["source_edition"]["url"])
        self.reject("duplicate source_url")

    def test_count_ablation(self):
        p = "data/bibliography_shards/B2.json"
        d = self.load(p); d["reserves"].pop(); self.put(p, d); self.reseal("B2")
        self.reject("count mismatch")

    def test_unready_audit(self):
        p = "sources/manifests/audit_B2.json"
        d = self.load(p); d["state"] = "NOT_READY"; self.put(p, d); self.reseal("B2")
        self.reject("audit not ready")

    def test_failed_row_under_green_summary(self):
        p = "sources/manifests/audit_B2.json"
        d = self.load(p); d["rows"][0]["checks"]["rights_match"] = False; self.put(p, d); self.reseal("B2")
        self.reject("failed audit row")

    def test_unready_receipt(self):
        p = "generated/receipts/B2A.json"
        d = self.load(p); d["status"] = "blocked"; self.put(p, d); self.commit()
        self.reject("receipt not ready")

    def test_stale_receipt_hash(self):
        p = "sources/manifests/audit_B2.json"
        d = self.load(p); d["extra"] = "changed"; self.put(p, d); self.commit()
        self.reject("stale/unbound audit")

    def test_schema_rejects_extra_record_field(self):
        self.edit_record("invented_field", True)
        self.reject("Additional properties")

    def test_dirty_provenance(self):
        p = "generated/receipts/B2A.json"
        d = self.load(p); d["result"] += " uncommitted"; self.put(p, d)
        self.reject("differs from committed")

    def test_source_order_does_not_change_dataset_bytes(self):
        merger.merge(self.root)
        expected = {p: (self.root / p).read_bytes() for p in merger.OUTPUTS[:2]}
        for name, _, _, _ in merger.INPUTS:
            p = f"data/bibliography_shards/{name}.json"
            d = self.load(p); d["works"].reverse(); d["reserves"].reverse(); self.put(p, d); self.reseal(name)
        merger.merge(self.root)
        self.assertEqual(expected, {p: (self.root / p).read_bytes() for p in merger.OUTPUTS[:2]})

    def test_global_author_cap_including_reserves(self):
        author = self.load("data/bibliography_shards/B1.json")["works"][0]["author"]
        p = "data/bibliography_shards/B2.json"; d = self.load(p)
        ap = "sources/manifests/audit_B2.json"; a = self.load(ap)
        for work in d["reserves"]:
            work["author"] = author
            next(r for r in a["rows"] if r["work_id"] == work["work_id"])["expected"]["author"] = author
        self.put(p, d); self.put(ap, a); self.reseal("B2"); self.reject("author cap")

    def test_stratum_ablation(self):
        p = "sources/manifests/bibliography_B2.json"; d = self.load(p)
        d["rows"][0]["stratum"] = "poetry"; self.put(p, d); self.reseal("B2"); self.reject("stratum quota")

    def test_women_floor_ablation(self):
        for name, _, _, _ in merger.INPUTS:
            p = f"sources/manifests/bibliography_{name}.json"; d = self.load(p)
            for row in d["rows"]:
                row["women_authored" if name != "B2" else "woman_authored"] = False
            self.put(p, d); self.reseal(name)
        self.reject("breadth floor")

    def test_non_novel_floor_ablation(self):
        for name, _, _, _ in merger.INPUTS:
            p = f"sources/manifests/bibliography_{name}.json"; d = self.load(p)
            for row in d["rows"]:
                if name == "B3":
                    row["form"] = "novel"
                else:
                    row["non_novel_or_hybrid"] = False
            self.put(p, d); self.reseal(name)
        self.reject("breadth floor")

    def test_verified_tradition_floor_ablation(self):
        p = "sources/manifests/bibliography_B3.json"; d = self.load(p)
        for row in d["rows"]:
            row["breadth_qualifies"] = False
        self.put(p, d); self.reseal("B3"); self.reject("breadth floor")

    def test_concurrent_output_edit_is_preserved(self):
        real = merger.write_json
        calls = []
        edited = b'{"user_edit": true}\n'
        def interrupted(path, value):
            calls.append(path)
            if len(calls) == 2:
                calls[0].write_bytes(edited)
                raise OSError("injected concurrent edit")
            return real(path, value)
        with patch.object(merger, "write_json", side_effect=interrupted):
            with self.assertRaisesRegex(merger.MergeError, "concurrent output change preserved"):
                merger.merge(self.root)
        self.assertEqual((self.root / merger.OUTPUTS[0]).read_bytes(), edited)
        for p in merger.OUTPUTS[1:]:
            self.assertEqual((self.root / p).read_bytes(), self.old_outputs[p])

    def test_source_race_before_publish(self):
        outputs, snapshots = merger.assemble(self.root)
        p = "data/bibliography_shards/B1.json"; (self.root / p).write_bytes(snapshots[p] + b" ")
        with self.assertRaisesRegex(merger.MergeError, "input changed"):
            merger.publish(self.root, outputs, snapshots)
        self.unchanged()

    def test_failure_rolls_back_and_rerun_recovers(self):
        real = merger.write_json
        calls = []
        def interrupted(path, value):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected second-output failure")
            return real(path, value)
        with patch.object(merger, "write_json", side_effect=interrupted):
            self.reject("second-output failure")
        self.assertEqual(merger.merge(self.root)["state"], "READY")

    def test_existing_lock_fails_closed(self):
        p = self.root / "generated/.bibliography-merge.lock"; p.mkdir()
        with self.assertRaisesRegex(merger.MergeError, "lock exists"):
            merger.merge(self.root)
        self.assertTrue(p.exists()); p.rmdir(); self.unchanged()

    def test_missing_schema_dependency_fails_closed(self):
        with patch.dict("sys.modules", {"jsonschema": None}):
            self.reject("jsonschema dependency unavailable")

if __name__ == "__main__":
    unittest.main()
