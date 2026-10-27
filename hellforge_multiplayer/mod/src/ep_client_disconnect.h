#ifndef EP_CLIENT_DISCONNECT_H
#define EP_CLIENT_DISCONNECT_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpClientDisconnectAddresses {
    uint64_t game,code,client,peers,reject;
    uint32_t capacity,reserved;
} EpClientDisconnectAddresses;
typedef struct EpClientDisconnectImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset,lookup_offset;
    uint8_t data[4096];
} EpClientDisconnectImage;
/* Saved 10845B0 disconnect_client, original RCX/EDX/R8D arguments. Keeps
 * native reason/mode handling, transport services, resource reset, state and
 * rejoin-state notifications, conditional return-to-host flow and cookie.
 * Only confirmed-peer access (+D0, stride 32) moves to the retained peers bank.
 * Count remains client+C8. Per-peer callbacks follow count; clearing covers
 * capacity*32 (4..8), including unused slots. Inline +D0..14F and +150 stay
 * untouched by this clear. Foreign client/excess count is rejected before
 * native effects, and each later lookup also checks the capacity boundary.
 *
 * Numeric generation/preparation only; no discovery, hooks or Mod-init calls.
 * Caller MUST migrate all confirmed-peer producers/readers/reset paths to this
 * same bank and exclude all writers throughout the ENTIRE native disconnect.
 * Other client lists, host state, resource/history/UI consumers still require
 * their corresponding capacity adaptations. This alone is NOT an eight-peer
 * disconnect implementation or a recovery coordinator. Native parameters must
 * come from an established engine call site, not guessed reason/mode numbers.
 * reject must never return (raise into the owning fault boundary). Entry uses
 * a tail transfer; late rejection uses a call with the native frame intact.
 * Exceptions/late rejection may follow effects: quarantine, never blind retry.
 * Bank, client, policy and image must outlive all calls. A prepared image is
 * cancellable until exposed; publication/retention is the caller's obligation.
 */
EpPropertyResult ep_client_disconnect_build(const EpClientDisconnectAddresses*,EpClientDisconnectImage*);
EpPropertyResult ep_client_disconnect_prepare(const HfApi*,HfMod*,const EpClientDisconnectAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
