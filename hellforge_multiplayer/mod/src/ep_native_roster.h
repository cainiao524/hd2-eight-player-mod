#ifndef EP_NATIVE_ROSTER_H
#define EP_NATIVE_ROSTER_H
#include "ep_roster_api.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_NATIVE_ROSTER_CAPACITY 8u
#define EP_NATIVE_ROSTER_BYTES 0x680u
#define EP_NATIVE_ROSTER_READ_BUDGET 4096u
typedef struct EpNativeTicket {
    uint64_t peer, epoch;
    uint32_t player, network_index, generation, reserved;
} EpNativeTicket;
typedef struct EpNativeRosterView {
    uintptr_t game, roster, storage;
    uint64_t epoch;
    uint32_t build, ticket_count;
    void* lease;
    EpNativeTicket tickets[EP_NATIVE_ROSTER_CAPACITY];
} EpNativeRosterView;
/* begin must hold a lifetime AND mutation-exclusion lease across ALL reads.
 * A reference count alone is insufficient. Failure owns no lease. Callbacks
 * must not throw/reenter. No production callbacks are supplied by this module. */
typedef struct EpNativeRosterSource {
    void* context;
    int (*begin)(void*, uintptr_t game, EpNativeRosterView*);
    int (*read)(void*, void* lease, uintptr_t address, void* out, size_t bytes);
    void (*end)(void*, void* lease);
} EpNativeRosterSource;
typedef enum EpNativeRosterStatus {
    EP_NATIVE_OK, EP_NATIVE_ARGUMENT, EP_NATIVE_UNAVAILABLE, EP_NATIVE_LAYOUT,
    EP_NATIVE_READ_FAILED, EP_NATIVE_BINDING_CHANGED, EP_NATIVE_PENDING,
    EP_NATIVE_MAP_MISMATCH, EP_NATIVE_TICKET_MISMATCH
} EpNativeRosterStatus;
/* Consumes the actual four-array B layout emitted by legacy roster builders.
 * Reads are explicit and bounded; nothing is allocated, installed or written.
 * On failure output is zero and every successfully acquired lease is released. */
EpNativeRosterStatus ep_native_roster_snapshot(const EpNativeRosterSource*, uintptr_t game, EpHfRosterSnapshot*);
/* Signature matches EpHfRosterProvider.read. The source must outlive unbind.
 * Use capacity=8 when binding. This function is not registered by mod init. */
int ep_native_roster_read(void* source, uintptr_t game, EpHfRosterSnapshot*);
#ifdef __cplusplus
}
#endif
#endif
