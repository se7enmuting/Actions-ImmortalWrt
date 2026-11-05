#!/usr/bin/env python3
"""Install requested LuCI packages, then load the seed AFTER feeds refreshes."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

from verify_config import read_config

recipe = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve()
settings = read_config(recipe / "config.seed")
packages = [
    key.removeprefix("CONFIG_PACKAGE_")
    for key, value in settings.items()
    if key.startswith("CONFIG_PACKAGE_") and value == "y" and "_INCLUDE_" not in key and not key.endswith("_Transparent_Proxy")
]
# Install upstream plugins first. feeds install -f alone does not replace
# already installed packages from another feed. Then link only requested
# maintenance packages and their dependencies; unrelated recipes can have
# Kconfig cycles even when they are not selected for this firmware.
lock = json.loads((work / "build-lock.json").read_text(encoding="utf-8"))
for feed in lock["plugin_feeds"]:
    subprocess.run(["./scripts/feeds", "install", "-a", "-f", "-p", feed], cwd=work, check=True)
subprocess.run(["./scripts/feeds", "install", *packages], cwd=work, check=True)
# New OAF creates these lazily at first start. Ship its own templates so the
# first-boot profile can set filtering, recording and MAC defaults before start.
config_dir = work / "files/etc/config"
config_dir.mkdir(parents=True, exist_ok=True)
for name in ("fwx", "macfilter"):
    shutil.copyfile(work / f"feeds/oaf/open-app-filter/files/{name}.config", config_dir / name)
shutil.copyfile(recipe / "config.seed", work / ".config")
print("Loaded requested configuration after feed installation")
