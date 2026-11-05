"""Execute both first-boot profiles with isolated UCI and init services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or (
    r"C:\Program Files\Git\bin\bash.exe"
    if Path(r"C:\Program Files\Git\bin\bash.exe").exists() else None
)
RECIPES = ["immortalwrt-25.12", "immortalwrt-25.12-fixed-25.12.2-20261105"]


@unittest.skipUnless(BASH, "bash required to execute the first-boot profiles")
class OafFirstBoot(unittest.TestCase):
    def run_profile(self, recipe):
        with tempfile.TemporaryDirectory(prefix="oaf-firstboot-") as directory:
            root = Path(directory)
            init = root / "etc/init.d"
            init.mkdir(parents=True)
            service = '#!/bin/sh\nprintf "%s %s\\n" "${0##*/}" "$*" >> "$OAF_TEST_ROOT/events"\n'
            for name in ("bandix", "nlbwmon", "qemu-ga", "appfilter", "openclash",
                         "passwall", "miniupnpd", "ddns", "acme"):
                path = init / name
                path.write_text(service, encoding="utf-8", newline="\n")
                path.chmod(0o755)
            # Map absolute filesystem accesses into the disposable fixture.
            profile = (ROOT / recipe / "files/etc/uci-defaults/99-pve-profile").read_text(encoding="utf-8")
            isolated = profile.replace("/etc/", "${OAF_TEST_ROOT}/etc/")
            mock_uci = r'''
uci() {
    printf 'uci %s\n' "$*" >> "$OAF_TEST_ROOT/events"
    if [ "$*" = "-q batch" ]; then
        cat >> "$OAF_TEST_ROOT/batch"
    fi
}
'''
            test_profile = root / "profile.sh"
            test_profile.write_text(mock_uci + isolated, encoding="utf-8", newline="\n")
            env = dict(os.environ, OAF_TEST_ROOT=root.as_posix())
            result = subprocess.run([BASH, "--noprofile", "--norc", test_profile.as_posix()],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            return ((root / "events").read_text().splitlines(),
                    (root / "batch").read_text())

    def test_service_is_enabled_and_started_on_first_boot_after_commit(self):
        for recipe in RECIPES:
            with self.subTest(recipe=recipe):
                events, batch = self.run_profile(recipe)
                self.assertIn("appfilter enable", events)
                self.assertIn("appfilter start", events)
                self.assertNotIn("appfilter disable", events)
                self.assertLess(events.index("appfilter enable"), events.index("appfilter start"))
                config = "appfilter" if "fixed" in recipe else "fwx"
                self.assertLess(events.index(f"uci -q commit {config}"), events.index("appfilter start"))

    def test_optional_services_retain_autostart_with_functions_disabled(self):
        for recipe in RECIPES:
            with self.subTest(recipe=recipe):
                events, batch = self.run_profile(recipe)
                for name in ("openclash", "passwall", "miniupnpd"):
                    self.assertIn(name + " enable", events)
                    self.assertNotIn(name + " disable", events)
                self.assertIn("set openclash.config.enable='0'", batch)
                self.assertIn("set passwall.@global[0].enabled='0'", batch)
                self.assertIn("set upnpd.config.enabled='0'", batch)
                self.assertIn("miniupnpd start", events)
                self.assertNotIn("openclash start", events)
                self.assertNotIn("passwall start", events)
                self.assertIn("ddns disable", events)
                self.assertIn("acme disable", events)

    def test_fixed_and_latest_use_their_own_native_switches(self):
        fixed_events, fixed = self.run_profile(RECIPES[1])
        latest_events, latest = self.run_profile(RECIPES[0])
        for setting in ("appfilter.global.enable='1'", "appfilter.global.record_enable='1'",
                        "appfilter.global.auto_load_engine='1'", "appfilter.global.app_filter_mode='0'"):
            self.assertIn("set " + setting, fixed)
        for setting in ("fwx.appfilter.enable='1'", "fwx.record.enable='1'",
                        "fwx.macfilter.enable='0'", "macfilter.global.enable='0'"):
            self.assertIn("set " + setting, latest)
        self.assertNotIn("appfilter.global.", latest)
        self.assertNotIn("fwx.", fixed)
        # Enabling collection must not introduce a blocklist.
        self.assertNotIn("app_list", fixed)
        self.assertNotIn("app_list", latest)


if __name__ == "__main__":
    unittest.main()
