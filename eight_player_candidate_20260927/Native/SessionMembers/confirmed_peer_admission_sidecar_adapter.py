"""Fail-closed offline plan validator for host confirmed-peer admission."""
from __future__ import annotations

REQUIRED_SENDER_REDIRECTS = frozenset({"0x108c7eb", "0x108c81a", "0x108c8e7", "0x108c9bc"})
REQUIRED_EXTERNAL_PATHS = frozenset({"host_capacity_gate", "host_index_allocator", "client_confirmed_peer_insert", "departure_cleanup", "host_migration"})


def validate_admission_plan(plan: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if plan.get("entry_rva") != "0x108c760":
        errors.append("entry_rva must identify host_confirmed_peer_sender")
    if plan.get("body_sha256") != "633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d":
        errors.append("live sender body fingerprint missing or changed")
    if plan.get("target_count") != 8:
        errors.append("target_count must be 8 for this adapter")
    missing = REQUIRED_SENDER_REDIRECTS - set(plan.get("redirected_sender_sites", []))
    if missing:
        errors.append("sender four-slot sites are not all redirected: " + ",".join(sorted(missing)))
    missing_external = REQUIRED_EXTERNAL_PATHS - set(plan.get("verified_external_paths", []))
    if missing_external:
        errors.append("external admission/cleanup paths are not verified: " + ",".join(sorted(missing_external)))
    for key in ("owner_keyed_sidecar", "table_storage_8", "ordinal_map_8", "serializer_8", "receiver_8", "unwind_verified"):
        if not plan.get(key):
            errors.append(key + " is not proven")
    if plan.get("installable") is True:
        errors.append("adapter cannot certify installability")
    return (not errors, errors)


def reject_sender_only_patch() -> list[str]:
    ok, errors = validate_admission_plan({
        "entry_rva": "0x108c760",
        "body_sha256": "633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d",
        "target_count": 8,
        "redirected_sender_sites": sorted(REQUIRED_SENDER_REDIRECTS),
        "verified_external_paths": [],
        "owner_keyed_sidecar": False,
        "table_storage_8": False,
        "ordinal_map_8": False,
        "serializer_8": False,
        "receiver_8": False,
        "unwind_verified": False,
        "installable": False,
    })
    if ok:
        raise AssertionError("sender-only patch unexpectedly passed")
    return errors
