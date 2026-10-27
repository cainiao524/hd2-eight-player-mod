#ifndef EP_LOADOUT_RESOURCE_ACTIONS_H
#define EP_LOADOUT_RESOURCE_ACTIONS_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_ACTIONS_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceActionsAddresses;
typedef struct EpLoadoutResourceActionsImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t activate,reset,complete;
    uint8_t data[EP_LOADOUT_RESOURCE_ACTIONS_BYTES];
} EpLoadoutResourceActionsImage;
/* Saved 661CF0 explicit activation, 662400 reset, 11B61F0 conditional activation.
 * Activation takes EDX resource ordinal and reads the common 4Ch resource bank.
 * Reset takes RCX countdown manager, clears native actor flags, sets owned
 * resource phases to 1, and uses the common first roster descriptor.
 * Completion takes RCX native owned actor, resolves its related resource
 * object through the native service/hash, then reads the shared resource row.
 * Unknown owner/catalog identities return without indexing missing records;
 * a known row's resource ordinal is bounded by the common capacity.
 * Native completion catalog (game+3326D78), mode stack, countdown actor list
 * and notification rows keep their original layouts and counts. These are
 * not player indices. Caller retains their full backing, validates native
 * catalog hash ordinals against its allocation, and excludes mutation.
 * Caller also retains callback arguments, roster descriptors and services.
 * No physical pod creation, catalog expansion, hooks, transport or activation;
 * these code images do not prove runtime or multiplayer behavior. */
EpPropertyResult ep_loadout_resource_actions_build(const EpLoadoutResourceActionsAddresses*,EpLoadoutResourceActionsImage*);
EpPropertyResult ep_loadout_resource_actions_prepare(const HfApi*,HfMod*,const EpLoadoutResourceActionsAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
