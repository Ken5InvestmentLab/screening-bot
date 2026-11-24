"""Historical approval reads return the exact bytes verified by ordinary Git."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from weak_early_beta.new_a.approval_git import approval_blobs, approval_git


class ApprovalGitTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.repo = Path(workspace.name)
        self.git("init", "-q")
        (self.repo / "evidence.txt").write_bytes(b"original\r\nbytes\x00\xff\n")
        self.git("add", "evidence.txt")
        self.commit("original")
        self.original = self.git("rev-parse", "HEAD").strip().decode()
        (self.repo / "evidence.txt").write_bytes(b"new\n")
        self.git("add", "evidence.txt")
        self.commit("new")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo)

    def commit(self, message):
        self.git("-c", "user.name=Approval Test", "-c", "user.email=test@example.invalid", "commit", "-qm", message)

    def test_pins_are_decoded_independently_and_other_commands_are_live(self):
        older = self.original + ":evidence.txt"
        newer = self.git("rev-parse", "HEAD").strip().decode() + ":evidence.txt"
        with approval_blobs(self.repo):
            self.assertEqual(approval_git(self.repo, "show", older), self.git("show", older))
            self.assertEqual(approval_git(self.repo, "show", newer), self.git("show", newer))
            self.assertEqual(approval_git(self.repo, "show", older), self.git("show", older))
            self.assertEqual(approval_git(self.repo, "rev-parse", "HEAD"), self.git("rev-parse", "HEAD"))
            with self.assertRaises(subprocess.CalledProcessError):
                approval_git(self.repo, "show", self.original + ":missing.txt")
            self.assertEqual(approval_git(self.repo, "show", newer), self.git("show", newer))

    def test_regular_git_is_used_with_replacement_refs(self):
        self.git("replace", self.original, "HEAD")
        target = self.original + ":evidence.txt"
        with approval_blobs(self.repo):
            self.assertEqual(approval_git(self.repo, "show", target), b"new\n")

    def test_fails_if_replacements_appear_during_the_read(self):
        with self.assertRaisesRegex(ValueError, "replacement refs changed"):
            with approval_blobs(self.repo):
                self.git("replace", self.original, "HEAD")
