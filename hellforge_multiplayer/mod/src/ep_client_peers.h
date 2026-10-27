#ifndef EP_CLIENT_PEERS_H
#define EP_CLIENT_PEERS_H
#include "ep_client_disconnect.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_CLIENT_PEER_INSERT=1, EP_CLIENT_PEER_REGISTERED_INSERT=2,
       EP_CLIENT_PEER_REMOVE=3, EP_CLIENT_PEER_RESET=4, EP_CLIENT_PEER_LOOKUP=5,
       EP_CLIENT_PEER_CONTAINS=6, EP_CLIENT_PEER_SET_FLAG=7, EP_CLIENT_PEER_FAMILY_COUNT=9 };
typedef struct EpClientPeerImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset,source_rva;
    uint8_t data[4096];
} EpClientPeerImage;
typedef struct EpClientPeerFamilyAddresses {
    uint64_t game,client,peers,reject,code[EP_CLIENT_PEER_FAMILY_COUNT];
    uint32_t capacity,reserved;
} EpClientPeerFamilyAddresses;
typedef struct EpClientPeerFamily {
    /* direct insert, registered insert, remove, reset, disconnect,
     * record lookup, contains, record +19 flag setter, whole client update.
     * This unreleased family layout now has nine code entries; rebuild callers. */
    EpSessionCodeInfo code[EP_CLIENT_PEER_FAMILY_COUNT];
} EpClientPeerFamily;
/* Saved 10872C0 / B90B20 / 1087540 / 1087010. Preserve the original ABI,
 * native duplicate handling, service ordering and complete 32-byte swap-remove.
 * Only confirmed peers use the shared bank; count stays client+C8. Bounds are
 * checked before every replaced lookup/copy/append. Duplicate peer at capacity
 * still follows the native duplicate branch; a new peer cannot append there.
 * Registered insertion checks the selected tag-EB client before dereference,
 * not RCX (which carries the host identity). Foreign selection rejects.
 *
 * Numeric generation/preparation only. No discovery, hooks or init activation.
 * All confirmed-peer readers and constructors must migrate to this same bank
 * before ANY path is exposed. The caller must retain/migrate the bank, preserve
 * client identity and exclude all writers/reentrancy throughout native calls.
 * Other inline lists, reset resource consumers, host/migration and UI still
 * require capacity adaptations. This family alone is NOT safe to activate or
 * evidence of playable fifth/eighth players. Rejection never returns; late
 * faults follow native effects and require quarantine, never blind replay.
 *
 * Leaf 1084FD0 returns the actual shared-bank record pointer or NULL; 1085010
 * returns the original boolean. 1085090 preserves the original host/bypass
 * predicate and sets only the matching record's +19 byte. No new meaning is
 * assigned to that opaque flag. All three check client before dereference and
 * bound the exact count used in their search. Returned pointers require the
 * common lifetime/exclusion lease through the caller's last access; compaction
 * can move a record. They do not cover other inlined engine/UI lookups.
 */
EpPropertyResult ep_client_peer_build(uint32_t kind,const EpClientDisconnectAddresses*,EpClientPeerImage*);
/* Prepares all nine functions, including disconnect and client update, against ONE bank/client/
 * capacity/reject contract. Never publishes. Failure cancels unexposed images;
 * if cancellation fails, CLEANUP returns every retained handle for retry.
 * Desired code bases may be zero (allocator chosen); rel32 validation remains.
 * No retained data allocation, four-peer migration or runtime switch is implied.
 */
EpPropertyResult ep_client_peer_family_prepare(const HfApi*,HfMod*,const EpClientPeerFamilyAddresses*,EpClientPeerFamily*);
int ep_client_peer_family_discard(HfMod*,EpClientPeerFamily*);
#ifdef __cplusplus
}
#endif
#endif
