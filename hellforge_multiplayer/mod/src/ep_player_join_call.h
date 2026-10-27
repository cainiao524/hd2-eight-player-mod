#ifndef EP_PLAYER_JOIN_CALL_H
#define EP_PLAYER_JOIN_CALL_H
#include "ep_roster_call.h"
#ifdef __cplusplus
extern "C" {
#endif
enum EpPlayerJoinStatus {
    EP_JOIN_OK,EP_JOIN_CAPACITY,EP_JOIN_RESOURCE,EP_JOIN_RECORD_BUSY,EP_JOIN_MAP_FULL,
    EP_JOIN_OWNER_FULL,EP_JOIN_CLEANED,EP_JOIN_BINDING,EP_JOIN_DUPLICATE,
    EP_JOIN_LAYOUT,EP_JOIN_READ_LIMIT,EP_JOIN_POSTCONDITION,EP_JOIN_FAULT
};
/* These are runtime integrations, never called at Mod init. The owned NEW
 * local-join scope installs the checked FDC140 replacement. Extra in-process
 * reads total <=64 KiB per attempt; engine function internals are excluded.
 * Stable engine/table lifetimes and exclusion of ALL external writers remain
 * caller obligations. No process/module discovery or new SDK hooks.
 *
 * Clean preflight rejection releases the newly allocated handle. A normally
 * completed native creation with ordinal 7FFF uses the original full remove
 * lifecycle, plus its otherwise-skipped owner8 sentinel-map cleanup. Only
 * checked restoration returns ordinary failure; exceptions, nested faults or
 * inconsistent identity quarantine the owner, never claim rollback.
 * Failed joins skip the original success/ready continuation. This is not
 * peer admission, retry scheduling, a UI error message or gameplay proof.
 * frame.padding reports EpPlayerJoinStatus; frame.reserved reports read bytes.
 */
uintptr_t ep_player_join_creation_entry(void);
int ep_player_join_invoke(EpRosterCallContext*,EpRosterCallFrame*,const EpNativeRosterView*,uintptr_t body);
#ifdef __cplusplus
}
#endif
#endif
