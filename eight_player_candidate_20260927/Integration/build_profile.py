"""Read-only, fail-closed disk identity gate for the saved HD2 offline candidate.

No process APIs, installation discovery, native execution, writes, or network
access are used. The caller explicitly supplies both roots and every game/data
file. Matching disk bytes is not proof of loaded code, permissions, integration
readiness, or multiplayer success. This revision can never authorize live use.

Trust is pinned in this source, not learned from observed files or the profile
JSON. Adding a trusted fingerprint requires a reviewed source/profile change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

SCHEMA_VERSION = 1
PROFILE_ID = "hd2-steam-25480438-offline-v014"
TRUSTED_MANIFEST_SHA256 = "b6a7e821233ddf5cceea2675a3f37d267c4d3dff28bfc9303849e38dce94f9fe"
TRUSTED_FINGERPRINTS: dict[str, str | None] = {
    "exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
    "playfab_multiplayer": None,
    "party": None,
    "data_typelib": None,
    "data_entities": None,
}
FILE_LABELS = {
    "exe": "helldivers2.exe",
    "game_dll": "game.dll",
    "playfab_multiplayer": "PlayFabMultiplayerWin.dll",
    "party": "PartyWin.dll",
    "data_typelib": "dl_library.dl_typelib",
    "data_entities": "generated_entities.dl_bin",
}
HEX256 = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", re.I)


class GateError(ValueError):
    """A supplied document, path, or file failed closed."""


def _json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GateError("duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_json(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_json_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("invalid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise GateError("JSON root must be an object")
    return value


def _reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _root(root: Path) -> Path:
    root = Path(root).absolute()
    if _reparse(root):
        raise GateError("root is a symlink or reparse point")
    if not root.is_dir():
        raise GateError("explicit root must be an existing directory")
    return root.resolve(strict=True)


def checked_path(root: Path, relative: str) -> Path:
    """Reject lexical escapes, ADS/device names, symlinks and junctions."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise GateError("file path must be a non-empty forward-slash relative path")
    if "\x00" in relative or PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
        raise GateError("absolute or invalid file path")
    parts = relative.split("/")
    if any(p in ("", ".", "..") or p[-1:] in (".", " ") or WINDOWS_RESERVED.match(p)
           or any(ord(c) < 32 or c in '<>\"|?*' for c in p) for p in parts):
        raise GateError("unsafe path component")
    boundary = _root(root)
    candidate = boundary
    for part in parts:
        candidate = candidate / part
        if _reparse(candidate):
            raise GateError("symlink or reparse point in supplied path")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(boundary):
        raise GateError("path escapes explicit root")
    if not resolved.is_file():
        raise GateError("supplied path is not a regular file")
    return resolved


def read_file(root: Path, relative: str, *, keep_bytes: bool = False) -> tuple[str, int, bytes | None]:
    """Hash one explicitly named file; detect observable replacement/change."""
    path = checked_path(root, relative)
    hasher = hashlib.sha256()
    chunks = [] if keep_bytes else None
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise GateError("supplied path is not a regular file")
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            hasher.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
        after = os.fstat(stream.fileno())
    same_path = checked_path(root, relative)
    final = same_path.stat()
    def stamp(info: os.stat_result) -> tuple:
        # Windows st_ctime is creation time for a path stat but metadata change
        # time for a file descriptor, so it cannot be compared across APIs.
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if same_path != path or stamp(before) != stamp(after) or stamp(after) != stamp(final) or size != after.st_size:
        raise GateError("file changed while being read")
    return hasher.hexdigest(), size, b"".join(chunks) if chunks is not None else None


def template() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": PROFILE_ID,
        "metadata": {"steam_build": 25480438, "exe_version": "1.8.46015.0",
                     "candidate_version": "0.14.0-offline", "metadata_is_identity_proof": False},
        "required_fingerprints": {
            role: {"label": FILE_LABELS[role], "sha256": digest,
                   "trust_status": "pinned_saved_evidence" if digest else "unresolved"}
            for role, digest in TRUSTED_FINGERPRINTS.items()
        },
        "manifest_sha256": TRUSTED_MANIFEST_SHA256,
        "live_ready": False,
        "trust_note": "Observed hashes never update trusted fingerprints. Version labels are metadata only.",
    }


def validate_profile(profile: dict) -> None:
    if profile.get("schema_version") != SCHEMA_VERSION or type(profile.get("schema_version")) is not int:
        raise GateError("unsupported profile schema")
    if profile.get("profile_id") != PROFILE_ID:
        raise GateError("unsupported profile identity")
    if profile.get("manifest_sha256") != TRUSTED_MANIFEST_SHA256:
        raise GateError("profile cannot replace the pinned manifest fingerprint")
    if profile.get("live_ready") is not False:
        raise GateError("profile cannot assert live readiness")
    records = profile.get("required_fingerprints")
    if not isinstance(records, dict) or set(records) != set(TRUSTED_FINGERPRINTS):
        raise GateError("all required fingerprint roles must be present exactly once")
    for role, expected in TRUSTED_FINGERPRINTS.items():
        record = records[role]
        if not isinstance(record, dict) or record.get("sha256") != expected:
            raise GateError("profile cannot introduce or replace a trusted fingerprint: " + role)
        status = "pinned_saved_evidence" if expected else "unresolved"
        if record.get("trust_status") != status:
            raise GateError("invalid fingerprint trust status: " + role)
    metadata = profile.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("metadata_is_identity_proof") is not False:
        raise GateError("version metadata cannot establish file identity")


def verify_manifest(package_root: Path, manifest_relative: str) -> dict:
    """Verify pinned manifest and every source digest it declares, no imports."""
    result: dict[str, Any] = {"verified": False, "manifest_sha256": None, "files": [], "errors": []}
    try:
        digest, _, raw = read_file(package_root, manifest_relative, keep_bytes=True)
        result["manifest_sha256"] = digest
        if digest != TRUSTED_MANIFEST_SHA256:
            raise GateError("candidate manifest fingerprint mismatch; its file list is not trusted")
        manifest = parse_json(raw or b"")
        target = manifest.get("target_profile", {})
        if target.get("exe_sha256") != TRUSTED_FINGERPRINTS["exe"] or target.get("game_dll_sha256") != TRUSTED_FINGERPRINTS["game_dll"]:
            raise GateError("candidate manifest target fingerprints disagree with pinned profile")
        entries = manifest.get("source_sha256")
        if not isinstance(entries, dict) or not entries:
            raise GateError("manifest has no source fingerprint list")
        seen = set()
        # Validate all spellings before any package source is read.
        for relative, expected in entries.items():
            if not isinstance(expected, str) or not HEX256.fullmatch(expected):
                raise GateError("invalid manifest source fingerprint")
            path = checked_path(package_root, relative)
            key = str(path).casefold()
            if key in seen:
                raise GateError("duplicate manifest path alias")
            seen.add(key)
        for relative, expected in entries.items():
            try:
                observed, size, _ = read_file(package_root, relative)
                matched = observed == expected
                result["files"].append({"path": relative, "expected_sha256": expected,
                                        "observed_sha256": observed, "size": size, "matched": matched})
                if not matched:
                    result["errors"].append("source fingerprint mismatch: " + relative)
            except (OSError, GateError) as exc:
                result["errors"].append(relative + ": " + str(exc))
        result["verified"] = not result["errors"]
        result["scope"] = "Pinned manifest and source_sha256 entries only; validation reports are not re-executed."
    except (OSError, GateError) as exc:
        result["errors"].append(str(exc))
    return result


def check(*, profile: dict, input_root: Path, supplied_files: dict[str, str],
          package_root: Path, manifest_relative: str) -> dict:
    """Return evidence only. This offline revision always denies live readiness."""
    result: dict[str, Any] = {
        "schema_version": 1, "profile_id": PROFILE_ID, "status": "blocked",
        "profile_valid": False, "package_integrity_verified": False,
        "required_fingerprints_verified": False, "pre_install_gate_passed": False,
        "live_ready": False, "installation_authorized": False, "multiplayer_verified": False,
        "process_accessed": False, "installation_discovery_performed": False,
        "files": [], "errors": [], "blockers": [],
        "evidence_scope": "Only explicitly supplied disk files at the time of reading; not loaded-image or runtime identity.",
    }
    try:
        validate_profile(profile)
        if not isinstance(supplied_files, dict) or any(role not in TRUSTED_FINGERPRINTS for role in supplied_files):
            raise GateError("unknown supplied file role")
        # The caller may provide no game files and still audit the package.
        _root(input_root)
        result["profile_valid"] = True
    except (OSError, GateError) as exc:
        result["errors"].append(str(exc))
        return result
    result["metadata"] = profile.get("metadata", {})
    result["manifest"] = verify_manifest(package_root, manifest_relative)
    result["package_integrity_verified"] = result["manifest"]["verified"]
    result["errors"].extend(result["manifest"]["errors"])
    seen = set()
    for role, expected in TRUSTED_FINGERPRINTS.items():
        row: dict[str, Any] = {"role": role, "label": FILE_LABELS[role], "expected_sha256": expected,
                              "trust_status": "pinned_saved_evidence" if expected else "unresolved",
                              "observed_sha256": None, "matched": False, "status": "not_supplied"}
        if expected is None:
            result["blockers"].append("unresolved_required_fingerprint:" + role)
        if role in supplied_files:
            relative = supplied_files[role]
            row["path"] = relative
            try:
                key = str(checked_path(input_root, relative)).casefold()
                if key in seen:
                    raise GateError("one file cannot satisfy multiple required roles")
                seen.add(key)
                observed, size, _ = read_file(input_root, relative)
                row.update(observed_sha256=observed, size=size)
                row["matched"] = expected is not None and observed == expected
                row["status"] = "observed_untrusted" if expected is None else "matched" if row["matched"] else "mismatch"
                if expected is not None and not row["matched"]:
                    result["errors"].append("required fingerprint mismatch: " + role)
            except (OSError, GateError) as exc:
                row["status"] = "rejected"
                row["error"] = str(exc)
                result["errors"].append(role + ": " + str(exc))
        else:
            result["blockers"].append("required_file_not_supplied:" + role)
        result["files"].append(row)
    result["required_fingerprints_verified"] = all(row["matched"] for row in result["files"])
    result["blockers"].extend([
        "offline_candidate_has_no_live_installer_or_complete_game_integration",
        "disk_fingerprints_do_not_prove_loaded_image_hooks_unwind_lifetime_or_authorization",
        "five_through_eight_account_mission_acceptance_not_verified",
    ])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--manifest", required=True, help="manifest path relative to package root")
    parser.add_argument("--profile", required=True, help="profile JSON path relative to package root")
    parser.add_argument("--input-root", type=Path, required=True, help="explicit root of user-supplied disk files")
    parser.add_argument("--file", action="append", default=[], metavar="ROLE=RELATIVE_PATH")
    args = parser.parse_args(argv)
    try:
        supplied = {}
        for item in args.file:
            role, separator, relative = item.partition("=")
            if not separator or role in supplied:
                raise GateError("each --file requires a unique ROLE=RELATIVE_PATH")
            supplied[role] = relative
        _, _, raw = read_file(args.package_root, args.profile, keep_bytes=True)
        result = check(profile=parse_json(raw or b""), input_root=args.input_root,
                       supplied_files=supplied, package_root=args.package_root,
                       manifest_relative=args.manifest)
    except (OSError, GateError) as exc:
        result = {"status": "blocked", "live_ready": False, "pre_install_gate_passed": False,
                  "process_accessed": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("pre_install_gate_passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
