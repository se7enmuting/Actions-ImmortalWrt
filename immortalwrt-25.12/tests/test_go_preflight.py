"""Exercise the Xray compiler mismatch before the full firmware build."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import go_preflight


class GoPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / "feeds/packages/lang/golang"
        self.root.mkdir(parents=True)
        self.defaults = self.root / "golang-values.mk"
        self.defaults.write_text("# official default\nGO_DEFAULT_VERSION:=1.26\n", newline="\n")
        (self.work / "build-lock.json").write_text(json.dumps({"feeds": {"packages": {"commit": "a" * 40}}}))
        (self.work / ".config").write_text("CONFIG_PACKAGE_xray-core=y\n")
        (self.work / "dl").mkdir()
        self.recipe("1.26", "10")
        self.recipe("1.27", "3")

    def recipe(self, series, patch, rc=""):
        path = self.root / ("golang" + series) / "Makefile"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"GO_VERSION_MAJOR_MINOR:={series}\nGO_VERSION_PATCH:={patch}\nGO_VERSION_RC:={rc}\n")

    def source(self, requirement="1.27", module=True):
        path = self.work / "feeds/passwall_packages/xray-core/Makefile"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PKG_NAME:=Xray-core\nPKG_VERSION:=26.10.31\n")
        archive = self.work / "dl/Xray-core-26.10.31.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            if module:
                data = f"module github.com/xtls/xray-core\n\ngo {requirement}\n".encode()
                member = tarfile.TarInfo("Xray-core-26.10.31/go.mod")
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data))
        return archive

    def test_selects_stable_official_compiler_and_records_selector_hashes(self):
        original = self.defaults.read_bytes()
        self.recipe("1.28", "0", "rc1")
        self.assertEqual(go_preflight.choose(self.work), "1.27")
        self.assertIn("GO_DEFAULT_VERSION:=1.27", self.defaults.read_text())
        record = json.loads((self.work / "build-lock.json").read_text())["go_toolchain"]
        self.assertEqual(record["version"], "1.27.3")
        self.assertEqual(record["default_original_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(record["default_selected_sha256"], hashlib.sha256(self.defaults.read_bytes()).hexdigest())

    def test_xray_127_is_checked_without_modifying_download(self):
        go_preflight.choose(self.work)
        archive = self.source()
        original = archive.read_bytes()
        go_preflight.check(self.work)
        self.assertEqual(original, archive.read_bytes())
        record = json.loads((self.work / "build-lock.json").read_text())["go_toolchain"]
        self.assertEqual(record["checked_modules"]["xray-core"]["requires_go"], "1.27")

    def test_original_go126_mismatch_fails_in_preflight(self):
        (self.root / "golang1.27/Makefile").unlink()
        go_preflight.choose(self.work)
        self.source()
        with self.assertRaisesRegex(RuntimeError, "requires Go 1.27.*1.26.10"):
            go_preflight.check(self.work)

    def test_future_patch_requirement_is_also_rejected(self):
        go_preflight.choose(self.work)
        self.source("1.27.4")
        with self.assertRaisesRegex(RuntimeError, "requires Go 1.27.4"):
            go_preflight.check(self.work)

    def test_missing_module_is_not_silently_accepted(self):
        go_preflight.choose(self.work)
        self.source(module=False)
        with self.assertRaisesRegex(RuntimeError, "root go.mod"):
            go_preflight.check(self.work)

    def test_changed_selector_is_rejected(self):
        go_preflight.choose(self.work)
        self.source()
        self.defaults.write_text("GO_DEFAULT_VERSION:=1.26\n")
        with self.assertRaisesRegex(RuntimeError, "selector changed"):
            go_preflight.check(self.work)

    def test_changed_upstream_selector_syntax_fails_before_editing(self):
        self.defaults.write_text("GO_DEFAULT_VERSION = 1.26\n")
        original = self.defaults.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "default selector"):
            go_preflight.choose(self.work)
        self.assertEqual(original, self.defaults.read_bytes())


if __name__ == "__main__":
    unittest.main()
