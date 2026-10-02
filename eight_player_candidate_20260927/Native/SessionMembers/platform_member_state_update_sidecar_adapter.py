"""Offline, fail-closed adapter contract for the 0x10937a0 sidecar plan.

This is a plan validator and data model only.  It never writes game memory,
registers a hook, or claims that the native callback ABI is known.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


CAPACITY_SITES = frozenset({"0x1093c91", "0x1093c96", "0x1093cb0", "0x1093d1e"})
ALL_FOUR_SITES = frozenset(
    {
        "0x10939c2", "0x10939ce", "0x1093a96", "0x1093ada", "0x1093bcc",
        "0x1093c91", "0x1093c96", "0x1093cb0", "0x1093d1e", "0x1093d72",
        "0x1093fd3", "0x1094105", "0x10942ac", "0x1094338",
    }
)
REQUIRED_REDIRECTS = frozenset({"0x1093ca9", "0x1093cfe", "0x1093d17", "0x1093dba", "0x10943a4", "0x10943c9"})


@dataclass
class SidecarRecord:
    owner_key: int
    ids: list[int] = field(default_factory=list)
    generation: int = 0
    refcount: int = 1
    quiescing: bool = False

    def __post_init__(self) -> None:
        if self.owner_key <= 0:
            raise ValueError("owner_key must be a non-null native pointer")
        if len(self.ids) > 8:
            raise ValueError("sidecar accepts at most eight IDs")
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("duplicate member IDs are not allowed")
        if self.refcount < 1:
            raise ValueError("sidecar must start with an owner lease")

    @property
    def count(self) -> int:
        return len(self.ids)


def prepare_record(owner_key: int, ids: Iterable[int], generation: int = 0) -> SidecarRecord:
    """Create an offline record; reject malformed input before native use."""
    values = [int(v) for v in ids]
    if any(v < 0 or v > 0xFFFFFFFFFFFFFFFF for v in values):
        raise ValueError("member IDs must be uint64 values")
    return SidecarRecord(owner_key=owner_key, ids=values, generation=int(generation))


def validate_patch_plan(plan: dict) -> tuple[bool, list[str]]:
    """Return whether a proposed native patch is sufficiently described.

    No current plan should pass: real resolver/dispatcher and callback ABI are
    intentionally required.  The validator prevents accidental installation
    of a partial constant patch.
    """
    errors: list[str] = []
    if plan.get("entry_rva") != "0x10937a0":
        errors.append("entry_rva must be 0x10937a0")
    if plan.get("body_sha256") != "929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69":
        errors.append("captured body fingerprint is missing or changed")
    changed = set(plan.get("changed_immediate_sites", []))
    unknown = changed - ALL_FOUR_SITES
    if unknown:
        errors.append("changed_immediate_sites contains unknown site(s): " + ",".join(sorted(unknown)))
    unsafe_state = changed - CAPACITY_SITES
    if unsafe_state:
        errors.append("state/status/allocator literals cannot be changed: " + ",".join(sorted(unsafe_state)))
    if plan.get("target_count") not in (4, 8):
        errors.append("target_count must be 4 or 8")
    if plan.get("target_count") == 8:
        missing = REQUIRED_REDIRECTS - set(plan.get("redirected_sites", []))
        if missing:
            errors.append("eight-slot plan misses inline-buffer redirects: " + ",".join(sorted(missing)))
        if not plan.get("sidecar_owner_keyed"):
            errors.append("sidecar must be keyed by exact RCX owner subobject")
        if not plan.get("resolver_bound"):
            errors.append("resolver/dispatcher ABI is not bound to a live native symbol")
        if not plan.get("enumerator_abi_bound"):
            errors.append("primary and alternate enumerator ABI are not bound")
        if not plan.get("cleanup_abi_bound"):
            errors.append("owner release/cleanup ABI is not bound")
        if not plan.get("unwind_verified"):
            errors.append("exception/unwind and reentrancy behavior is not verified")
    if plan.get("installable") is True:
        errors.append("adapter cannot certify installability")
    return (not errors, errors)


def reject_partial_plan() -> list[str]:
    ok, errors = validate_patch_plan(
        {
            "entry_rva": "0x10937a0",
            "body_sha256": "929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69",
            "target_count": 8,
            "changed_immediate_sites": sorted(CAPACITY_SITES),
            "redirected_sites": [],
            "sidecar_owner_keyed": False,
            "resolver_bound": False,
            "enumerator_abi_bound": False,
            "cleanup_abi_bound": False,
            "unwind_verified": False,
            "installable": False,
        }
    )
    if ok:
        raise AssertionError("partial eight-slot plan unexpectedly accepted")
    return errors
