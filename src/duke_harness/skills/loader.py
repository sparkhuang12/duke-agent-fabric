from __future__ import annotations

import builtins
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


class SkillIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    content: str
    source_url: str
    source_commit: str
    sha256: str
    license: str


class SkillRegistry:
    """Loads text-only skills declared in a pinned manifest.

    The loader deliberately ignores scripts and assets. A skill can contribute
    instructions to a prompt, but it cannot gain execution privileges.
    """

    def __init__(self, manifest_path: Path, *, max_skill_bytes: int = 128_000):
        self._manifest_path = manifest_path
        self._max_skill_bytes = max_skill_bytes
        self._skills = self._load()

    def _load(self) -> dict[str, Skill]:
        if not self._manifest_path.exists():
            return {}
        payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise SkillIntegrityError("unsupported skills manifest schema")
        result: dict[str, Skill] = {}
        root = self._manifest_path.parent.resolve()
        for entry in payload.get("skills", []):
            name = str(entry["name"])
            target = (root / str(entry["path"])).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise SkillIntegrityError(f"skill path escapes registry root: {name}") from exc
            if target.is_symlink() or not target.is_file():
                raise SkillIntegrityError(f"skill must be a regular file: {name}")
            raw = target.read_bytes()
            if len(raw) > self._max_skill_bytes:
                raise SkillIntegrityError(f"skill is too large: {name}")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != entry.get("sha256"):
                raise SkillIntegrityError(f"checksum mismatch for skill: {name}")
            text = raw.decode("utf-8")
            match = FRONTMATTER.match(text)
            if not match:
                raise SkillIntegrityError(f"skill is missing frontmatter: {name}")
            header = self._parse_header(match.group("header"))
            if header.get("name") != name:
                raise SkillIntegrityError(f"manifest/frontmatter name mismatch: {name}")
            result[name] = Skill(
                name=name,
                description=header.get("description", ""),
                content=match.group("body").strip(),
                source_url=str(entry["source_url"]),
                source_commit=str(entry["source_commit"]),
                sha256=digest,
                license=str(entry["license"]),
            )
        return result

    @staticmethod
    def _parse_header(header: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in header.splitlines():
            if ":" not in line or line.startswith((" ", "\t")):
                continue
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("'\"")
        return values

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def require(self, name: str) -> Skill:
        skill = self.get(name)
        if skill is None:
            raise SkillIntegrityError(f"unknown skill: {name}")
        return skill

    def list(self) -> builtins.list[Skill]:
        return list(self._skills.values())

    def prompt_for(self, names: builtins.list[str]) -> str:
        if not names:
            return ""
        sections = []
        for name in names:
            skill = self.require(name)
            sections.append(f'<skill name="{skill.name}">\n{skill.content}\n</skill>')
        return "\n\n".join(sections)
