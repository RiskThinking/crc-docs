"""Package each skill as a zip for upload to Claude, ChatGPT or other hosts.

Run from the repository root:

    uv run python tools/package_skills.py            # writes dist/skills/<name>.zip

A skill that mentions ``scripts/<file>.py`` gets ``pipelines/<file>.py`` copied
into its ``scripts/`` folder inside the zip (the repository keeps one copy), so
the uploaded skill can run without downloading the script.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

SKILLS = Path(".agents/skills")
PIPELINES = Path("pipelines")
SCRIPT = re.compile(r"scripts/([a-z0-9_]+\.py)")


def bundled_scripts(skill: Path) -> dict[str, Path]:
    """Pipelines the skill refers to as scripts/<file> but does not ship itself."""
    text = (skill / "SKILL.md").read_text()
    return {
        name: PIPELINES / name
        for name in sorted(set(SCRIPT.findall(text)))
        if not (skill / "scripts" / name).exists() and (PIPELINES / name).exists()
    }


def package(skill: Path, output: Path) -> Path:
    target = output / f"{skill.name}.zip"
    temporary = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(skill.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, Path(skill.name) / path.relative_to(skill))
        for name, source in bundled_scripts(skill).items():
            archive.write(source, Path(skill.name) / "scripts" / name)
    temporary.replace(target)
    return target


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/skills"))
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    for skill in sorted(path.parent for path in SKILLS.glob("*/SKILL.md")):
        target = package(skill, args.output)
        extras = ", ".join(bundled_scripts(skill)) or "no bundled scripts"
        print(f"{target} ({extras})")


if __name__ == "__main__":
    main()
