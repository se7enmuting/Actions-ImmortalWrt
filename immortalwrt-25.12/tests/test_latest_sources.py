"""Checks for latest resolution, snapshot reuse and fail-closed integrity."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import resolve
import prepare


class LatestInputs(unittest.TestCase):
    def test_branch_is_resolved_to_exact_commit(self):
        sha = "a" * 40
        spec = {"url": "https://github.com/example/source.git", "ref": "main"}
        with patch.object(resolve.subprocess, "check_output", return_value=sha + "\trefs/heads/main\n"):
            self.assertEqual(resolve.resolve_branch(spec)["commit"], sha)

    def test_missing_branch_fails(self):
        with patch.object(resolve.subprocess, "check_output", return_value=""):
            with self.assertRaises(RuntimeError):
                resolve.resolve_branch({"url": "https://github.com/example/source.git", "ref": "main"})

    def test_official_feeds_cannot_drift_to_master(self):
        with patch.object(resolve, "fetch", return_value=b"src-git packages https://github.com/immortalwrt/packages.git;master\n"):
            with self.assertRaises(RuntimeError):
                resolve.resolve_feeds({"url": "https://github.com/immortalwrt/immortalwrt.git", "commit": "a" * 40})

    def test_upstream_checksum_required_for_alpha(self):
        digest = "a" * 64
        self.assertEqual(resolve.checksum_for(f"{digest}  ./core.tar.gz\n", "core.tar.gz"), digest)
        with self.assertRaises(RuntimeError):
            resolve.checksum_for(f"{digest}  ./other.tar.gz\n", "core.tar.gz")

    def test_changed_download_fails_before_caching(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(resolve, "fetch", return_value=b"new bytes"):
                with self.assertRaises(RuntimeError):
                    resolve.save_asset({"file": "test.dat", "url": "https://example.com/test"}, Path(directory), "0" * 64)
            self.assertFalse((Path(directory) / "test.dat").exists())

    def test_geoip_and_geosite_use_same_latest_release(self):
        content = b"release payload"
        digest = hashlib.sha256(content).hexdigest()
        release = {"tag_name": "today", "id": 100, "assets": [
            {"name": name, "id": number, "updated_at": "now", "size": len(content),
             "browser_download_url": f"https://example.com/{name}", "digest": "sha256:" + digest}
            for name, number in [("geoip.dat", 1), ("geosite.dat", 2)]
        ]}
        policies = [
            {"file": file, "repo": "example/rules", "release": "latest", "asset": asset}
            for file, asset in [("GeoIP.dat", "geoip.dat"), ("GeoSite.dat", "geosite.dat")]
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(resolve, "api", return_value=release) as api, patch.object(resolve, "fetch", return_value=content):
                results = resolve.resolve_geodata(policies, Path(directory))
            api.assert_called_once_with("example/rules/releases/latest")
            self.assertEqual([item["release_id"] for item in results], [100, 100])
            self.assertEqual((Path(directory) / "GeoIP.dat").read_bytes(), content)

    def test_release_digest_mismatch_fails(self):
        release = {"tag_name": "latest", "id": 1, "assets": [
            {"name": "ASN.mmdb", "id": 2, "updated_at": "now", "size": 3,
             "browser_download_url": "https://example.com/ASN.mmdb", "digest": "sha256:" + "0" * 64}
        ]}
        policy = [{"repo": "example/asn", "release": "tag:latest", "asset": "ASN.mmdb", "file": "ASN.mmdb"}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(resolve, "api", return_value=release) as api, patch.object(resolve, "fetch", return_value=b"abc"):
                with self.assertRaises(RuntimeError):
                    resolve.resolve_geodata(policy, Path(directory))
                api.assert_called_once_with("example/asn/releases/tags/latest")

    def test_prepare_uses_cached_bytes_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory) / "assets"
            assets.mkdir()
            source = assets / "GeoIP.dat"
            source.write_bytes(b"snapshot")
            spec = {"file": source.name, "sha256": hashlib.sha256(b"snapshot").hexdigest()}
            target = Path(directory) / "output/GeoIP.dat"
            prepare.copy_asset(spec, assets, target)
            self.assertEqual(target.read_bytes(), b"snapshot")
            source.write_bytes(b"changed upstream or tampered cache")
            with self.assertRaises(RuntimeError):
                prepare.copy_asset(spec, assets, target)
            self.assertEqual(target.read_bytes(), b"snapshot")

    def test_core_archive_does_not_extract_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "core.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                entry = tarfile.TarInfo("../clash")
                entry.size = 3
                bundle.addfile(entry, io.BytesIO(b"bad"))
            with self.assertRaises(RuntimeError):
                prepare.unpack_core(archive, Path(directory) / "clash", "tar.gz")

    def test_policy_keeps_maintenance_and_alpha_v2(self):
        policy = json.loads((SCRIPTS.parent / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["core"]["ref"], "openwrt-25.12")
        self.assertEqual(policy["mihomo"]["channel"], "alpha")
        self.assertEqual(policy["mihomo"]["architecture"], "linux-amd64-v2")
        self.assertEqual({item["file"] for item in policy["geodata"]},
                         {"Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"})
        self.assertTrue(all("commit" not in item for item in policy["plugins"].values()))


if __name__ == "__main__":
    unittest.main()
