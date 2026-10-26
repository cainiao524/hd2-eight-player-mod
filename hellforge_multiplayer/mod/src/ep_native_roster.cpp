/* C-compatible implementation also compiled into the real engine test TU. */
#include "ep_native_roster.h"
#include <string.h>
static uint32_t NativeU32(const void* p) { uint32_t v; memcpy(&v, p, 4); return v; }
static uint64_t NativeU64(const void* p) { uint64_t v; memcpy(&v, p, 8); return v; }
static int NativeRange(uintptr_t p, size_t n)
{ return p >= 0x10000 && p < ((uint64_t)1 << 47) && n <= ((uint64_t)1 << 47) - p; }
static int NativeOverlap(uintptr_t a, size_t na, uintptr_t b, size_t nb)
{ return a < b + nb && b < a + na; }
static int NativeRead(const EpNativeRosterSource* src, const EpNativeRosterView* view,
                      uintptr_t p, void* out, size_t n, size_t* used)
{
    if (!NativeRange(p, n) || n > EP_NATIVE_ROSTER_READ_BUDGET - *used) return 0;
    *used += n;
    return src->read(src->context, view->lease, p, out, n) == 1;
}
EpNativeRosterStatus ep_native_roster_snapshot(const EpNativeRosterSource* src, uintptr_t game, EpHfRosterSnapshot* out)
{
    EpNativeRosterView view = {0}; EpHfRosterSnapshot next = {0};
    uint8_t header[0xE8], storage[EP_NATIVE_ROSTER_BYTES], map[64];
    uintptr_t current = 0, user = 0, buckets = 0;
    uint64_t local = 0; size_t used = 0;
    uint32_t tracked, dense, prefix, empty, multiplier;
    EpNativeRosterStatus status = EP_NATIVE_LAYOUT;
    if (out) memset(out, 0, sizeof *out);
    if (!out || !src || !src->begin || !src->read || !src->end || !NativeRange(game, 0x347CEF8)) return EP_NATIVE_ARGUMENT;
    if (src->begin(src->context, game, &view) != 1) return EP_NATIVE_UNAVAILABLE;
    if (!view.lease || view.game != game || view.build != 25480438 || !view.epoch || view.ticket_count > 8 ||
        (view.roster & 7) || (view.storage & 15) || !NativeRange(view.roster, sizeof header) ||
        !NativeRange(view.storage, sizeof storage) || NativeOverlap(view.roster, sizeof header, view.storage, sizeof storage)) goto done;
    for (uint32_t i = 0; i < view.ticket_count; i++)
    {
        const EpNativeTicket* t = &view.tickets[i];
        status = EP_NATIVE_TICKET_MISMATCH;
        if (!t->peer || !t->player || t->epoch != view.epoch || !t->generation || t->network_index >= 8 || t->reserved) goto done;
        for (uint32_t j = 0; j < i; j++)
            if (view.tickets[j].peer == t->peer || view.tickets[j].player == t->player || view.tickets[j].network_index == t->network_index) goto done;
    }
    status = EP_NATIVE_READ_FAILED;
    if (!NativeRead(src, &view, game + 0x3326468, &current, 8, &used)) goto done;
    status = EP_NATIVE_BINDING_CHANGED; if (current != view.roster) goto done;
    status = EP_NATIVE_READ_FAILED;
    if (!NativeRead(src, &view, view.roster, header, sizeof header, &used)) goto done;
    tracked = NativeU32(header + 0x80); dense = NativeU32(header + 0x84); prefix = NativeU32(header + 0x88);
    status = EP_NATIVE_LAYOUT;
    if (tracked > 8 || dense > tracked || prefix > dense || NativeU32(header + 0xD8) != 8) goto done;
    status = EP_NATIVE_PENDING; if (tracked != dense) goto done; /* never advertise a partial roster as solo */
    buckets = (uintptr_t)NativeU64(header + 0xD0); empty = NativeU32(header + 0xDC); multiplier = NativeU32(header + 0xE0);
    status = EP_NATIVE_LAYOUT;
    if ((buckets & 7) || !NativeRange(buckets, sizeof map) ||
        (NativeOverlap(buckets, sizeof map, view.roster, sizeof header) && buckets != view.roster+0x90) || NativeOverlap(buckets, sizeof map, view.storage, sizeof storage)) goto done;
    status = EP_NATIVE_READ_FAILED;
    if (!NativeRead(src, &view, view.storage, storage, sizeof storage, &used) ||
        !(buckets==view.roster+0x90 ? (memcpy(map,header+0x90,sizeof map),1) : NativeRead(src, &view, buckets, map, sizeof map, &used)) ||
        !NativeRead(src, &view, game + 0x347CEF0, &user, 8, &used)) goto done;
    if (user && (!NativeRange(user, 0xB3A0) || !NativeRead(src, &view, user + 0xB398, &local, 8, &used))) goto done;
    next.size = sizeof next; next.version = EP_HF_ROSTER_VERSION; next.capacity = 8; next.epoch = view.epoch;
    for (uint32_t i = 0; i < dense; i++)
    {
        uintptr_t descriptor = (uintptr_t)NativeU64(storage + i * 8);
        uint32_t entity = 0, index = NativeU32(storage + 0x580 + i * 0x20 + 0xC);
        uint64_t peer = NativeU64(storage + 0x3C0 + i * 0x38);
        const EpNativeTicket* ticket = NULL;
        int found = 0;
        status = EP_NATIVE_LAYOUT;
        if (!NativeRange(descriptor, 12) || NativeOverlap(descriptor, 12, view.roster, sizeof header) ||
            NativeOverlap(descriptor, 12, view.storage, sizeof storage) || NativeOverlap(descriptor, 12, buckets, sizeof map)) goto done;
        status = EP_NATIVE_READ_FAILED;
        if (!NativeRead(src, &view, descriptor + 8, &entity, 4, &used)) goto done;
        status = EP_NATIVE_MAP_MISMATCH;
        if (!entity || entity == empty) goto done;
        for (uint32_t probe = 0; probe < 8; probe++)
        {
            uint32_t bucket = (entity * multiplier + probe) % 8;
            uint32_t key = NativeU32(map + bucket * 8);
            if (key == empty) break;
            if (key == entity) { found = NativeU32(map + bucket * 8 + 4) == i; break; }
        }
        if (!found) goto done;
        status = EP_NATIVE_TICKET_MISMATCH;
        for (uint32_t t = 0; t < view.ticket_count; t++)
            if (view.tickets[t].peer == peer && view.tickets[t].player == entity && view.tickets[t].network_index == index) ticket = &view.tickets[t];
        if (!ticket) goto done;
        for (uint32_t j = 0; j < i; j++) if (next.players[j].peer == peer || next.players[j].network_index == index) goto done;
        EpHfPlayer* p = &next.players[next.count++];
        p->peer = peer; p->player = entity; p->life = NativeU32(storage + 0x3C0 + i * 0x38 + 0x18);
        p->local = peer == local; p->network_index = index; p->generation = ticket->generation;
        p->network_id = NativeU32(storage + 0x580 + i * 0x20); /* avatar entity network ID, not player index */
    }
    status = EP_NATIVE_READ_FAILED;
    if (!NativeRead(src, &view, game + 0x3326468, &current, 8, &used)) goto done;
    status = EP_NATIVE_BINDING_CHANGED; if (current != view.roster) goto done;
    *out = next; status = EP_NATIVE_OK;
done:
    src->end(src->context, view.lease);
    return status;
}
int ep_native_roster_read(void* source, uintptr_t game, EpHfRosterSnapshot* out)
{ return ep_native_roster_snapshot((const EpNativeRosterSource*)source, game, out) == EP_NATIVE_OK; }
