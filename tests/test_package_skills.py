import zipfile
from pathlib import Path

from tools.package_skills import main


def test_question_skills_bundle_their_pipeline(tmp_path: Path) -> None:
    main(["--output", str(tmp_path)])
    for skill, script in [
        ("how-hot-will-it-get", "how_hot_will_it_get.py"),
        ("how-hard-will-it-rain", "how_hard_will_it_rain.py"),
        ("which-sites-are-most-at-risk", "which_sites_are_most_at_risk.py"),
        ("will-my-farm-get-drier", "will_my_farm_get_drier.py"),
    ]:
        names = zipfile.ZipFile(tmp_path / f"{skill}.zip").namelist()
        assert f"{skill}/SKILL.md" in names
        assert f"{skill}/scripts/{script}" in names
