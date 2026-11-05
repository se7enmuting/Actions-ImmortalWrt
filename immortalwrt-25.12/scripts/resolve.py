#!/usr/bin/env python3
"""Resolve moving upstream refs once, then build exclusively from that snapshot."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

RECIPE = Path(__file__).resolve().parents[1]


def request(url):
    headers = {"User-Agent": "Actions-ImmortalWrt-latest"}
    # Do not send the runner token to raw content, release CDNs or redirects.
    if urllib.parse.urlparse(url).netloc == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        token = os.getenv("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request(url), timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def api(path):
    return json.loads(fetch(f"https://api.github.com/repos/{path}"))


def repository(url):
    match = re.fullmatch(r"https://github.com/([\w.-]+/[\w.-]+?)(?:\.git)?", url)
    if not match:
        raise ValueError(f"Unsupported repository URL: {url}")
    return match[1]


def resolve_branch(spec):
    ref = spec["ref"]
    output = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", spec["url"], f"refs/heads/{ref}"],
        text=True, timeout=120,
    ).strip().splitlines()
    if len(output) != 1 or not re.fullmatch(r"[0-9a-f]{40}\s+refs/heads/" + re.escape(ref), output[0]):
        raise RuntimeError(f"Cannot resolve branch: {spec['url']} {ref}")
    commit = output[0].split()[0]
    print(f"Resolved {spec['url']} {ref}: {commit}", flush=True)
    return {**spec, "commit": commit}


def raw(spec, path):
    return f"https://raw.githubusercontent.com/{repository(spec['url'])}/{spec['commit']}/{path}"


def resolve_feeds(core):
    content = fetch(raw(core, "feeds.conf.default")).decode()
    feeds = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"src-git(?:-full)?\s+([\w-]+)\s+(https://github.com/[\w./-]+);([\w./-]+)", line)
        if not match or match[3] != "openwrt-25.12":
            raise RuntimeError(f"Unexpected 25.12 maintenance feed: {line}")
        name, url, ref = match.groups()
        if name in feeds:
            raise RuntimeError(f"Duplicate feed: {name}")
        feeds[name] = resolve_branch({"url": url, "ref": ref})
    if not {"packages", "luci", "routing", "telephony", "video"} <= feeds.keys():
        raise RuntimeError("Missing official maintenance feeds")
    return feeds


def checksum_for(text, filename):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*").removeprefix("./") == filename:
            if re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
                return fields[0].lower()
    raise RuntimeError(f"Missing upstream SHA256 for {filename}")


def save_asset(spec, assets, expected=None):
    print(f"Downloading {spec['file']}", flush=True)
    data = fetch(spec["url"])
    if not data:
        raise RuntimeError(f"Empty download: {spec['file']}")
    digest = hashlib.sha256(data).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f"Upstream SHA256 mismatch: {spec['file']}")
    (assets / spec["file"]).write_bytes(data)
    return {**spec, "sha256": digest, "size": len(data),
            "checksum_source": "upstream" if expected else "computed"}


def resolve_mihomo(policy, assets):
    source = resolve_branch({"url": f"https://github.com/{policy['repo']}.git", "ref": policy["ref"]})
    version = fetch(raw(source, policy["version_path"])).decode().splitlines()[0].strip()
    if not version.startswith("alpha-"):
        raise RuntimeError(f"Expected Meta Alpha, got {version}")
    filename = Path(policy["path"]).name
    checksums = fetch(raw(source, policy["checksums_path"])).decode()
    return save_asset({
        "file": filename, "url": raw(source, policy["path"]), "version": version,
        "channel": policy["channel"], "architecture": policy["architecture"],
        "source_commit": source["commit"], "ref": policy["ref"],
        "archive_format": "tar.gz",
    }, assets, checksum_for(checksums, filename))


def resolve_geodata(policies, assets):
    releases = {}
    result = []
    for policy in policies:
        repo = policy["repo"]
        if "path" in policy:
            source = resolve_branch({"url": f"https://github.com/{repo}.git", "ref": policy["ref"]})
            spec = {"file": policy["file"], "url": raw(source, policy["path"]),
                    "source_commit": source["commit"], "ref": source["ref"]}
            result.append(save_asset(spec, assets))
            continue
        key = (repo, policy["release"])
        if key not in releases:
            suffix = ("tags/" + urllib.parse.quote(policy["release"][4:], safe="")
                      if policy["release"].startswith("tag:") else "latest")
            releases[key] = api(f"{repo}/releases/{suffix}")
        release = releases[key]
        matches = [item for item in release["assets"] if item["name"] == policy["asset"]]
        if len(matches) != 1:
            raise RuntimeError(f"Missing or ambiguous release asset: {repo}/{policy['asset']}")
        asset = matches[0]
        digest = asset.get("digest") or ""
        if digest and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise RuntimeError(f"Unsupported upstream digest: {digest}")
        spec = {"file": policy["file"], "url": asset["browser_download_url"],
                "release": release["tag_name"], "release_id": release["id"],
                "asset_id": asset["id"], "asset_updated_at": asset["updated_at"]}
        resolved = save_asset(spec, assets, digest.removeprefix("sha256:") or None)
        if resolved["size"] != asset["size"]:
            raise RuntimeError(f"Release asset changed while resolving: {policy['file']}")
        result.append(resolved)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=RECIPE / "sources.json")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    if args.lock.exists() or (args.assets.exists() and any(args.assets.iterdir())):
        raise RuntimeError("Use a fresh lock path and asset directory for each run")
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    args.assets.mkdir(parents=True, exist_ok=True)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if policy["core"]["ref"] != "openwrt-25.12":
        raise RuntimeError("This recipe follows openwrt-25.12, not system master")
    core = resolve_branch(policy["core"])
    feeds = resolve_feeds(core)
    for name, spec in policy["plugins"].items():
        if name in feeds:
            raise RuntimeError(f"Plugin shadows official feed name: {name}")
        feeds[name] = resolve_branch(spec)
    lock = {
        "schema_version": 1, "mode": "latest",
        "release": "25.12-SNAPSHOT",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "recipe_commit": os.getenv("GITHUB_SHA", "local"),
        "policy_sha256": hashlib.sha256(args.policy.read_bytes()).hexdigest(),
        "core": core, "feeds": feeds,
        "plugin_feeds": list(policy["plugins"]),
        "mihomo": resolve_mihomo(policy["mihomo"], args.assets),
        "geodata": resolve_geodata(policy["geodata"], args.assets),
    }
    # This is an output record. Never write it back over the source policy.
    args.lock.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Resolved {core['ref']} at {core['commit']}, {len(feeds)} feeds")
    print(f"Meta {lock['mihomo']['version']} ({lock['mihomo']['architecture']}); four fresh databases")


if __name__ == "__main__":
    main()
