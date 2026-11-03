#!/usr/bin/env python3
"""Reject local state and generated output in the public source tree."""
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = {
    "generated-artifacts", "attached_assets", ".agents", ".local", ".cache",
    ".conversation", ".replit", ".replitignore", "replit.md", "node_modules",
    ".idea", ".vscode", ".claude", ".cursor", ".codex", "AGENTS.md", "CLAUDE.md",
    "build", "dist", "coverage", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".venv", "venv",
}
OUTPUT_SUFFIXES = {".o", ".a", ".elf", ".map", ".su", ".pyc", ".log"}
IGNORE_PROBES = (
    "generated-artifacts/releases/example.zip",
    "generated-artifacts/nested/build/firmware.ipod",
    ".agents/memory/MEMORY.md", ".local/toolchain/bin/gcc",
    "attached_assets/upload.jpg", ".env", ".env.production",
    ".cache/example", "__pycache__/example.pyc", "build/example.o",
)


def forbidden(name):
    path = PurePosixPath(name)
    return (path.parts[0] in LOCAL or path.parts[0].startswith("build-")
            or "__pycache__" in path.parts
            or path.name in (".DS_Store", "Thumbs.db")
            or path.suffix.lower() in OUTPUT_SUFFIXES
            or (path.name.startswith(".env") and not
                (path.name == ".env.example" or path.name.endswith(".example"))))


def main():
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    bad = [name for name in tracked if name and forbidden(name)]
    for name in IGNORE_PROBES:
        if subprocess.run(["git", "check-ignore", "-q", "--", name],
                          cwd=ROOT).returncode != 0:
            bad.append(f"not ignored: {name}")
    if bad:
        print("Public source must not include local state or build output:",
              *bad, sep="\n  ", file=sys.stderr)
        return 1
    print("Public repository check passed: local state and build output excluded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
