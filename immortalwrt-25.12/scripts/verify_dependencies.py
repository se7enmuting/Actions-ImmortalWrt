#!/usr/bin/env python3
"""Reject missing dependencies of selected recipes before downloading/building."""
from pathlib import Path
import re
import sys
from verify_config import read_config


def verify(work):
    selected = {key.removeprefix("CONFIG_PACKAGE_") for key, value in read_config(work / ".config").items()
                if key.startswith("CONFIG_PACKAGE_") and value in {"y", "m"}}
    sources = set()
    for block in (work / "tmp/.packageinfo").read_text(encoding="utf-8").split("Source-Makefile: ")[1:]:
        if selected.intersection(re.findall(r"^Package: (\S+)", block, re.M)):
            sources.add(block.splitlines()[0])
    failures = []
    for source, dependency in re.findall(
        r"WARNING: Makefile '([^']+)' has a (?:build )?dependency on '([^']+)', which does not exist",
        (work / "defconfig.log").read_text(encoding="utf-8")
    ):
        if source in sources:
            failures.append(f"{source}: missing {dependency}")
    if failures:
        raise RuntimeError("Selected package dependencies are unavailable:\n" + "\n".join(sorted(set(failures))))
    print(f"Checked missing-dependency warnings against {len(sources)} selected recipes")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve())
