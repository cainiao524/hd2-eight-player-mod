#pragma once

#include <windows.h>

// Runtime probe data model for build 25480438.  This module does not discover,
// inject, patch, or call the game.  A reviewed external observer may pass a
// copied entry frame to ep_probe_record; the probe only records bounded data.
#define EP_PROBE_MAGIC 0x45505052u /* EPPR */
#define EP_PROBE_VERSION 1u
#define EP_PROBE_BUILD 25480438u
#define EP_PROBE_HOST_JOIN_RVA 0x108BC70u
#define EP_PROBE_RECORD_CAPACITY 32u
#define EP_PROBE_STACK_WORDS 16u

extern "C" {

typedef enum EP_PROBE_STATUS : UINT32 {
    EP_PROBE_OK = 0,
    EP_PROBE_INVALID_ARGUMENT = 1,
    EP_PROBE_NOT_ACTIVE = 2,
    EP_PROBE_FULL = 3,
    EP_PROBE_BUILD_MISMATCH = 4,
    EP_PROBE_SITE_MISMATCH = 5,
} EP_PROBE_STATUS;

// Values observed at host_join_root before its prologue.  The caller must copy
// stack words from a safe, bounded buffer; this API never dereferences rsp.
typedef struct EP_PROBE_ENTRY_FRAME {
    UINT64 rcx_host;
    UINT64 rdx_context;
    UINT64 r8_request_list;
    UINT64 r9_request_container;
    UINT64 rsp_entry;
    UINT64 rbp;
    UINT64 r12;
    UINT64 r13;
    UINT64 r14;
    UINT64 r15;
    UINT64 flags;
    UINT64 return_address;
    UINT64 stack_words[EP_PROBE_STACK_WORDS];
    UINT32 stack_word_count;
    UINT32 reserved;
} EP_PROBE_ENTRY_FRAME;

typedef struct EP_PROBE_RECORD {
    UINT32 magic;
    UINT16 version;
    UINT16 size;
    UINT32 sequence;
    UINT32 thread_id;
    UINT32 steam_build;
    UINT32 site_rva;
    UINT64 qpc;
    EP_PROBE_ENTRY_FRAME frame;
} EP_PROBE_RECORD;

typedef struct EP_PROBE_CONTEXT {
    UINT32 magic;
    UINT16 version;
    UINT16 record_size;
    UINT32 steam_build;
    UINT32 site_rva;
    volatile LONG active;
    volatile LONG next_sequence;
    volatile LONG record_count;
    volatile LONG write_lock;
    EP_PROBE_RECORD records[EP_PROBE_RECORD_CAPACITY];
} EP_PROBE_CONTEXT;

__declspec(dllexport) EP_PROBE_STATUS __cdecl ep_probe_init(
    EP_PROBE_CONTEXT* context, UINT32 steam_build, UINT32 site_rva);
__declspec(dllexport) EP_PROBE_STATUS __cdecl ep_probe_start(
    EP_PROBE_CONTEXT* context);
__declspec(dllexport) EP_PROBE_STATUS __cdecl ep_probe_stop(
    EP_PROBE_CONTEXT* context);
__declspec(dllexport) EP_PROBE_STATUS __cdecl ep_probe_record(
    EP_PROBE_CONTEXT* context, const EP_PROBE_ENTRY_FRAME* frame);
__declspec(dllexport) UINT32 __cdecl ep_probe_snapshot(
    const EP_PROBE_CONTEXT* context, EP_PROBE_RECORD* output,
    UINT32 output_capacity);
__declspec(dllexport) BOOL __cdecl ep_probe_validate_site(
    HMODULE module, const BYTE* expected, SIZE_T expected_size);
__declspec(dllexport) UINT32 __cdecl ep_probe_expected_build();
__declspec(dllexport) UINT32 __cdecl ep_probe_expected_rva();

}

