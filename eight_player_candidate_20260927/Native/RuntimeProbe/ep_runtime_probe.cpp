#include "ep_runtime_probe.h"

#include <cstring>

namespace {

constexpr UINT32 kBuild = EP_PROBE_BUILD;
constexpr UINT32 kRva = EP_PROBE_HOST_JOIN_RVA;

bool readable(const void* address, SIZE_T size) {
    if (!address || size == 0) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT) return false;
    const DWORD p = mbi.Protect & 0xff;
    return p == PAGE_READONLY || p == PAGE_READWRITE ||
           p == PAGE_WRITECOPY || p == PAGE_EXECUTE_READ ||
           p == PAGE_EXECUTE_READWRITE || p == PAGE_EXECUTE_WRITECOPY;
}

void reset_records(EP_PROBE_CONTEXT* c) {
    std::memset(c->records, 0, sizeof(c->records));
    InterlockedExchange(&c->record_count, 0);
    InterlockedExchange(&c->next_sequence, 0);
}

bool lock(volatile LONG* value) {
    for (unsigned i = 0; i < 1000; ++i) {
        if (InterlockedCompareExchange(value, 1, 0) == 0) return true;
        YieldProcessor();
    }
    return false;
}

void unlock(volatile LONG* value) {
    InterlockedExchange(value, 0);
}

} // namespace

extern "C" __declspec(dllexport)
EP_PROBE_STATUS __cdecl ep_probe_init(EP_PROBE_CONTEXT* context,
                                      UINT32 steam_build, UINT32 site_rva) {
    if (!context) return EP_PROBE_INVALID_ARGUMENT;
    if (steam_build != kBuild) return EP_PROBE_BUILD_MISMATCH;
    if (site_rva != kRva) return EP_PROBE_SITE_MISMATCH;
    std::memset(context, 0, sizeof(*context));
    context->magic = EP_PROBE_MAGIC;
    context->version = EP_PROBE_VERSION;
    context->record_size = static_cast<UINT16>(sizeof(EP_PROBE_RECORD));
    context->steam_build = steam_build;
    context->site_rva = site_rva;
    return EP_PROBE_OK;
}

extern "C" __declspec(dllexport)
EP_PROBE_STATUS __cdecl ep_probe_start(EP_PROBE_CONTEXT* context) {
    if (!context || context->magic != EP_PROBE_MAGIC ||
        context->version != EP_PROBE_VERSION ||
        context->record_size != sizeof(EP_PROBE_RECORD) ||
        context->steam_build != kBuild || context->site_rva != kRva) {
        return EP_PROBE_INVALID_ARGUMENT;
    }
    if (InterlockedCompareExchange(&context->active, 1, 0) != 0) {
        return EP_PROBE_INVALID_ARGUMENT;
    }
    if (!lock(&context->write_lock)) {
        InterlockedExchange(&context->active, 0);
        return EP_PROBE_INVALID_ARGUMENT;
    }
    reset_records(context);
    unlock(&context->write_lock);
    return EP_PROBE_OK;
}

extern "C" __declspec(dllexport)
EP_PROBE_STATUS __cdecl ep_probe_stop(EP_PROBE_CONTEXT* context) {
    if (!context || context->magic != EP_PROBE_MAGIC ||
        context->version != EP_PROBE_VERSION) return EP_PROBE_INVALID_ARGUMENT;
    if (InterlockedCompareExchange(&context->active, 0, 1) != 1) {
        return EP_PROBE_NOT_ACTIVE;
    }
    return EP_PROBE_OK;
}

extern "C" __declspec(dllexport)
EP_PROBE_STATUS __cdecl ep_probe_record(EP_PROBE_CONTEXT* context,
                                        const EP_PROBE_ENTRY_FRAME* frame) {
    if (!context || !frame || context->magic != EP_PROBE_MAGIC ||
        context->version != EP_PROBE_VERSION || context->record_size != sizeof(EP_PROBE_RECORD) ||
        context->steam_build != kBuild || context->site_rva != kRva) {
        return EP_PROBE_INVALID_ARGUMENT;
    }
    if (InterlockedCompareExchange(&context->active, 1, 1) != 1) {
        return EP_PROBE_NOT_ACTIVE;
    }
    if (!lock(&context->write_lock)) return EP_PROBE_FULL;
    const LONG index = context->record_count;
    if (index < 0 || index >= static_cast<LONG>(EP_PROBE_RECORD_CAPACITY)) {
        unlock(&context->write_lock);
        return EP_PROBE_FULL;
    }
    EP_PROBE_RECORD& out = context->records[index];
    std::memset(&out, 0, sizeof(out));
    out.magic = EP_PROBE_MAGIC;
    out.version = EP_PROBE_VERSION;
    out.size = static_cast<UINT16>(sizeof(EP_PROBE_RECORD));
    out.sequence = static_cast<UINT32>(InterlockedIncrement(&context->next_sequence));
    out.thread_id = GetCurrentThreadId();
    out.steam_build = kBuild;
    out.site_rva = kRva;
    LARGE_INTEGER qpc{};
    QueryPerformanceCounter(&qpc);
    out.qpc = static_cast<UINT64>(qpc.QuadPart);
    out.frame = *frame;
    if (out.frame.stack_word_count > EP_PROBE_STACK_WORDS) {
        out.frame.stack_word_count = EP_PROBE_STACK_WORDS;
    }
    InterlockedIncrement(&context->record_count);
    unlock(&context->write_lock);
    return EP_PROBE_OK;
}

extern "C" __declspec(dllexport)
UINT32 __cdecl ep_probe_snapshot(const EP_PROBE_CONTEXT* context,
                                 EP_PROBE_RECORD* output,
                                 UINT32 output_capacity) {
    if (!context || !output || output_capacity == 0 ||
        context->magic != EP_PROBE_MAGIC || context->version != EP_PROBE_VERSION ||
        context->record_size != sizeof(EP_PROBE_RECORD)) return 0;
    auto* mutable_context = const_cast<EP_PROBE_CONTEXT*>(context);
    if (!lock(&mutable_context->write_lock)) return 0;
    LONG count = mutable_context->record_count;
    if (count < 0) count = 0;
    if (count > static_cast<LONG>(EP_PROBE_RECORD_CAPACITY)) count = EP_PROBE_RECORD_CAPACITY;
    const UINT32 copied = (static_cast<UINT32>(count) < output_capacity)
        ? static_cast<UINT32>(count) : output_capacity;
    std::memcpy(output, mutable_context->records,
                static_cast<SIZE_T>(copied) * sizeof(EP_PROBE_RECORD));
    unlock(&mutable_context->write_lock);
    return copied;
}

extern "C" __declspec(dllexport)
BOOL __cdecl ep_probe_validate_site(HMODULE module, const BYTE* expected,
                                    SIZE_T expected_size) {
    if (!module || !expected || expected_size == 0) return FALSE;
    const auto* base = reinterpret_cast<const BYTE*>(module);
    const BYTE* site = base + kRva;
    if (!readable(site, expected_size)) return FALSE;
    return std::memcmp(site, expected, expected_size) == 0 ? TRUE : FALSE;
}

extern "C" __declspec(dllexport)
UINT32 __cdecl ep_probe_expected_build() { return kBuild; }

extern "C" __declspec(dllexport)
UINT32 __cdecl ep_probe_expected_rva() { return kRva; }
