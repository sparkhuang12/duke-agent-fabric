from __future__ import annotations

from pathlib import Path

import pytest

from duke_harness.config import PROJECT_ROOT
from duke_harness.skills.loader import SkillIntegrityError, SkillRegistry


def test_vendored_skills_are_checksum_verified() -> None:
    registry = SkillRegistry(PROJECT_ROOT / "skills" / "manifest.json")
    assert {item.name for item in registry.list()} == {
        "meeting-minutes",
        "documentation-writer",
        "ai-prompt-engineering-safety-review",
    }
    assert '<skill name="meeting-minutes">' in registry.prompt_for(["meeting-minutes"])


def test_modified_skill_is_rejected(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: bad\ndescription: bad\n---\nchanged", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"schema_version":1,"skills":[{"name":"bad","path":"SKILL.md","source_url":"x",'
        '"source_commit":"x","sha256":"wrong","license":"MIT"}]}',
        encoding="utf-8",
    )
    with pytest.raises(SkillIntegrityError, match="checksum mismatch"):
        SkillRegistry(manifest)
