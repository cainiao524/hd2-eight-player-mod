#include "ep_runtime_probe.h"

#include <cstdio>
#include <cstring>

namespace {

constexpr BYTE kExpectedPrologue[] = {
    0x40, 0x55, 0x53, 0x56, 0x41, 0x54,
    0x48, 0x8D, 0x6C, 0x24, 0xE9,
    0x48, 0x81, 0xEC, 0xC8, 0x00, 0x00, 0x00,
};

bool check(bool value, const char* label) {
    if (!value) std::printf("failed:%s\n", label);
    return value;
}

}

int main() {
    EP_PROBE_CONTEXT context{};
    if (!check(ep_probe_init(&context, EP_PROBE_BUILD, EP_PROBE_HOST_JOIN_RVA) == EP_PROBE_OK, "init")) return 1;
    if (!check(ep_probe_init(&context, EP_PROBE_BUILD - 1, EP_PROBE_HOST_JOIN_RVA) == EP_PROBE_BUILD_MISMATCH, "build_gate")) return 1;
    if (!check(ep_probe_init(&context, EP_PROBE_BUILD, EP_PROBE_HOST_JOIN_RVA + 1) == EP_PROBE_SITE_MISMATCH, "rva_gate")) return 1;
    if (!check(ep_probe_start(&context) == EP_PROBE_OK, "start")) return 1;

    EP_PROBE_ENTRY_FRAME frame{};
    frame.rcx_host = 0x11110000;
    frame.rdx_context = 0x22220000;
    frame.r8_request_list = 0x33330000;
    frame.r9_request_container = 0x44440000;
    frame.rsp_entry = 0x55550000;
    frame.return_address = 0x66660000;
    frame.stack_word_count = EP_PROBE_STACK_WORDS + 3;
    for (UINT32 i = 0; i < EP_PROBE_STACK_WORDS; ++i) frame.stack_words[i] = 0x1000 + i;
    if (!check(ep_probe_record(&context, &frame) == EP_PROBE_OK, "record")) return 1;

    EP_PROBE_RECORD records[EP_PROBE_RECORD_CAPACITY]{};
    if (!check(ep_probe_snapshot(&context, records, EP_PROBE_RECORD_CAPACITY) == 1, "snapshot_count")) return 1;
    if (!check(records[0].frame.rcx_host == frame.rcx_host, "rcx")) return 1;
    if (!check(records[0].frame.r9_request_container == frame.r9_request_container, "r9")) return 1;
    if (!check(records[0].frame.stack_word_count == EP_PROBE_STACK_WORDS, "stack_bound")) return 1;
    if (!check(records[0].sequence == 1 && records[0].site_rva == EP_PROBE_HOST_JOIN_RVA, "metadata")) return 1;

    for (UINT32 i = 1; i < EP_PROBE_RECORD_CAPACITY; ++i) {
        frame.rcx_host = 0x11110000 + i;
        if (!check(ep_probe_record(&context, &frame) == EP_PROBE_OK, "fill")) return 1;
    }
    if (!check(ep_probe_record(&context, &frame) == EP_PROBE_FULL, "full_gate")) return 1;
    if (!check(ep_probe_stop(&context) == EP_PROBE_OK, "stop")) return 1;
    if (!check(ep_probe_record(&context, &frame) == EP_PROBE_NOT_ACTIVE, "inactive_gate")) return 1;

    void* synthetic = VirtualAlloc(nullptr, 0x1100000, MEM_RESERVE | MEM_COMMIT,
                                   PAGE_READWRITE);
    if (!check(synthetic != nullptr, "synthetic_alloc")) return 1;
    auto* site = static_cast<BYTE*>(synthetic) + EP_PROBE_HOST_JOIN_RVA;
    std::memcpy(site, kExpectedPrologue, sizeof(kExpectedPrologue));
    if (!check(ep_probe_validate_site(static_cast<HMODULE>(synthetic), kExpectedPrologue,
                                      sizeof(kExpectedPrologue)) == TRUE, "site_match")) return 1;
    site[0] ^= 0x01;
    if (!check(ep_probe_validate_site(static_cast<HMODULE>(synthetic), kExpectedPrologue,
                                      sizeof(kExpectedPrologue)) == FALSE, "site_mismatch")) return 1;
    VirtualFree(synthetic, 0, MEM_RELEASE);
    std::printf("ep_runtime_probe_synthetic_passed\n");
    return 0;
}
