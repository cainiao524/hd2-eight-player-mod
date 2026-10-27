#include "ep_host_migration.h"
#include <limits.h>
#include <string.h>
struct EpHostMigrationFixup {uint32_t offset,next,key,kind,multiplier;int64_t add;};
#include "ep_host_migration_template.h"
EpPropertyResult ep_host_migration_build(const EpHostMigrationAddresses* input,EpHostMigrationImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostMigrationAddresses a={};if (input) a=*input;*out={};
    const auto& h=a.host;
    if (!input || h.reserved || h.capacity<4 || h.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (h.client<0x262c8) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{h.game,74727424,4096},{h.code,8192,16},{h.client-0x162c8,0x20100,8},
        {h.confirmed,32ull*h.capacity,16},{h.reject,1,1},{h.peers,56ull*h.capacity,16},
        {h.flags,h.capacity,8},{h.large,uint64_t(EP_HOST_TASK_STRIDE)*h.capacity,16},{h.pending,uint64_t(EP_HOST_PENDING_STRIDE)*h.capacity,16},
        {a.ids,8ull*h.capacity,8},{a.pairs,16ull*h.capacity,16},{a.history,16ull*h.capacity,16},{a.timers,16ull*h.capacity,16},
        {a.lookup,1,1},{a.remove_dispatch,1,1}};
    for (unsigned i=0;i<15;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t values[]={h.game,h.client-0x918,h.client-0x162c8,h.confirmed,h.peers,h.flags,h.large,h.pending,h.capacity,h.reject,
        a.ids,a.pairs,a.history,a.timers,a.lookup,a.remove_dispatch,h.code};
    EpHostMigrationImage image={};memcpy(image.data,ep_host_migration_template,sizeof(ep_host_migration_template));
    for (const auto& f:ep_host_migration_fixups) {
        int64_t value=(int64_t)(values[f.key]*f.multiplier)+f.add;
        if (!f.kind) {value-=(int64_t)(h.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_host_migration_template);image.table_offset=ep_host_migration_table;
    image.function_count=2;image.body_offset=ep_host_migration_body;*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_host_migration_prepare(const HfApi* api,HfMod* mod,const EpHostMigrationAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostMigrationAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpHostMigrationImage image={};
    if (!ep_session_code_reserve(api,mod,a.host.code,sizeof(ep_host_migration_template),&code)) return EP_PROPERTY_RESERVE;
    a.host.code=code.base;auto rc=ep_host_migration_build(&a,&image);
    if (rc==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) rc=EP_PROPERTY_SEAL;
    if (rc==EP_PROPERTY_OK && ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
