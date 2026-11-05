"""Regression checks for the Fullcone backport and removed vnStat packages."""
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
sys.path.insert(0, str(ROOT / "immortalwrt-25.12/scripts"))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(result)
    finally:
        sys.path.pop(0)
    return result


prepare = module("fixed_prepare", FIXED / "scripts/prepare.py")


class TrafficConfiguration(unittest.TestCase):
    def test_fixed_backport_applies_and_cannot_be_silently_reapplied(self):
        lock = json.loads((FIXED / "sources.lock.json").read_text())
        # Minimal original context from the pinned generic kernel configuration.
        context = "\n".join([
            "# CONFIG_NF_CONNTRACK is not set",
            "# CONFIG_NF_CONNTRACK_AMANDA is not set",
            "# CONFIG_NF_CONNTRACK_BRIDGE is not set",
            "# CONFIG_NF_CONNTRACK_EVENTS is not set",
            "# CONFIG_NF_CONNTRACK_FTP is not set",
            "# CONFIG_NF_CONNTRACK_H323 is not set", "",
        ])
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            config = work / "target/linux/generic/config-6.12"
            config.parent.mkdir(parents=True)
            config.write_text(context, newline="\n")
            subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
            subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=work, check=True)
            prepare.apply_backports(work, {**lock, "patches": lock["patches"][:1]})
            self.assertIn("CONFIG_NF_CONNTRACK_CHAIN_EVENTS", config.read_text())
            patch = work / "target/linux/generic/hack-6.12/952-net-conntrack-events-support-multiple-registrant.patch"
            self.assertIn("atomic_notifier_chain_register", patch.read_text())
            with self.assertRaises(subprocess.CalledProcessError):
                prepare.apply_backports(work, {**lock, "patches": lock["patches"][:1]})

    def test_backport_checksum_failure_stops_before_applying(self):
        lock = json.loads((FIXED / "sources.lock.json").read_text())
        lock["patches"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Backport SHA256 mismatch"):
                prepare.apply_backports(Path(directory), lock)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_collectors_reject_vnstat_and_unfixed_kernel(self):
        for recipe in ("immortalwrt-25.12", FIXED.name):
            with self.subTest(recipe=recipe), tempfile.TemporaryDirectory() as directory:
                collect = module(recipe.replace("-", "_") + "_collect", ROOT / recipe / "scripts/collect.py")
                work = Path(directory)
                target = work / "bin/targets/x86/64"
                target.mkdir(parents=True)
                manifest = target / "firmware.manifest"
                packages = collect.REQUIRED_PACKAGES
                manifest.write_text("\n".join(f"{name} - 1" for name in packages | {"vnstat2"}))
                with self.assertRaisesRegex(RuntimeError, "unwanted=.*vnstat2"):
                    collect.validate(work)
                manifest.write_text("\n".join(f"{name} - 1" for name in packages))
                kernel = work / "build_dir/target-test/linux-x86_64/linux-6.12.103/.config"
                kernel.parent.mkdir(parents=True)
                kernel.write_text("\n".join(
                    f"{name}=y" for name in collect.KERNEL_FEATURES
                    if name != "CONFIG_NF_CONNTRACK_CHAIN_EVENTS"
                ))
                with self.assertRaisesRegex(RuntimeError, "CONFIG_NF_CONNTRACK_CHAIN_EVENTS"):
                    collect.validate(work)


if __name__ == "__main__":
    unittest.main()
