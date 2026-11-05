"""Run both real publication scripts against a fault-injecting gh stub."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("build-immortalwrt-*.yml"))


def step_script(text, name):
    step = text.split("      - name: " + name + "\n", 1)[1].split("\n      - name:", 1)[0]
    script = step.split("        run: |\n", 1)[1]
    lines = []
    for line in script.splitlines():
        if line.strip() and not line.startswith("          "):
            break
        lines.append(line[10:] if line.startswith("          ") else "")
    return "\n".join(lines)


class ReleaseRetry(unittest.TestCase):
    def test_interrupted_upload_remains_draft_and_same_build_can_retry(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                (work / "firmware").mkdir()
                (work / "firmware/BUILD-INFO.md").write_text("build record")
                (work / "firmware/image.img.gz").write_bytes(b"firmware")
                (work / "bin").mkdir()
                stub = work / "bin/gh"
                stub.write_text("""#!/bin/bash
set -eu
echo "$*" >> gh-calls.log
case "$1 $2" in
  'release view')
    test -f draft || exit 1
    if [[ " $* " == *" --json "* ]]; then echo https://example.test/release; fi ;;
  'release create')
    test ! -e draft
    [[ " $* " == *" --draft "* ]]
    [[ " $* " == *" --verify-tag "* ]]
    [[ " $* " != *" --target "* ]]
    touch draft ;;
  'release upload')
    [[ " $* " == *" --clobber "* ]]
    if [[ ! -e failed-once ]]; then touch failed-once; exit 1; fi
    touch uploaded ;;
  'release edit')
    test -f uploaded
    [[ " $* " == *" --draft=false "* ]]
    touch published ;;
  *) exit 2 ;;
esac
""", encoding="utf-8", newline="\n")
                stub.chmod(0o755)
                text = workflow.read_text(encoding="utf-8")
                script = work / "publish.sh"
                script.write_text(step_script(text, "Publish this manual build"), encoding="utf-8", newline="\n")
                # Convert the PATH inside Bash so Windows path separators cannot affect command lookup.
                command = 'export PATH="$PWD/bin:$PATH"; bash publish.sh'
                env = {**os.environ, "GITHUB_STEP_SUMMARY": "summary.md", "BUILD_NUMBER": "4",
                       "BUILD_ATTEMPT": "1", "SOURCE_COMMIT": "a" * 40}
                first = subprocess.run([BASH, "-c", command], cwd=work, env=env, capture_output=True, timeout=15)
                self.assertNotEqual(first.returncode, 0)
                self.assertTrue((work / "draft").exists())
                self.assertFalse((work / "published").exists())
                second = subprocess.run([BASH, "-c", command], cwd=work, env=env, capture_output=True, timeout=15)
                self.assertEqual(second.returncode, 0, second.stderr.decode(errors="replace"))
                self.assertTrue((work / "published").exists())
                calls = (work / "gh-calls.log").read_text().splitlines()
                self.assertEqual(sum(line.startswith("release create ") for line in calls), 1)
                self.assertEqual(sum(line.startswith("release upload ") for line in calls), 2)
                release_job = text.split("  release:\n", 1)[1]
                self.assertIn("name: ${{ needs.build.outputs.firmware_artifact }}", release_job)
                self.assertIn("BUILD_ATTEMPT: ${{ needs.build.outputs.build_attempt }}", release_job)

    def test_tag_permission_and_target_checks_run_before_compilation(self):
        for workflow in WORKFLOWS:
            for status, succeeds, creates in [("missing", True, True), ("existing", True, False),
                                               ("different", False, False), ("denied", False, False)]:
                with self.subTest(workflow=workflow.name, status=status), tempfile.TemporaryDirectory() as directory:
                    work = Path(directory)
                    (work / "bin").mkdir()
                    stub = work / "bin/gh"
                    stub.write_text("""#!/bin/bash
set -eu
if [[ " $* " == *" --method POST "* ]]; then touch created; echo '{}'; exit 0; fi
case "$TAG_TEST_STATUS" in
 missing) echo 'HTTP 404' >&2; exit 1 ;;
 existing) echo "$SOURCE_COMMIT" ;;
 different) echo wrong-commit ;;
 denied) echo 'HTTP 403: Resource not accessible by integration' >&2; exit 1 ;;
esac
""", newline="\n")
                    stub.chmod(0o755)
                    text = workflow.read_text(encoding="utf-8")
                    (work / "reserve.sh").write_text(step_script(text, "Reserve tag for the exact build commit before compilation"), newline="\n")
                    env = {**os.environ, "TAG_TEST_STATUS": status, "SOURCE_COMMIT": "a" * 40,
                           "GH_REPO": "example/repo", "TAG": "test-tag"}
                    result = subprocess.run([BASH, "-c", 'export PATH="$PWD/bin:$PATH"; bash reserve.sh'],
                                            cwd=work, env=env, capture_output=True, timeout=15)
                    self.assertEqual(result.returncode == 0, succeeds, result.stderr.decode(errors="replace"))
                    self.assertEqual((work / "created").exists(), creates)
                    self.assertIn("needs: reserve_release_tag", text)

    def test_download_corruption_blocks_publication(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                (work / "BUILD-INFO.md").write_text("record")
                image = work / "image.img.gz"
                image.write_bytes(b"firmware")
                (work / "SHA256SUMS").write_text(hashlib.sha256(image.read_bytes()).hexdigest() + "  image.img.gz\n", newline="\n")
                script = step_script(workflow.read_text(encoding="utf-8"), "Verify downloaded firmware checksums")
                good = subprocess.run([BASH, "-e", "-c", script], cwd=work, capture_output=True, timeout=15)
                self.assertEqual(good.returncode, 0, good.stderr.decode(errors="replace"))
                image.write_bytes(b"corrupt")
                bad = subprocess.run([BASH, "-e", "-c", script], cwd=work, capture_output=True, timeout=15)
                self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
