#!/usr/bin/env python3
"""Check checked-out commits and selected plugin origins after feed installation."""
import json
from pathlib import Path
import re
import subprocess
import sys

EXPECTED = {
    "openclash": ["luci-app-openclash"],
    "passwall": ["luci-app-passwall"],
    "passwall_packages": ["xray-core", "sing-box", "geoview"],
    "bandix_backend": ["bandix"],
    "bandix_luci": ["luci-app-bandix"],
    "luci-theme-argon": ["luci-theme-argon"],
    "luci-app-argon-config": ["luci-app-argon-config"],
    "oaf": ["luci-app-oaf", "appfilter", "kmod-oaf"],
}


def revision(directory):
    return subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True,
    ).strip()


def verify(work):
    lock_path = work / "build-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if revision(work) != lock["core"]["commit"]:
        raise RuntimeError("Core source no longer matches this run's lock")
    for feed, spec in lock["feeds"].items():
        if revision(work / "feeds" / feed) != spec["commit"]:
            raise RuntimeError(f"Feed source no longer matches this run's lock: {feed}")
    recipes = {}
    for feed, packages in EXPECTED.items():
        for package in packages:
            # Kernel package oaf is installed under its source recipe name.
            link_name = "oaf" if package == "kmod-oaf" else ("open-app-filter" if package == "appfilter" else "openwrt-bandix" if package == "bandix" else package)
            link = work / "package/feeds" / feed / link_name
            source = link.resolve()
            if not link.is_symlink() or not source.is_relative_to((work / "feeds" / feed).resolve()):
                raise RuntimeError(f"Wrong upstream package origin: {package} ({link})")
            makefile = source / "Makefile"
            variables = dict(re.findall(
                r"^((?:PKG|LUCI)_(?:NAME|VERSION|RELEASE))\s*:?=\s*(.+)$",
                makefile.read_text(encoding="utf-8"), re.MULTILINE,
            ))
            recipes[package] = {
                "feed": feed, "commit": lock["feeds"][feed]["commit"],
                "makefile": str(makefile.relative_to(work)),
                "variables": variables,
            }
    lock["package_recipes"] = recipes
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Verified core, {len(lock['feeds'])} feed commits and {len(recipes)} upstream package origins")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve())
