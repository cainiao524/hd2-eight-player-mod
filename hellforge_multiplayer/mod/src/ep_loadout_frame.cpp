#include "ep_loadout_frame.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutFrameFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_frame_template.h"
EpPropertyResult ep_loadout_frame_build(const EpLoadoutFrameAddresses* input,EpLoadoutFrameImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutFrameAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult result=ep_loadout_records_validate_span(input ? &a.records : nullptr,EP_LOADOUT_FRAME_BYTES);
    if (result!=EP_PROPERTY_OK) return result;
    const auto& b=a.records.common;const auto& l=b.lifecycle;const auto& s=a.records.source;
    const uint64_t entries[]={a.sync_records,a.update,a.lookup,a.open_mode};
    for (uint64_t entry:entries) {
        if (entry>=l.code && entry<l.code+EP_LOADOUT_FRAME_BYTES) return EP_PROPERTY_OVERLAP;
        EpLoadoutRecordsAddresses target=a.records;target.common.lifecycle.code=entry;
        result=ep_loadout_records_validate_span(&target,1);if (result!=EP_PROPERTY_OK) return result;
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
        b.forward_map,b.inverse_map,b.roster,b.roster_storage,s.manager,s.actors,s.equipment,s.status,
        a.sync_records,a.update,a.lookup,a.open_mode};
    EpLoadoutFrameImage image={};memcpy(image.data,ep_loadout_frame_template,sizeof(ep_loadout_frame_template));
    for (const auto& f:ep_loadout_frame_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        for (unsigned i=0;i<(f.kind==1 || f.kind==3 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_frame_template);image.code_bytes=ep_loadout_frame_code_bytes;
    image.unwind_offset=ep_loadout_frame_unwind_offset;image.table_offset=ep_loadout_frame_table_offset;
    image.handler_offset=ep_loadout_frame_handler_offset;image.frame=ep_loadout_frame_entries[0];
    image.local_update=ep_loadout_frame_entries[1];*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_frame_prepare(const HfApi* api,HfMod* mod,const EpLoadoutFrameAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutFrameAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutFrameImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.records.common.lifecycle.code,sizeof(ep_loadout_frame_template),&code)) return EP_PROPERTY_RESERVE;
    a.records.common.lifecycle.code=code.base;EpPropertyResult result=ep_loadout_frame_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.records.common.lifecycle.game+0x21044a0};
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_loadout_frame(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;result=EP_PROPERTY_SEAL;}
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
