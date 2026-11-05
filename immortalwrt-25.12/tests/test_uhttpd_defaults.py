"""Run the EC defaults normalization with isolated OpenWrt UCI functions."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
RECIPES = ("immortalwrt-25.12", "immortalwrt-25.12-fixed-25.12.2-20261105")


class UhttpdDefaults(unittest.TestCase):
    def run_helper(self, recipe, algorithm, bits, fail=False):
        with tempfile.TemporaryDirectory(prefix="uhttpd-defaults-") as directory:
            root = Path(directory)
            library = root / "functions.sh"
            library.write_text("""
config_load() { [ "$1" = uhttpd ]; }
config_foreach() { [ "$2" = cert ] && "$1" defaults; }
config_get() {
    case "$3" in
        key_type) eval "$1='$TEST_ALGORITHM'" ;;
        bits) eval "$1='$TEST_BITS'" ;;
        *) return 1 ;;
    esac
}
uci() {
    printf '%s\\n' "$*" >> "$TEST_LOG"
    [ "$TEST_FAIL" != 1 ] || [ "$2" != set ]
}
""", encoding="utf-8", newline="\n")
            helper = (ROOT / recipe / "files/usr/libexec/pve-normalize-uhttpd").read_text(encoding="utf-8")
            helper = helper.replace(". /lib/functions.sh", '. "$TEST_LIBRARY"')
            path = root / "helper.sh"
            path.write_text(helper, encoding="utf-8", newline="\n")
            log = root / "events"
            env = dict(os.environ, TEST_LIBRARY=library.as_posix(), TEST_LOG=log.as_posix(),
                       TEST_ALGORITHM=algorithm, TEST_BITS=bits, TEST_FAIL="1" if fail else "0")
            result = subprocess.run([BASH, "--noprofile", "--norc", path.as_posix()],
                                    env=env, capture_output=True, text=True, timeout=20)
            return result, log.read_text().splitlines() if log.exists() else []

    def test_ec_256_changes_only_bits_and_commits(self):
        for recipe in RECIPES:
            with self.subTest(recipe=recipe):
                result, events = self.run_helper(recipe, "ec", "256")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(events, ["-q set uhttpd.defaults.bits=2048", "-q commit uhttpd"])

    def test_other_defaults_remain_unchanged(self):
        for recipe in RECIPES:
            for algorithm, bits in (("ec", "2048"), ("ec", "384"), ("rsa", "256"), ("rsa", "4096"), ("ec", "")):
                with self.subTest(recipe=recipe, algorithm=algorithm, bits=bits):
                    result, events = self.run_helper(recipe, algorithm, bits)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(events, [])

    def test_write_failure_is_reported_without_commit(self):
        for recipe in RECIPES:
            with self.subTest(recipe=recipe):
                result, events = self.run_helper(recipe, "ec", "256", fail=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("-q commit uhttpd", events)


if __name__ == "__main__":
    unittest.main()
