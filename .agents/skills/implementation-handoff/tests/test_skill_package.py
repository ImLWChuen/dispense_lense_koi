from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]


class SkillPackageTests(unittest.TestCase):
    def test_skill_metadata_is_discoverable(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter_match = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)

        self.assertIsNotNone(frontmatter_match)
        assert frontmatter_match
        frontmatter = frontmatter_match.group(1)
        self.assertIn("name: implementation-handoff", frontmatter)
        self.assertRegex(frontmatter, r"(?m)^description: \S.+$")
        self.assertLessEqual(
            len(re.search(r"(?m)^description: (.+)$", frontmatter).group(1)),
            1024,
        )

    def test_reusable_resources_exist(self) -> None:
        expected_paths = [
            SKILL_ROOT / "references" / "task-template.md",
            SKILL_ROOT / "references" / "project-config-template.md",
            SKILL_ROOT / "scripts" / "validate_task.py",
            SKILL_ROOT / "evals" / "evals.json",
        ]

        for path in expected_paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_dispenseiq_installation_has_required_handoff_files(self) -> None:
        expected_paths = [
            REPOSITORY_ROOT / ".agents" / "handoff" / "PROJECT.md",
            REPOSITORY_ROOT / ".agents" / "handoff" / "QUEUE.md",
            REPOSITORY_ROOT / ".agents" / "workflows" / "implement-next-task.md",
        ]

        for path in expected_paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_dispenseiq_policy_names_feature_branch_and_blocks_remote_actions(self) -> None:
        project_config = (
            REPOSITORY_ROOT / ".agents" / "handoff" / "PROJECT.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Feature branch: `cskee-branch`", project_config)
        self.assertIn("Push: `prohibited", project_config)
        self.assertIn("Merge: `prohibited", project_config)


if __name__ == "__main__":
    unittest.main()

