#!/usr/bin/env python3
"""Prepare sources exclusively from this run's resolved snapshot."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

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


def copy_asset(spec, assets, destination):
    source = assets / spec["file"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec["sha256"]:
        raise RuntimeError(f"Resolved asset SHA256 mismatch: {spec['file']}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    checkout(lock["core"], work)
    # Prefer upstream plugins when resolving dependencies from any feed.
    ordered = lock["plugin_feeds"] + [name for name in lock["feeds"] if name not in lock["plugin_feeds"]]
    lines = [
        f"src-git {name} {lock['feeds'][name]['url']}^{lock['feeds'][name]['commit']}"
        for name in ordered
    ]
    (work / "feeds.conf.default").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    copy_asset(mihomo, args.assets, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != mihomo["sha256"]:
        raise RuntimeError("Mihomo SHA256 mismatch")
    core = work / "files/etc/openclash/core/clash_meta"
    core.parent.mkdir(parents=True, exist_ok=True)
    unpack_core(archive, core, mihomo.get("archive_format", "gzip"))
    core.chmod(0o755)
    header = core.read_bytes()[:20]
    if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
        raise RuntimeError("Mihomo must be a Linux x86_64 ELF binary")
    banner = subprocess.check_output([str(core), "-v"], text=True).strip()
    if mihomo["version"] not in banner:
        raise RuntimeError(f"Mihomo binary version differs from metadata: {banner}")
    lock["mihomo"]["version_output"] = banner
    lock["mihomo"]["binary_sha256"] = hashlib.sha256(core.read_bytes()).hexdigest()
    archive.unlink()
    for spec in lock["geodata"]:
        if spec["file"] not in {"Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"}:
            raise RuntimeError("Unsupported geodata destination")
        target = work / "files/etc/openclash" / spec["file"]
        copy_asset(spec, args.assets, target)
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
