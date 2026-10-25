/* GPL-3.0-only. Private eight-player research extension, NOT an upstream SDK version.
 * Resolve hellforge_ep_roster_api_v1 from the patched loader and check magic/size/version.
 * Binding only redirects loader readers; it never expands the game's native storage. */
#ifndef EP_HF_ROSTER_H
#define EP_HF_ROSTER_H
#include <stdint.h>
#include <stddef.h>
#define EP_HF_ROSTER_MAGIC 0x45505231u
#define EP_HF_ROSTER_VERSION 1u
#define EP_HF_ROSTER_LIMIT 16u
#ifdef __cplusplus
extern "C" {
#endif
typedef struct HfMod HfMod;
typedef struct EpHfPlayer {
    uint64_t peer;
    uint32_t player, avatar, life, local;
    uint32_t network_index, generation;
    /* Avatar network entity ID is not the player's slot index. 0x7FFF: absent.
     * A provider normally supplies avatar directly and leaves network_id absent. */
    uint32_t network_id, reserved;
} EpHfPlayer;
typedef struct EpHfRosterSnapshot {
    uint32_t size, version, count, capacity;
    uint64_t binding; /* reserved: provider returns zero, loader fills its lease */
    uint64_t epoch; /* nonzero session/owner epoch; change it on replacement */
    EpHfPlayer players[EP_HF_ROSTER_LIMIT];
} EpHfRosterSnapshot;
typedef struct EpHfRosterProvider {
    uint32_t size, version, capacity, reserved;
    void* context;
    /* Called synchronously on either game or watch thread. Must be thread-safe.
     * Return 1 with a coherent owned snapshot; 0 means unavailable (NO fallback).
     * Do not reenter this API. Keep context/code alive until unbind returns. */
    int (*read)(void* context, uintptr_t game, EpHfRosterSnapshot* out);
} EpHfRosterProvider;
typedef struct EpHfRosterApi {
    uint32_t magic, size, version, limit;
    uint64_t (*bind)(HfMod* owner, const EpHfRosterProvider* provider);
    int (*unbind)(HfMod* owner, uint64_t lease);
} EpHfRosterApi;
typedef const EpHfRosterApi* (*EpHfGetRosterApi)(void);
#ifdef __cplusplus
}
#endif
#endif
