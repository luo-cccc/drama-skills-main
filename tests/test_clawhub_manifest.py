import hashlib
import json
import re
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
MANIFEST = SUITE / ".clawhub/publish.json"
SKILL_DEPENDENCY = re.compile(
    r"^skill:([A-Za-z0-9][A-Za-z0-9-]{0,38})/([a-z0-9]+(?:-[a-z0-9]+)*)@(.+)$"
)


class ClawHubManifestDependencyTests(unittest.TestCase):
    def manifest_skills(self) -> list[dict[str, object]]:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest.get("skills"), list)
        return manifest["skills"]

    def package_digest(self, skill: dict[str, object]) -> str:
        base = SUITE / str(skill["path"])
        files: dict[str, bytes] = {}
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(base).as_posix()
            if (
                any(part.startswith(".") for part in relative.split("/"))
                or "__pycache__" in relative.split("/")
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            files[relative] = path.read_bytes()
        if not any(Path(name).name.lower().startswith("license") for name in files):
            files["LICENSE"] = (SUITE / "LICENSE").read_bytes()

        dependencies = [
            dependency
            for dependency in skill["runtimeDependsOn"]
            if str(dependency).startswith("skill:")
        ]
        if dependencies:
            install = (
                "# Exact companion skills\n\n"
                "ClawHub does not auto-install these dependencies. Install all into "
                "the same skills root:\n\n```sh\n"
                + "\n".join(
                    "clawhub install @"
                    + str(dependency)[6 : str(dependency).rfind("@")]
                    + " --version "
                    + str(dependency)[str(dependency).rfind("@") + 1 :]
                    for dependency in dependencies
                )
                + "\n```\n"
            )
            files["INSTALL.md"] = install.encode()

        inventory = [
            {
                "path": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
            for name, data in sorted(files.items())
        ]
        canonical = json.dumps(
            inventory, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def test_every_skill_directory_is_declared_once(self) -> None:
        declared = [str(skill["path"]) for skill in self.manifest_skills()]
        actual = {
            path.parent.relative_to(SUITE).as_posix()
            for path in (SUITE / "skills").rglob("SKILL.md")
        }

        self.assertEqual(len(declared), len(set(declared)))
        self.assertEqual(set(declared), actual)

    def test_skill_dependencies_pin_a_declared_version(self) -> None:
        skills = self.manifest_skills()
        identities = {
            (str(skill["publisher"]).casefold(), str(skill["slug"])): skill
            for skill in skills
        }

        for skill in skills:
            for dependency in skill["runtimeDependsOn"]:
                if not str(dependency).startswith("skill:"):
                    continue
                match = SKILL_DEPENDENCY.fullmatch(str(dependency))
                self.assertIsNotNone(match, dependency)
                assert match is not None
                owner, slug, version = match.groups()
                identity = (owner.casefold(), slug)
                with self.subTest(skill=skill["slug"], dependency=dependency):
                    self.assertIn(identity, identities)
                    self.assertEqual(identities[identity]["version"], version)

    def test_every_package_digest_matches_its_source(self) -> None:
        for skill in self.manifest_skills():
            if skill["disposition"] != "publish":
                continue
            with self.subTest(skill=skill["slug"]):
                self.assertEqual(
                    skill["packageDigest"], self.package_digest(skill)
                )


if __name__ == "__main__":
    unittest.main()
