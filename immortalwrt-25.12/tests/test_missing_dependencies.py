import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_dependencies import verify


class MissingDependencies(unittest.TestCase):
    def test_selected_core_dependency_failure_is_caught_early(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "tmp").mkdir()
            (work / ".config").write_text("CONFIG_PACKAGE_autocore=y\n")
            (work / "tmp/.packageinfo").write_text("Source-Makefile: package/emortal/autocore/Makefile\nPackage: autocore\n")
            (work / "defconfig.log").write_text("WARNING: Makefile 'package/emortal/autocore/Makefile' has a dependency on 'lm-sensors', which does not exist\n")
            with self.assertRaisesRegex(RuntimeError, "missing lm-sensors"):
                verify(work)
            (work / ".config").write_text("# CONFIG_PACKAGE_autocore is not set\n")
            verify(work)
            (work / ".config").write_text("CONFIG_PACKAGE_autocore=y\n")
            (work / "defconfig.log").write_text("")
            verify(work)


if __name__ == "__main__":
    unittest.main()
