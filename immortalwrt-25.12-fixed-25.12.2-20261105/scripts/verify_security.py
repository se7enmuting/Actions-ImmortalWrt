#!/usr/bin/env python3
"""Verify fixed security inputs before compilation and versions before publishing."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from verify_config import read_config


def verify(work):
    lock = json.loads((work / "build-lock.json").read_text(encoding="utf-8"))
    expected = lock["security_revision"]
    for name, digest in expected["expected_files"].items():
        path = work / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Security source mismatch: {name}")
    for name, spec in lock["feeds"].items():
        actual = subprocess.check_output(["git", "-C", str(work / "feeds" / name), "rev-parse", "HEAD"], text=True).strip()
        if actual != spec["commit"]:
            raise RuntimeError(f"Fixed feed changed: {name}")
    config = read_config(work / ".config")
    for name in ("uhttpd", "uhttpd-mod-ubus", "libopenssl", "openssl-util", "ca-bundle", "libc"):
        if config.get("CONFIG_PACKAGE_" + name) != "y":
            raise RuntimeError(f"Security package was not selected: {name}")
    print(f"Verified {expected['id']}: {len(expected['expected_files'])} source hashes, fixed feeds and selected security packages")


def verify_manifest(path):
    versions = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "-":
            versions[fields[0]] = fields[2]
    for name, prefix in {"uhttpd": "2026.08.24~373145f7", "openssl-util": "3.5.9", "ca-bundle": "20260816-r2"}.items():
        if not versions.get(name, "").startswith(prefix):
            raise RuntimeError(f"Security package version mismatch: {name}: {versions.get(name)}")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve())
