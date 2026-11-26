#!/usr/bin/env python3
"""Validate a released ZIP and run its dependency-free scientific checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile


MAX_MEMBERS = 20_000
MAX_UNCOMPRESSED_BYTES = 1_073_741_824
MAX_COMPRESSION_RATIO = 250
TEXT_SUFFIXES = {
    ".cfg", ".conf", ".csv", ".html", ".ini", ".ipynb", ".json",
    ".jsonl", ".log", ".md", ".py", ".r", ".rst", ".sh", ".tex",
    ".toml", ".ts", ".tsv", ".txt", ".xml", ".yaml", ".yml",
}
HOME_PATH = re.compile(
    rb"(?:/" + rb"Users/[^/\s]+/|/" + rb"home/[^/\s]+/|[A-Za-z]:\\" + rb"Users\\[^\\\s]+\\)"
)
CREDENTIAL_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"(?i)\bAuthorization[ \t]*:[ \t]*(?:Basic|Bearer)[ \t]+[^\s]{8,}"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(
        rb"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|pwd)"
        rb"[ \t]*[:=][ \t]*['\"][A-Za-z0-9._~+/-]{12,}['\"]"
    ),
    re.compile(rb"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s:/]+:[^\s@/]+@"),
)
WINDOWS_RESERVED = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE
)


class VerificationFailure(RuntimeError):
    """A public archive or scientific-contract check failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def relative_member_name(name: str) -> str:
    path = PurePosixPath(name)
    require(name and not name.startswith("/") and "\\" not in name, "unsafe archive member path")
    require(all(part not in ("", ".", "..") for part in name.split("/")), "ambiguous archive member path")
    require(".." not in path.parts and "." not in path.parts, "unsafe archive member path")
    require(len(path.parts) >= 2 and path.parts[0], "archive must have one non-empty root directory")
    return PurePosixPath(*path.parts[1:]).as_posix()


def credential_like_material(content: bytes) -> bool:
    return any(pattern.search(content) is not None for pattern in CREDENTIAL_PATTERNS)


def portable_home_path(content: bytes) -> bool:
    return HOME_PATH.search(content) is not None


def check_archive_members(members: list[zipfile.ZipInfo]) -> dict[str, int]:
    require(members, "archive has no file members")
    require(len(members) <= MAX_MEMBERS, "archive member limit exceeded")
    roots: set[str] = set()
    portable_names: set[str] = set()
    total_size = 0
    for member in members:
        relative = relative_member_name(member.filename)
        roots.add(PurePosixPath(member.filename).parts[0])
        require(not member.is_dir(), "directory entry supplied as a file member")
        file_type = stat.S_IFMT(member.external_attr >> 16)
        require(file_type in (0, stat.S_IFREG), "archive special-file member is not permitted")
        require(not relative.startswith(".git/") and relative != ".git", "version-control metadata is not permitted")
        parts = PurePosixPath(relative).parts
        require("__MACOSX" not in parts, "macOS resource-fork metadata is not permitted")
        require(not any(part.startswith("._") or part == ".DS_Store" for part in parts), "Finder metadata is not permitted")
        require(not any(":" in part or WINDOWS_RESERVED.match(part) for part in parts), "archive member is not portable to Windows")
        require(not any(any(ord(char) < 32 or ord(char) == 127 for char in part) for part in parts), "archive member contains control characters")
        require(not any(part.endswith((" ", ".")) for part in parts), "archive member has a non-portable trailing character")
        portable_name = "/".join(unicodedata.normalize("NFC", part).casefold() for part in parts)
        require(portable_name not in portable_names, "archive has a cross-platform path collision")
        portable_names.add(portable_name)
        require(
            not re.search(r"(?:^|/)(?:\.env(?:\..*)?|id_rsa|id_ed25519|credentials)(?:$|/)", relative, re.IGNORECASE),
            "archive includes a credential-like filename",
        )
        total_size += member.file_size
        require(total_size <= MAX_UNCOMPRESSED_BYTES, "archive expanded-size limit exceeded")
        if member.compress_size:
            require(member.file_size / member.compress_size <= MAX_COMPRESSION_RATIO, "archive compression-ratio limit exceeded")
    require(len(roots) == 1, "archive must have exactly one top-level directory")
    return {"members": len(members), "uncompressed_bytes": total_size}


def checked_file_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    require(len(entries) <= MAX_MEMBERS, "archive member limit exceeded")
    files = [entry for entry in entries if not entry.is_dir()]
    check_archive_members(files)
    root = PurePosixPath(files[0].filename).parts[0]
    seen = set()
    for entry in entries:
        name = entry.filename.rstrip("/")
        require(name and not name.startswith("/") and "\\" not in name, "unsafe archive member path")
        parts = name.split("/")
        require(all(part not in ("", ".", "..") for part in parts), "unsafe archive member path")
        require(parts[0] == root, "archive has an unexpected root")
        require(not any(any(ord(c) < 32 or ord(c) == 127 for c in p) for p in parts), "archive path has control characters")
        require(not any(p in (".git", "__MACOSX", ".DS_Store") or p.startswith("._") for p in parts), "archive has unrelated metadata")
        require(not any(":" in p or WINDOWS_RESERVED.match(p) or p.endswith((" ", ".")) for p in parts), "non-portable archive path")
        key = unicodedata.normalize("NFC", name).casefold()
        require(key not in seen, "archive contains colliding entries")
        seen.add(key)
        if entry.is_dir():
            require(stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFDIR), "archive directory has a special-file type")
            require(entry.file_size == 0, "archive directory has unexpected content")
    return files


def check_member_content(archive: zipfile.ZipFile, members: list[zipfile.ZipInfo]) -> dict[str, int]:
    scanned = 0
    for member in members:
        relative = relative_member_name(member.filename)
        if Path(relative).suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = archive.read(member)
        scanned += 1
        require(not portable_home_path(content), f"portable user-home path in {relative}")
        require(not credential_like_material(content), f"credential-like material in {relative}")
    return {"text_members_scanned": scanned}


def verify_archive_hygiene(archive_path: Path) -> dict[str, int]:
    require(archive_path.is_file(), "archive does not exist")
    require(archive_path.suffix.lower() == ".zip", "public verifier accepts ZIP archives")
    with zipfile.ZipFile(archive_path) as archive:
        members = checked_file_members(archive)
        result = check_archive_members(members)
        result.update(check_member_content(archive, members))
        return result


def extract_verified_archive(archive_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        members = checked_file_members(archive)
        root_name = PurePosixPath(members[0].filename).parts[0]
        for member in members:
            target = destination / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    root = destination / root_name
    require(root.is_dir(), "archive package root is missing after extraction")
    return root


def run_static_validation(root: Path) -> dict[str, object]:
    trusted = Path(__file__).resolve().parents[1]
    require((root / "checksums.json").read_bytes() == (trusted / "checksums.json").read_bytes(), "archive differs from this reference package")
    validator = trusted / "analysis" / "verify_static_package.py"
    require(validator.is_file(), "static scientific validator is missing")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-I", str(validator), "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    require(result.stdout.strip(), "static scientific validator produced no output")
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as error:
        raise VerificationFailure("static scientific validator returned invalid JSON") from error
    require(result.returncode == 0, "static scientific validation failed")
    require(report.get("PACKAGE_VALIDATION") == "PASS", "static scientific validation did not pass")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    archive_path = args.archive.resolve()
    try:
        hygiene = verify_archive_hygiene(archive_path)
        with tempfile.TemporaryDirectory(prefix="bmg-public-verification-") as temporary:
            root = extract_verified_archive(archive_path, Path(temporary))
            scientific = run_static_validation(root)
        print(json.dumps({"status": "PASS", "archive": hygiene, "scientific": scientific}, sort_keys=True))
    except (OSError, ValueError, zipfile.BadZipFile, VerificationFailure) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
