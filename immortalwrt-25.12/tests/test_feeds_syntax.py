"""Check generated feeds with the real upstream Perl parser."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare
import resolve

RECIPE = Path(__file__).resolve().parents[1]
PERL = shutil.which("perl") or r"C:\Program Files\Git\usr\bin\perl.exe"
PARSER = Path(__file__).parent / "fixtures/feeds-parser.pl"


class FeedsSyntax(unittest.TestCase):
    def test_latest_policy_generates_valid_upstream_feeds(self):
        policy = json.loads((RECIPE / "sources.json").read_text())
        feeds = {"packages": {"url": "https://github.com/immortalwrt/packages.git", "commit": "a" * 40}}
        with patch.object(resolve, "resolve_branch", side_effect=lambda spec: {**spec, "commit": "b" * 40}):
            names, packages = resolve.resolve_plugins(policy["plugins"], feeds)
        self.assertEqual({spec["package_dir"] for spec in packages.values()},
                         {"luci-theme-argon", "luci-app-argon-config"})
        self.assertNotIn("argon", feeds)
        text = prepare.render_feeds({"feeds": feeds, "plugin_feeds": names})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feeds.conf.default"
            path.write_text(text, newline="\n")
            result = subprocess.run([PERL, PARSER.as_posix(), path.as_posix()],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), set(feeds))

    def test_original_hyphenated_feed_failure_is_reproduced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feeds.conf.default"
            path.write_text("src-git luci-theme-argon https://github.com/jerrykuku/luci-theme-argon.git\n",
                            newline="\n")
            result = subprocess.run([PERL, PARSER.as_posix(), path.as_posix()],
                                    capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Syntax error", result.stderr)

    def test_render_rejects_invalid_feed_name(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid feed identifier"):
            prepare.render_feeds({"plugin_feeds": [], "feeds": {
                "luci-theme-argon": {"url": "https://example.com/repo.git", "commit": "a" * 40}
            }})


if __name__ == "__main__":
    unittest.main()
