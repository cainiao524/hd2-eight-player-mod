#include <windows.h>
#include <cstdio>

typedef unsigned (__cdecl *get_u32_fn)();
int main() {
    HMODULE module = LoadLibraryW(L"ep_midgate_executor.dll");
    if (!module) return 10;
    const char* names[] = {
        "ep_midgate_install", "ep_midgate_remove", "ep_midgate_expected_build",
        "ep_midgate_capacity_rva", "ep_midgate_allocator_rva",
        "ep_midgate_capacity_span", "ep_midgate_allocator_span",
        "ep_midgate_capacity_code_size", "ep_midgate_allocator_code_size"};
    for (const char* name : names) if (!GetProcAddress(module, name)) { FreeLibrary(module); return 11; }
    auto build = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_expected_build"));
    auto cap = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_capacity_rva"));
    auto alloc = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_allocator_rva"));
    auto cap_span = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_capacity_span"));
    auto alloc_span = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_allocator_span"));
    auto cap_code = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_capacity_code_size"));
    auto alloc_code = reinterpret_cast<get_u32_fn>(GetProcAddress(module, "ep_midgate_allocator_code_size"));
    if (!build || !cap || !alloc || !cap_span || !alloc_span || !cap_code || !alloc_code ||
        build() != 25480438u || cap() != 0x108C18Fu || alloc() != 0x108C3D8u ||
        cap_span() != 38u || alloc_span() != 15u || cap_code() != 77u || alloc_code() != 63u) {
        FreeLibrary(module); return 12;
    }
    FreeLibrary(module);
    std::puts("ep_midgate_executor_dll_exports_passed");
    return 0;
}
