#ifndef EP_CLIENT_UPDATE_H
#define EP_CLIENT_UPDATE_H
#include "ep_client_disconnect.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpClientUpdateImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset;
    uint8_t data[8192];
} EpClientUpdateImage;
/* Saved client update 1083150. Entire call MUST hold the same owner lease as
 * its two 1084FD0 calls, including both returned record's +18 consumers.
 * Inline reverse lookup uses the bound bank and preserves the native owner.
 * Host+100 is still a FOUR-byte map: local index >=4 rejects before host+34
 * is changed, never writes beyond that map. This is an outstanding migration
 * prerequisite, not support for fifth-player host migration. Other native
 * lists/services are preserved. Late rejection requires quarantine, no replay.
 * Numeric generation/preparation only; does not discover or touch a game.
 */
EpPropertyResult ep_client_update_build(const EpClientDisconnectAddresses*,EpClientUpdateImage*);
EpPropertyResult ep_client_update_prepare(const HfApi*,HfMod*,const EpClientDisconnectAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
