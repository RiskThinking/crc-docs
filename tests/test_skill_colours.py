"""Chart colours in the skills must come from assets/impact_risk_colours.json."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE = set(
    json.loads((ROOT / "assets/impact_risk_colours.json").read_text()).values()
)
SKILLS = ("how-exposed-is-this-company", "which-sites-are-most-at-risk")


def test_skill_chart_colours_are_in_the_palette() -> None:
    for skill in SKILLS:
        text = (ROOT / ".agents/skills" / skill / "SKILL.md").read_text()
        used = set(re.findall(r"#[0-9a-f]{6}\b", text))
        assert used, skill
        assert used <= PALETTE, (skill, used - PALETTE)
