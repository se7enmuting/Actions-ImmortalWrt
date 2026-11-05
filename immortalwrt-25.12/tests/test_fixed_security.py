"""Apply the reviewed security chain to real fixed-base files and reject old outputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "immortalwrt-25.12-fixed-25.12.2-20261105"
sys.path.insert(0, str(FIXED / "scripts"))
spec = importlib.util.spec_from_file_location("fixed_security_prepare", FIXED / "scripts/prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
from verify_security import verify_manifest


class FixedSecurity(unittest.TestCase):
    def test_real_locked_base_accepts_complete_security_chain_and_hashes(self):
        lock = json.loads((FIXED / "sources.lock.json").read_text())
        fixture = json.loads((Path(__file__).parent / "fixtures/fixed-security-base.json").read_text())
        self.assertEqual(fixture["commit"], lock["core"]["commit"])
        self.assertEqual(len(lock["patches"][1:]), 8)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for name, text in fixture["files"].items():
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="\n")
            subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
            subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=work, check=True)
            prepare.apply_backports(work, {**lock, "patches": lock["patches"][1:]})
            for name, digest in lock["security_revision"]["expected_files"].items():
                self.assertEqual(hashlib.sha256((work / name).read_bytes()).hexdigest(), digest, name)

    def test_fixed_asn_snapshot_retains_original_digest_without_network(self):
        lock = json.loads((FIXED / "sources.lock.json").read_text())
        spec = next(s for s in lock["geodata"] if s["file"] == "ASN.mmdb")
        self.assertEqual(spec["sha256"], "3169b9ea7dad762f6837b95408dadc1173f47be33be2d83b6c90e67a57a7eb2e")
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory, patch.object(prepare.urllib.request, "urlopen", side_effect=AssertionError("network")):
            path = Path(directory) / "ASN.mmdb"
            prepare.install_geodata(spec, path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), spec["sha256"])
            with self.assertRaisesRegex(RuntimeError, "SHA256 mismatch"):
                prepare.install_geodata({**spec, "sha256": "0" * 64}, path)

    def test_old_or_missing_security_package_versions_block_publication(self):
        good = "uhttpd - 2026.08.24~373145f7-r1\nopenssl-util - 3.5.9-r1\nca-bundle - 20260816-r2\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firmware.manifest"
            path.write_text(good)
            verify_manifest(path)
            for old in (good.replace("3.5.9", "3.5.7"), good.replace("373145f7", "7b1bec45"), good.replace("20260816-r2", "20260601-r1")):
                path.write_text(old)
                with self.assertRaisesRegex(RuntimeError, "Security package version mismatch"):
                    verify_manifest(path)


if __name__ == "__main__":
    unittest.main()
