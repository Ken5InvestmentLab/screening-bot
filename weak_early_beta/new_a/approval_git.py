"""Read pinned approval blobs through one Git process per verification."""

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import re
import subprocess


_GIT = ("git", "--no-optional-locks")
_BLOB = re.compile(r"[a-f0-9]{40}:([A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+")
_HEADER = re.compile(rb"[a-f0-9]{40} blob (0|[1-9][0-9]{0,8})\n")
_ACTIVE = ContextVar("approval_git_reader", default=None)


def _replacement_refs(repo):
    return subprocess.check_output(
        [*_GIT, "for-each-ref", "--format=%(objectname) %(refname)", "refs/replace"],
        cwd=repo,
    )


@contextmanager
def approval_blobs(repo):
    """Retain ordinary Git reads where a repository uses object replacements."""
    repo = Path(repo).resolve()
    if "GIT_REPLACE_REF_BASE" in os.environ or _replacement_refs(repo):
        yield
        return

    with subprocess.Popen(
        [*_GIT, "cat-file", "--batch"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as process:
        token = _ACTIVE.set((repo, process))
        try:
            yield
            if _replacement_refs(repo):
                raise ValueError("Approval Git replacement refs changed during verification")
        finally:
            _ACTIVE.reset(token)
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def approval_git(repo, *args):
    active = _ACTIVE.get()
    if (active is None or len(args) != 2 or args[0] != "show"
            or not isinstance(args[1], str) or not _BLOB.fullmatch(args[1])
            or Path(repo).resolve() != active[0]):
        return subprocess.check_output([*_GIT, *args], cwd=repo)

    process = active[1]
    request = args[1].encode("ascii")
    process.stdin.write(request + b"\n")
    process.stdin.flush()
    header = process.stdout.readline(len(request) + 64)
    if header == request + b" missing\n":
        raise subprocess.CalledProcessError(128, [*_GIT, *args])
    match = _HEADER.fullmatch(header)
    if not match:
        raise ValueError("Approval Git object is not a regular blob")
    size = int(match.group(1))
    if size > 128 * 1024 * 1024:
        raise ValueError("Approval Git blob exceeds the retained input limit")
    body = process.stdout.read(size)
    if len(body) != size or process.stdout.read(1) != b"\n":
        raise ValueError("Approval Git blob output is incomplete")
    return body
