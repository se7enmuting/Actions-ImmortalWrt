"""Check data selection, complete-set fallback and public provenance records."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "immortalwrt-25.12-fixed-25.12.2-20261105"
sys.path.insert(0, str(FIXED / "scripts"))
import geodata
from geodata_release import render
NAMES = ["Country.mmdb", "GeoIP.dat", "GeoSite.dat", "ASN.mmdb"]


class DataPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.recipe = Path(self.temp.name)
        self.cache = self.recipe / "cache"
        self.cache.mkdir()
        self.records = []
        for name in NAMES:
            data = ("fallback-" + name).encode()
            (self.cache / name).write_bytes(data)
            self.records.append({"file": name, "sha256": hashlib.sha256(data).hexdigest(),
                                 "release": "cached-version", "downloaded_at": "2026-11-05T00:00:00Z"})
        (self.cache / "manifest.json").write_text(json.dumps({"assets": self.records}))
        (self.recipe / "geodata.policy.json").write_text(json.dumps({"fallback": "cache", "sources": [{"file": n} for n in NAMES]}))
        self.target = self.recipe / "output"

    def online(self, sources, destination):
        records = []
        for name in NAMES:
            data = ("online-" + name).encode()
            (destination / name).write_bytes(data)
            records.append({"file": name, "sha256": hashlib.sha256(data).hexdigest(), "mode": "online"})
        return records

    def test_online_success_and_current_meta_validation(self):
        with patch.object(geodata, "online", side_effect=self.online):
            validator = unittest.mock.Mock()
            records = geodata.prepare(self.recipe, self.target, Path("core"), validator)
        self.assertEqual(validator.call_count, 1)
        self.assertTrue(all(r["mode"] == "online" and r["validated_by_fixed_meta"] for r in records))
        self.assertEqual((self.target / NAMES[0]).read_bytes(), b"online-Country.mmdb")

    def test_incompatible_online_set_falls_back_as_a_complete_set(self):
        with patch.object(geodata, "online", side_effect=self.online):
            validator = unittest.mock.Mock(side_effect=[RuntimeError("incompatible"), None])
            records = geodata.prepare(self.recipe, self.target, Path("core"), validator)
        self.assertEqual(validator.call_count, 2)
        self.assertTrue(all(r["mode"] == "fallback" for r in records))
        for name in NAMES:
            self.assertEqual((self.target / name).read_bytes(), ("fallback-" + name).encode())

    def test_failed_download_and_corrupt_fallback_stop_before_installing(self):
        (self.cache / NAMES[0]).write_bytes(b"corrupt")
        with patch.object(geodata, "online", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "Fallback checksum"):
                geodata.prepare(self.recipe, self.target, Path("core"), lambda *args: None)
        self.assertFalse(self.target.exists())

    def test_release_notes_show_upstream_date_separately_from_fetch_time(self):
        lock = {"geodata": [{"file": "GeoSite.dat", "release": "202611042203", "mode": "online",
                            "source_updated_at": "2026-11-04", "fetched_at": "2026-11-05", "sha256": "a" * 64}]}
        note = render(lock)
        for value in ("GeoSite.dat", "202611042203", "2026-11-04", "2026-11-05", "online"):
            self.assertIn(value, note)
        lock["geodata"][0].update(mode="fallback", downloaded_at="2026-11-03")
        self.assertIn("托底快照", render(lock))
        self.assertIn("2026-11-03", render(lock))


if __name__ == "__main__":
    unittest.main()
