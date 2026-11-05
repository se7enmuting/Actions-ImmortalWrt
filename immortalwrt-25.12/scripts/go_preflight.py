#!/usr/bin/env python3
"""Select an available official Go compiler and check downloaded module requirements."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile


def version(value):
    parts = [int(x) for x in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


def choose(work):
    root = work / "feeds/packages/lang/golang"
    available = []
    for recipe in root.glob("golang1.*/Makefile"):
        text = recipe.read_text(encoding="utf-8")
        major = re.search(r"^GO_VERSION_MAJOR_MINOR:=(\d+\.\d+)$", text, re.M)
        patch = re.search(r"^GO_VERSION_PATCH:=(\d+)$", text, re.M)
        rc = re.search(r"^GO_VERSION_RC:=(.*)$", text, re.M)
        if major and patch and (not rc or not rc[1].strip()):
            available.append((version(major[1] + "." + patch[1]), major[1], recipe))
    if not available:
        raise RuntimeError("No stable official Go compiler recipe available")
    full, series, recipe = max(available)
    defaults = root / "golang-values.mk"
    original = defaults.read_bytes()
    replacement, count = re.subn(rb"(?m)^GO_DEFAULT_VERSION:=\d+\.\d+(?=\r?$)",
                                 f"GO_DEFAULT_VERSION:={series}".encode(), original)
    if count != 1:
        raise RuntimeError("Cannot identify the official Go default selector")
    defaults.write_bytes(replacement)
    # scan.mk does not track golang-values.mk as a dependency. Invalidate the
    # generated Go metadata so feeds install links the newly selected host tool.
    for cached in (work / "feeds/packages.tmp/info").glob(".packageinfo-lang_golang_*"):
        if cached.is_file():
            cached.unlink()
    lock_path = work / "build-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["go_toolchain"] = {
        "series": series, "version": ".".join(map(str, full)),
        "recipe": recipe.relative_to(work).as_posix(),
        "default_selector": defaults.relative_to(work).as_posix(),
        "default_original_sha256": hashlib.sha256(original).hexdigest(),
        "default_selected_sha256": hashlib.sha256(replacement).hexdigest(),
        "recipe_sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
        "feed_commit": lock["feeds"]["packages"]["commit"],
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return series


def check_index(work):
    lock_path = work / "build-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    series = lock["go_toolchain"]["series"]
    text = (work / "feeds/packages.index").read_text(encoding="utf-8")
    blocks = [block for block in text.split("Source-Makefile: ")[1:]
              if block.splitlines()[0] == "feeds/packages/lang/golang/golang/Makefile"]
    if len(blocks) != 1 or not re.search(
        r"^Build-Depends/host:.*(?<!\S)golang" + re.escape(series) + r"/host(?!\S)", blocks[0], re.M
    ):
        raise RuntimeError(f"Go feed index does not select golang{series}/host")
    lock["go_toolchain"]["index_verified"] = True
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Verified default golang/host dependency: golang{series}/host")


def check(work):
    lock_path = work / "build-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    compiler = lock["go_toolchain"]["version"]
    selector = work / lock["go_toolchain"]["default_selector"]
    if hashlib.sha256(selector.read_bytes()).hexdigest() != lock["go_toolchain"]["default_selected_sha256"]:
        raise RuntimeError("Go default selector changed after selection")
    recipe = work / lock["go_toolchain"]["recipe"]
    if hashlib.sha256(recipe.read_bytes()).hexdigest() != lock["go_toolchain"]["recipe_sha256"]:
        raise RuntimeError("Go compiler recipe changed after selection")
    checked = {}
    config = (work / ".config").read_text()
    for package in ("xray-core", "sing-box", "geoview"):
        if f"CONFIG_PACKAGE_{package}=y\n" not in config:
            continue
        text = (work / "feeds/passwall_packages" / package / "Makefile").read_text(encoding="utf-8")
        def literal(key):
            match = re.search(r"^" + key + r":=([\w.+-]+)$", text, re.M)
            if not match:
                raise RuntimeError(f"Cannot determine {package} {key}")
            return match[1]
        archive = work / "dl" / f"{literal('PKG_NAME')}-{literal('PKG_VERSION')}.tar.gz"
        with tarfile.open(archive) as bundle:
            matches = [m for m in bundle.getmembers()
                       if m.isfile() and len(Path(m.name).parts) == 2 and Path(m.name).name == "go.mod"]
            if len(matches) != 1:
                raise RuntimeError(f"Missing unambiguous root go.mod in {archive.name}")
            module = bundle.extractfile(matches[0]).read().decode()
        requirement = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)\s*$", module, re.M)
        if not requirement:
            raise RuntimeError(f"Missing Go requirement: {package}")
        required = requirement[1]
        if version(compiler) < version(required):
            raise RuntimeError(f"{package} requires Go {required}, selected official compiler is {compiler}")
        checked[package] = {"requires_go": required, "archive": archive.name}
        print(f"{package}: requires Go {required}; selected {compiler}: compatible")
    if not checked:
        raise RuntimeError("No selected proxy Go sources checked")
    lock["go_toolchain"]["checked_modules"] = checked
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["choose", "index", "check"])
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    if args.operation == "choose":
        print(choose(args.work.resolve()))
    elif args.operation == "index":
        check_index(args.work.resolve())
    else:
        check(args.work.resolve())
