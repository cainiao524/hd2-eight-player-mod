"""Fail-closed completion audit for the eight-player objective.

This audit reads the repository's goal, handoff and state files and checks that
the evidence needed by the full A--E acceptance criteria exists.  It never
starts the game, opens a process handle, loads a DLL, patches bytes, contacts a
network service, or treats a synthetic test as multiplayer evidence.

The normal result for the current repository is ``status=incomplete``.  That
is intentional: the repository contains extensive offline/native candidates,
but no authoritative eight-account mission receipt yet.  A future live
acceptance receipt can be supplied with ``--acceptance-receipt``; it must have
been produced by the real acceptance verifier and must explicitly prove eight
distinct accounts and clients in one mission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BUILD = 25480438
EXE_VERSION = "1.8.46015.0"
GOAL = Path("github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md")
HANDOFF = Path("github_handoff_20260927/HANDOFF.zh-TW.md")
STATE = Path("github_handoff_20260927/STATE.json")
WORKLIST = Path("five_player_feasibility_20260927/IMPLEMENTATION_WORKLIST.zh-TW.md")
ACCEPTANCE_VERIFIER = Path(
    "eight_player_candidate_20260927/Integration/verify_multiplayer_acceptance.py"
)
PRESERVED_USER_AUDIT = Path(
    "five_player_feasibility_20260927/audit_native_loader_boundary_20261003.py"
)

REQUIRED_FILES = (GOAL, HANDOFF, STATE, WORKLIST, ACCEPTANCE_VERIFIER)

# These are the acceptance conditions stated in GOAL_OBJECTIVE.zh-TW.md.  A
# row is only marked proven when a real, non-synthetic eight-client receipt is
# supplied.  This keeps this audit from widening a narrow static test into a
# multiplayer claim.
ACCEPTANCE_ROWS = (
    ("A1", "八個獨立帳號加入同一隊伍"),
    ("A2", "房主與八個客戶端的身分及名單一致"),
    ("A3", "離隊、重新加入及重連維持索引與資料對應"),
    ("A4", "額外玩家不覆蓋既有玩家"),
    ("B1", "第 5--8 名各自建立有效角色"),
    ("B2", "所有客戶端看見並識別第 5--8 名角色"),
    ("B3", "每位玩家能控制自己的角色"),
    ("B4", "角色死亡、增援及移除生命週期完整"),
    ("C1", "位置、動作、傷害、死亡與增援一致"),
    ("C2", "敵人、目標、投射物及互動狀態一致"),
    ("C3", "沒有本機可見而其他客戶端遺漏的玩家"),
    ("D1", "進入、降落、遊玩、撤離與結算完成"),
    ("D2", "離隊及重連後任務可繼續"),
    ("D3", "房主轉移若涉及修改則已驗證"),
    ("D4", "任務進度與結算結果可核對"),
    ("E1", "八人負載沒有已知必現崩潰、越界或資料破壞"),
    ("E2", "支援 build、平台及連線組合已列明並實測"),
    ("E3", "可重現建置與安裝方式已核對"),
    ("E4", "移除、恢復及錯誤診斷已核對"),
    ("E5", "版本不匹配處理及未支援情境已核對"),
)


class AuditError(ValueError):
    """Raised for malformed evidence supplied to the audit."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot_read_json:{path}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"json_root_not_object:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _git_exists(repo_root: Path, *args: str) -> bool:
    """Return whether a git query succeeds, even when it prints no output."""
    try:
        subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _verify_state_manifest(repo_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    entries = state.get("files_sha256")
    if not isinstance(entries, dict):
        return {
            "declared_entries": 0,
            "missing": ["files_sha256"],
            "bad": [],
            "ok": False,
        }
    missing: list[str] = []
    bad: list[dict[str, str]] = []
    for name, expected in entries.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            bad.append({"path": str(name), "reason": "invalid_manifest_entry"})
            continue
        path = repo_root / Path(name)
        if not path.is_file():
            missing.append(name)
            continue
        actual = _sha256(path)
        if actual != expected:
            bad.append({"path": name, "expected": expected, "actual": actual})
    return {
        "declared_entries": len(entries),
        "missing": missing,
        "bad": bad,
        "ok": not missing and not bad,
    }


def _validate_acceptance_receipt(path: Path, repo_root: Path) -> dict[str, Any]:
    receipt = _read_json(path)
    required = {
        "schema": "hd2_eight_player_multiplayer_acceptance_v1",
        "status": "passed_live_multiplayer_acceptance",
        "steam_build": BUILD,
        "exe_version": EXE_VERSION,
        "account_count": 8,
        "client_count": 8,
        "network_indexes": list(range(8)),
        "multiplayer_verified": True,
        "synthetic": False,
    }
    mismatches = {
        key: {"expected": value, "actual": receipt.get(key)}
        for key, value in required.items()
        if receipt.get(key) != value
    }
    rows = receipt.get("rows")
    row_ok = isinstance(rows, list) and len(rows) == 8
    unique_accounts = (
        row_ok
        and len({str(row.get("account_id", "")) for row in rows}) == 8
        and all(row.get("account_id") for row in rows)
    )
    unique_clients = (
        row_ok
        and len({str(row.get("client_id", "")) for row in rows}) == 8
        and all(row.get("client_id") for row in rows)
    )
    row_indexes = [row.get("network_index") for row in rows] if row_ok else []
    row_index_ok = bool(
        row_ok
        and all(isinstance(index, int) and not isinstance(index, bool) for index in row_indexes)
        and sorted(row_indexes) == list(range(8))
    )
    mission_ok = bool(receipt.get("mission_id"))
    session_ok = bool(receipt.get("session_id"))
    # Require the receipt to be inside this repository, so a copied summary
    # cannot silently serve as external evidence.
    try:
        resolved = path.resolve()
        inside_repo = resolved.is_relative_to(repo_root.resolve())
    except AttributeError:  # pragma: no cover - Python < 3.9 compatibility
        inside_repo = str(path.resolve()).startswith(str(repo_root.resolve()))
    return {
        "path": path.as_posix(),
        "inside_repo": inside_repo,
        "field_mismatches": mismatches,
        "rows": len(rows) if isinstance(rows, list) else None,
        "unique_accounts": bool(unique_accounts),
        "unique_clients": bool(unique_clients),
        "row_indexes_exactly_0_to_7": bool(row_index_ok),
        "mission_id_present": mission_ok,
        "session_id_present": session_ok,
        "valid": (
            inside_repo
            and not mismatches
            and bool(row_ok and unique_accounts and unique_clients)
            and row_index_ok
            and mission_ok
            and session_ok
        ),
    }


def audit(repo_root: Path, acceptance_receipt: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    state_path = repo_root / STATE
    state = _read_json(state_path)
    required_files = {
        path.as_posix(): (repo_root / path).is_file() for path in REQUIRED_FILES
    }
    goal_path = repo_root / GOAL
    goal_hash = _sha256(goal_path) if goal_path.is_file() else None
    state_goal_hash = state.get("goal_objective_sha256")
    manifest = _verify_state_manifest(repo_root, state)

    flags = {
        name: state.get(name)
        for name in ("installable", "multiplayer_verified", "mod_installed", "game_process_accessed")
    }
    live_receipt = None
    if acceptance_receipt is not None:
        live_receipt = _validate_acceptance_receipt(acceptance_receipt, repo_root)

    state_live_claim = bool(state.get("multiplayer_verified") is True)
    live_proof = bool(live_receipt and live_receipt.get("valid"))
    # A state flag alone cannot prove completion.  A future receipt must also
    # be present and valid before the rows below can become proven.
    acceptance_proven = bool(state_live_claim and live_proof)
    rows = [
        {
            "id": row_id,
            "requirement": requirement,
            "proven": acceptance_proven,
            "evidence": (
                live_receipt.get("path") if acceptance_proven and live_receipt else None
            ),
        }
        for row_id, requirement in ACCEPTANCE_ROWS
    ]

    remaining = state.get("remaining_release_work")
    required_work_present = isinstance(remaining, list) and bool(remaining)
    refs = {
        "head": _git(repo_root, "rev-parse", "HEAD"),
        "latest_research_commit": state.get("latest_research_commit"),
        "latest_status_receipt_commit": state.get("latest_status_receipt_commit"),
        "latest_research_exists": bool(
            state.get("latest_research_commit")
            and _git_exists(
                repo_root,
                "cat-file",
                "-e",
                f"{state.get('latest_research_commit')}^{{commit}}",
            )
        ),
        "latest_status_receipt_exists": bool(
            state.get("latest_status_receipt_commit")
            and _git_exists(
                repo_root,
                "cat-file",
                "-e",
                f"{state.get('latest_status_receipt_commit')}^{{commit}}",
            )
        ),
    }

    untracked = _git(repo_root, "status", "--short") or ""
    user_audit_preserved = (repo_root / PRESERVED_USER_AUDIT).is_file()
    missing_proof = [row["id"] for row in rows if not row["proven"]]
    blockers = []
    if not acceptance_proven:
        blockers.append("no_authoritative_eight_client_live_acceptance_receipt")
    if flags.get("installable") is not True:
        blockers.append("installable_gate_false")
    if flags.get("multiplayer_verified") is not True:
        blockers.append("multiplayer_verified_gate_false")
    if required_work_present:
        blockers.append("state_remaining_release_work_nonempty")
    if not manifest["ok"]:
        blockers.append("state_manifest_mismatch")
    if not all(required_files.values()):
        blockers.append("required_objective_files_missing")
    return {
        "schema": "hd2_eight_player_completion_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not blockers else "incomplete",
        "authoritative_completion": not blockers,
        "build": BUILD,
        "exe_version": EXE_VERSION,
        "objective": {
            "goal_file": GOAL.as_posix(),
            "goal_sha256": goal_hash,
            "state_goal_sha256": state_goal_hash,
            "goal_hash_matches_state": bool(goal_hash and goal_hash == state_goal_hash),
        },
        "required_files": required_files,
        "state_flags": flags,
        "state_manifest": manifest,
        "acceptance_receipt": live_receipt,
        "acceptance": {
            "criteria_count": len(rows),
            "proven_count": sum(1 for row in rows if row["proven"]),
            "missing_proof": missing_proof,
            "criteria": rows,
        },
        "remaining_release_work": {
            "present": required_work_present,
            "count": len(remaining) if isinstance(remaining, list) else None,
        },
        "git": refs,
        "untracked_status": untracked.splitlines() if untracked else [],
        "preserved_user_audit_present": user_audit_preserved,
        "blockers": blockers,
        "next_actions": [
            "bind native admission, player creation, replication and cleanup callbacks to real HD2 ABI",
            "run the fifth-peer then six-, seven- and eight-account mission ladder",
            "record eight independent live client logs and run verify_multiplayer_acceptance.py",
            "set installable/multiplayer_verified only after the receipt and package gates pass",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--acceptance-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.repo_root, args.acceptance_receipt)
    except (AuditError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": output.as_posix()}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
