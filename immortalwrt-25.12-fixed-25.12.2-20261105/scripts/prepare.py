#!/usr/bin/env python3
"""Fetch the reviewed sources without running the legacy 18.06 DIY scripts."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

RECIPE = Path(__file__).resolve().parents[1]


def unpack_core(archive, destination, archive_format):
    if archive_format == "tar.gz":
        with tarfile.open(archive, "r:gz") as bundle:
            entries = bundle.getmembers()
            if len(entries) != 1 or entries[0].name not in {"clash", "./clash"} or not entries[0].isfile():
                raise RuntimeError("Unexpected OpenClash core archive layout")
            with bundle.extractfile(entries[0]) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
    elif archive_format == "gzip":
        with gzip.open(archive, "rb") as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)
    else:
        raise RuntimeError("Unsupported core archive format")


def checkout(spec, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise RuntimeError(f"Refusing to overwrite a nonempty source directory: {destination}")
    subprocess.run(["git", "init", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "remote", "add", "origin", spec["url"]], check=True)
    subprocess.run(["git", "-C", str(destination), "fetch", "--depth=1", "origin", spec["commit"]], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"], check=True)
    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
    if actual != spec["commit"]:
        raise RuntimeError(f"Source revision mismatch: {destination}")


def main():
    work = Path(sys.argv[1]).resolve()
    lock = json.loads((RECIPE / "sources.lock.json").read_text(encoding="utf-8"))
    checkout(lock["core"], work)
    lines = [
        f"src-git {name} {spec['url']}^{spec['commit']}"
        for name, spec in lock["feeds"].items()
    ]
    (work / "feeds.conf.default").write_text("\n".join(lines) + "\n", encoding="utf-8")
    checkout(lock["bandix_backend"], work / "package/custom/bandix-backend")
    checkout(lock["bandix_luci"], work / "package/custom/bandix-luci")
    shutil.copytree(RECIPE / "files", work / "files", dirs_exist_ok=True)
    for f in (work / "files/etc/uci-defaults").iterdir():
        f.chmod(0o755)

    # Retain the upstream verified binary recipe for Bandix. Its Makefile pins
    # the architecture-specific binary hash; it is NOT compiled from Rust here.
    mihomo = lock["mihomo"]
    profile = (work / "files/etc/uci-defaults/99-pve-profile").read_text()
    if f"set openclash.config.core_version='{mihomo['architecture']}'" not in profile:
        raise RuntimeError("Mihomo archive architecture and first-boot selection differ")
    archive = work / "mihomo.archive"
    with urllib.request.urlopen(mihomo["url"], timeout=120) as response, archive.open("wb") as out:
        shutil.copyfileobj(response, out)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != mihomo["sha256"]:
        raise RuntimeError("Mihomo SHA256 mismatch")
    core = work / "files/etc/openclash/core/clash_meta"
    core.parent.mkdir(parents=True, exist_ok=True)
    unpack_core(archive, core, mihomo.get("archive_format", "gzip"))
    core.chmod(0o755)
    archive.unlink()
    for spec in lock["geodata"]:
        if spec["file"] not in {"Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"}:
            raise RuntimeError("Unsupported geodata destination")
        target = work / "files/etc/openclash" / spec["file"]
        with urllib.request.urlopen(spec["url"], timeout=120) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != spec["sha256"]:
            raise RuntimeError(f"Geodata SHA256 mismatch: {spec['file']}")
        target.chmod(0o644)
    # amd64-v2 requires the matching guest CPU features; AVX is not required.
    (work / "build-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared ImmortalWrt {lock['release']} at {lock['core']['commit']}")


if __name__ == "__main__":
    main()
