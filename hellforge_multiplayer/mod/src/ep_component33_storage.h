#ifndef EP_COMPONENT33_STORAGE_H
#define EP_COMPONENT33_STORAGE_H
#include "ep_component33_family.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_SOURCE_BYTES=0x2b8, EP_C33_OLD_CAPACITY=4 };
typedef enum EpC33StorageResult {
    EP_C33_STORAGE_OK, EP_C33_STORAGE_ARGUMENT, EP_C33_STORAGE_POINTER,
    EP_C33_STORAGE_COUNTS, EP_C33_STORAGE_MAP, EP_C33_STORAGE_IDENTITY,
    EP_C33_STORAGE_FLAGS, EP_C33_STORAGE_STALE, EP_C33_STORAGE_RESERVE,
    EP_C33_STORAGE_FAMILY, EP_C33_STORAGE_CLEANUP, EP_C33_STORAGE_STATE,
    EP_C33_STORAGE_CONFLICT
} EpC33StorageResult;
typedef struct EpC33EntitySnapshot { uint64_t address;uint32_t id,flags; } EpC33EntitySnapshot;
typedef struct EpC33Snapshot {
    uint64_t component_address,global_component;
    uint32_t invalid_entity_id,entity_count;
    uint8_t component[EP_C33_SOURCE_BYTES];
    EpC33EntitySnapshot entities[EP_C33_OLD_CAPACITY];
} EpC33Snapshot;
typedef struct EpC33Migration { uint8_t data[EP_COMPONENT33_STORAGE_BYTES]; } EpC33Migration;
/* Copies caller-owned snapshots only. Never follows an entity/global pointer.
 * Validates 0<=P<=D<=T<=4, the eight-bucket map/bounded probe/bijection, active
 * pointer/ID pairs and dense prefix flags. The provider must acquire the raw
 * component and entity +8/+14 fields coherently under whole-call exclusion;
 * this checks consistency, not peer authentication or snapshot freshness.
 * Copy ALL four old slots (including inactive opaque fields) into B's four
 * arrays; zero new slots and alignment padding. Header/map stay in S. New zero
 * slots are storage only, not constructed game resources. Embedded resource
 * references remain shallow: no new resource, destructor or ownership clone.
 * Errors zero output. Neither source nor any address named in it is written. */
EpC33StorageResult ep_component33_migrate_snapshot(const EpC33Snapshot*,EpC33Migration*);

enum { EP_C33_STORAGE_PREPARING=1,EP_C33_STORAGE_PREPARED,EP_C33_STORAGE_CLEANUP_REQUIRED,EP_C33_STORAGE_RETAINED };
typedef struct EpC33StorageBindings {
    uint64_t game_base,reject_address;
    uintptr_t desired_storage,desired_code[EP_C33_FAMILY_IMAGES];
} EpC33StorageBindings;
typedef struct EpC33StorageInfo {
    uint64_t handle,storage_address;
    uint32_t state,storage_bytes,family_result;
    EpComponent33FamilyInfo family;
} EpC33StorageInfo;
/* Owns a real RW B allocation and its complete code family. Raw snapshot and
 * input values are copied; no live-source reader is supplied. Overlapping S
 * ownership is refused. Internal family/code handles are exclusive to this
 * owner; callers must not cancel, retain or publish them separately. */
EpC33StorageResult ep_component33_storage_prepare(const HfApi*,HfMod*,const EpC33StorageBindings*,const EpC33Snapshot*,EpC33StorageInfo*);
int ep_component33_storage_info(HfMod*,uint64_t,EpC33StorageInfo*);
int ep_component33_storage_cancel(HfMod*,uint64_t);
/* Compare the provider's fresh coherent snapshot and the owned B bytes to the
 * preparation snapshot before retaining the code family and B. Caller MUST
 * already exclude/drain ALL old/new calls and keep that scope through the
 * eventual coordinated publication. This API does not acquire such a scope,
 * install any target, transfer resource ownership, or activate a player.
 * Freshness mismatch is retryable; retention is permanent even if later
 * publication fails. Cleanup failure keeps B until code cleanup succeeds. */
EpC33StorageResult ep_component33_storage_retain(HfMod*,uint64_t,const EpC33Snapshot* current);
#ifdef __cplusplus
}
#endif
#endif
