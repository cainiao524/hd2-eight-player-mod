"""Reference model for the fixed-build platform member consumer at 0x1093590.

The model follows the captured Windows x64 function without calling the game:
``RCX`` is the owner/platform state and the signed ``EAX`` result is either
``-1`` (the member set cannot be validated) or ``0/1`` (the mode predicate).
The sidecar form keeps the same predicate while moving the member IDs and
count out of the four-entry inline storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


MAX_PLAYERS = 8
INVALID_STATUS = -1


@dataclass(frozen=True)
class OwnerState:
    """Only fields observed by 0x1093590 and its sidecar adapter."""

    platform_object: int
    ready: bool  # owner + 0x1ba6


@dataclass(frozen=True)
class MemberSidecar:
    """Eight-slot replacement for owner + 0x1b58 and owner + 0x1bb0."""

    member_ids: tuple[int, ...]

    @property
    def count(self) -> int:
        return len(self.member_ids)


Lookup = Callable[[int, int], Optional[int]]
Validate = Callable[[int], int]


def mode_predicate(flag_nonzero: bool, mode_enum: int) -> bool:
    """Reproduce the initial ``sil`` predicate from the captured bytes.

    A nonzero byte at the first global makes the predicate true.  When that
    byte is zero, the second global's dword is mapped as observed at
    ``0x10935c2..0x10935f2``; none of its values maps to zero, so the result
    is false.  Keeping the mapping explicit prevents a guessed enum name from
    becoming part of the ABI.
    """

    if flag_nonzero:
        return True
    mapping = {0: 2, 1: 1, 2: 4, 3: 5, 4: 3}
    mapped = mapping.get(mode_enum, 5)
    return mapped == 0


def evaluate(
    owner: OwnerState,
    sidecar: MemberSidecar,
    *,
    local_id: int,
    flag_nonzero: bool,
    mode_enum: int,
    lookup: Lookup,
    validate: Validate,
) -> int:
    """Evaluate the captured function against an eight-slot sidecar.

    ``lookup(platform_object, member_id)`` models the captured indirect call
    through API ``+0xf8``/vtable ``+0x118``.  ``validate(token)`` models the
    fixed status helper at ``0x20bde78``; status zero is success.
    """

    mode_ok = mode_predicate(flag_nonzero, mode_enum)

    # The captured function returns the mode predicate when no platform object
    # exists.  A non-ready object reaches the explicit -1 path.
    if owner.platform_object == 0:
        return int(mode_ok)
    if not owner.ready:
        return INVALID_STATUS

    count = sidecar.count
    if count > MAX_PLAYERS:
        return INVALID_STATUS
    if count == 0:
        # r15d starts at one and is compared with the member count.
        return INVALID_STATUS

    all_ok = mode_ok
    # r15d starts at one.  It is incremented only for a non-local member whose
    # platform lookup returned a non-null token.  Exactly one local ID is
    # therefore required for count == successful_non_local + 1.
    successful_non_local_plus_one = 1
    for member_id in sidecar.member_ids:
        if member_id == local_id:
            continue
        token = lookup(owner.platform_object, member_id)
        if token is None:
            continue
        all_ok = all_ok and (validate(token) == 0)
        successful_non_local_plus_one += 1

    if successful_non_local_plus_one != count:
        return INVALID_STATUS
    return int(all_ok)


ABI = {
    "entry_rva": "0x1093590",
    "calling_convention": "Windows x64",
    "input": {"RCX": "owner/platform state"},
    "output": {"EAX": "signed status: -1 or 0/1"},
    "sidecar_input": {"member_ids": "uint64[0..7]", "count": "0..8"},
}

