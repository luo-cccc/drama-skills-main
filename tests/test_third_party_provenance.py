"""Third-party source inventory and license files remain complete."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ThirdPartyProvenanceTests(unittest.TestCase):
    def test_target_mapping_resolves_and_each_independent_skill_carries_its_notices(self) -> None:
        inventory = json.loads((ROOT / "docs/third-party/shuohao-skills-2.2.1.json").read_text(encoding="utf-8"))
        upstream_paths = {entry["path"] for entry in inventory["files"]}
        mapping = json.loads((ROOT / "docs/third-party/shuohao-adaptations.json").read_text(encoding="utf-8"))
        self.assertTrue(mapping["adaptations"])
        for entry in mapping["adaptations"]:
            skill = ROOT / "skills" / entry["skill"]
            with self.subTest(skill=entry["skill"]):
                self.assertTrue((skill / "THIRD_PARTY_NOTICES.md").is_file())
                self.assertTrue(set(entry["upstream"]) <= upstream_paths)
                for target in entry["targets"]:
                    self.assertTrue((skill / target).is_file())
                    self.assertIn(skill.resolve(), (skill / target).resolve().parents)
                for name in ("Apache-2.0.txt", "shuohao-skills-NOTICE.txt"):
                    self.assertEqual((skill / "licenses" / name).read_bytes(), (ROOT / "licenses" / name).read_bytes())
        for entry in mapping["repository_tools"]:
            self.assertTrue((ROOT / entry["target"]).is_file())
            self.assertTrue(set(entry["upstream"]) <= upstream_paths)

    def test_source_inventory_hashes_every_captured_file(self) -> None:
        manifest = json.loads(
            (
                ROOT / "docs/third-party/shuohao-skills-2.2.1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["declared_version"], "2.2.1")
        self.assertEqual(manifest["license"], "Apache-2.0")
        files = manifest["files"]
        self.assertGreater(len(files), 100)
        paths = {entry["path"] for entry in files}
        self.assertIn("NOTICE", paths)
        self.assertIn("LICENSE", paths)
        self.assertIn("skills/novel-staging/scripts/novel-staging.mjs", paths)
        for entry in files:
            with self.subTest(path=entry["path"]):
                self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreaterEqual(entry["bytes"], 0)
        self.assertEqual(len(paths), len(files))

    def test_apache_license_and_upstream_notice_are_shipped(self) -> None:
        license_text = (ROOT / "licenses/Apache-2.0.txt").read_text(
            encoding="utf-8"
        )
        notice = (ROOT / "licenses/shuohao-skills-NOTICE.txt").read_text(
            encoding="utf-8"
        )
        self.assertRegex(license_text, r"Apache License\s+Version 2\.0")
        self.assertIn("Copyright 2026", notice)
        self.assertIn(
            "https://github.com/eternityspring/shuohao-skills",
            (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
