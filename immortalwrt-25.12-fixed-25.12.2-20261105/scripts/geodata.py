#!/usr/bin/env python3
"""Refresh OpenClash data once, validating the complete set with the fixed core."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request


def now():
    return datetime.now(timezone.utc).isoformat()


def fetch(url):
    headers = {"User-Agent": "Actions-ImmortalWrt-fixed-geodata"}
    if url.startswith("https://api.github.com/") and os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def api(path):
    return json.loads(fetch("https://api.github.com/repos/" + path))


def online(sources, destination):
    releases = {}
    records = []
    for spec in sources:
        record = {"file": spec["file"], "configured_url": spec["url"], "mode": "online"}
        expected = None
        if "ref" in spec:
            commit = api(spec["repo"] + "/commits/" + spec["ref"])
            record.update(source_commit=commit["sha"], source_updated_at=commit["commit"]["committer"]["date"],
                          url=f"https://raw.githubusercontent.com/{spec['repo']}/{commit['sha']}/{spec['path']}")
        else:
            key = (spec["repo"], spec["release"])
            if key not in releases:
                releases[key] = api(spec["repo"] + "/releases/" + spec["release"])
            release = releases[key]
            matches = [a for a in release["assets"] if a["name"] == spec["asset"]]
            if len(matches) != 1:
                raise RuntimeError("Missing release asset: " + spec["file"])
            asset = matches[0]
            record.update(release=release["tag_name"], release_id=release["id"], asset_id=asset["id"],
                          source_updated_at=asset["updated_at"], url=asset["browser_download_url"])
            expected = asset.get("digest") or ""
            if expected and not expected.startswith("sha256:"):
                raise RuntimeError("Unsupported upstream digest")
        data = fetch(record["url"])
        if len(data) < 1024 or data.lstrip().startswith((b"<", b"{")):
            raise RuntimeError("Invalid database response: " + spec["file"])
        digest = hashlib.sha256(data).hexdigest()
        if expected and expected != "sha256:" + digest:
            raise RuntimeError("Upstream checksum mismatch: " + spec["file"])
        if "ref" not in spec and len(data) != asset["size"]:
            raise RuntimeError("Release asset changed during download")
        (destination / spec["file"]).write_bytes(data)
        record.update(sha256=digest, size=len(data), fetched_at=now(), checksum_source="upstream" if expected else "computed")
        records.append(record)
    return records


def validate_core(core, directory):
    # -t parses rules/databases and exits without starting proxy listeners.
    for mode, rules in [(False, ["GEOIP,CN,DIRECT", "IP-ASN,13335,DIRECT"]),
                        (True, ["GEOIP,CN,DIRECT", "GEOSITE,CN,DIRECT"])]:
        with tempfile.TemporaryDirectory(prefix="meta-data-probe-") as scratch:
            probe = Path(scratch)
            for name in ("Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"):
                shutil.copyfile(directory / name, probe / name)
            config = {"mode": "rule", "geodata-mode": mode, "rules": rules + ["MATCH,DIRECT"]}
            path = probe / "probe.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            result = subprocess.run([str(core), "-t", "-d", str(probe), "-f", str(path)],
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError("Fixed Meta database load failed: " + (result.stdout + result.stderr)[-1200:])


def prepare(recipe, target, core, validator=validate_core):
    policy = json.loads((recipe / "geodata.policy.json").read_text(encoding="utf-8"))
    names = {s["file"] for s in policy["sources"]}
    if names != {"Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"}:
        raise RuntimeError("Unexpected geodata policy")
    with tempfile.TemporaryDirectory(prefix="fixed-geodata-") as temporary:
        directory = Path(temporary)
        reason = None
        try:
            records = online(policy["sources"], directory)
            validator(core, directory)
        except Exception as exc:
            reason = str(exc)[:1600]
            print("Online database set rejected; validating fallback: " + reason, flush=True)
            fallback = recipe / policy["fallback"]
            baseline = json.loads((fallback / "manifest.json").read_text(encoding="utf-8"))
            records = baseline["assets"]
            if {r["file"] for r in records} != names:
                raise RuntimeError("Incomplete fallback set")
            records = [dict(r, mode="fallback", fallback_reason=reason, fetched_at=now(),
                            source_updated_at=r.get("asset_updated_at", "")) for r in records]
            for record in records:
                source = fallback / record["file"]
                if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
                    raise RuntimeError("Fallback checksum mismatch: " + record["file"])
                shutil.copyfile(source, directory / record["file"])
            validator(core, directory)
        target.mkdir(parents=True, exist_ok=True)
        for record in records:
            shutil.copyfile(directory / record["file"], target / record["file"])
            record["validated_by_fixed_meta"] = True
            print(f"{record['file']}: {record['mode']}, {record['sha256']}", flush=True)
        if reason and os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write("\n本次 OpenClash 数据库使用托底快照；原因详见 build-lock.json 与日志。\n")
        return records
