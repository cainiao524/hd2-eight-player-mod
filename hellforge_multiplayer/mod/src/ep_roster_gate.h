#ifndef EP_ROSTER_GATE_H
#define EP_ROSTER_GATE_H
#include "ep_insert_image.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_ROSTER_ENTRIES 18u
#define EP_ROSTER_GATED_MAX 4096u
typedef enum EpRosterEntry {
    EP_ROSTER_SEND=1,EP_ROSTER_RECEIVE,EP_ROSTER_GETTER,EP_ROSTER_MOVER,
    EP_ROSTER_DENSE_LEGACY,EP_ROSTER_APPEND_LEGACY,EP_ROSTER_APPEND_REGISTERED,EP_ROSTER_DENSE_REGISTERED,
    EP_ROSTER_REMOVE_LEGACY,EP_ROSTER_REMOVE_REGISTERED,EP_ROSTER_ENTER,EP_ROSTER_LEAVE,
    EP_ROSTER_REGISTRY_UPDATE,EP_ROSTER_ASSOCIATION,EP_ROSTER_DEPARTURE,EP_ROSTER_ENTITY_REMOVE,
    EP_ROSTER_STATE_UPDATE,EP_ROSTER_PLAYER_JOIN
} EpRosterEntry;
typedef struct EpRosterGateLayout { uint32_t original_rva,original_bytes,image_bytes,function_count; } EpRosterGateLayout;
typedef struct EpRosterGateImage {
    uint32_t bytes,table_offset,function_count;
    uint8_t data[EP_ROSTER_GATED_MAX];
} EpRosterGateImage;
/* Same 32-byte switch ABI as property gates. move_code_address identifies the
 * prepared mover BODY (+32), never the independently switchable mover gate.
 * For REGISTRY_UPDATE this field instead identifies the group's ASSOCIATION
 * BODY (+32). The association ID is not the network-index getter result.
 * For DEPARTURE it identifies the same group's network-index getter BODY.
 * ENTITY_REMOVE scopes the original dispatcher; both routes follow the live
 * SDK next-pointer slot. Its body does not clone or replace that dispatcher.
 * All addresses numeric; no game discovery, access or installation. */
int ep_roster_gate_layout(uint32_t,EpRosterGateLayout*);
EpPropertyResult ep_roster_gate_build(uint32_t,const EpInsertAddresses*,uint64_t control,uint64_t next,EpRosterGateImage*);
#ifdef __cplusplus
}
#endif
#endif
