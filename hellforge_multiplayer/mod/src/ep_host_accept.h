#ifndef EP_HOST_ACCEPT_H
#define EP_HOST_ACCEPT_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_HOST_ACCEPT_ENTRY=0,EP_MEMBER_METADATA_RECEIVE_ENTRY=1,EP_MEMBER_METADATA_LOCAL_ENTRY=2};
typedef struct EpHostAcceptAddresses {
    EpHostLifecycleAddresses host;
    uint64_t metadata,remove_data,registered_insert;
} EpHostAcceptAddresses;
typedef struct EpHostAcceptImage {
    uint32_t bytes,table_offset,function_count,entry[3],handler_offset;
    uint8_t data[4096];
} EpHostAcceptImage;
/* Whole saved 108C760 acceptance, 1084F50 metadata receive and 1084E10 local
 * metadata refresh. Entry 0 retains the original host ABI; entries 1/2 take
 * the bound client in RCX. All three use the same owner, capacity and banks.
 * metadata replaces client+150's four 16-byte records (ID, two DWORD fields).
 * This names the layout only, not established gameplay meaning. Native 90/60
 * field limits, state predicates, blocked-mode deferral and RPC formats stay.
 * Peers in all slots receive reciprocal membership and metadata notifications.
 *
 * remove_data MUST bind the same-owner ep_host_removal entry 1;
 * registered_insert MUST bind EP_CLIENT_PEER_REGISTERED_INSERT against this
 * client's exact confirmed bank. Raw original four-slot helpers are forbidden.
 * Bind update.accept_peer to entry 0, retaining all helper images and banks.
 *
 * Numeric preparation only: no game reads, hooks, imports or activation.
 * Import/initialize all metadata records before exposing any of these entries.
 * Bind constructor/send to ep_client_metadata with this exact metadata bank;
 * retain its readiness helpers and storage for the whole client lifetime.
 * Other readiness readers/reset paths, packet decoding and coordinated
 * activation are separate prerequisites before exposure.
 * Hold one exclusive owner lease for whole calls and helper lifetimes. Reject
 * is nonreturning; late effects require quarantine, never partial replay.
 */
EpPropertyResult ep_host_accept_build(const EpHostAcceptAddresses*,EpHostAcceptImage*);
EpPropertyResult ep_host_accept_prepare(const HfApi*,HfMod*,const EpHostAcceptAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
