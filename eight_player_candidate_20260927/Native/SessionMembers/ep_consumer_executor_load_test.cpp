#include <windows.h>
#include <cstdio>

typedef unsigned (__cdecl *get_build_fn)();
int main() {
    HMODULE module = LoadLibraryW(L"ep_consumer_executor.dll");
    if (!module) return 10;
    const char* names[] = {"ep_consumer_install", "ep_consumer_remove", "ep_consumer_expected_build", "ep_consumer_code_size", "ep_consumer_stolen_size"};
    for (const char* name : names) if (!GetProcAddress(module, name)) { FreeLibrary(module); return 11; }
    auto build = reinterpret_cast<get_build_fn>(GetProcAddress(module, "ep_consumer_expected_build"));
    auto code = reinterpret_cast<get_build_fn>(GetProcAddress(module, "ep_consumer_code_size"));
    auto stolen = reinterpret_cast<get_build_fn>(GetProcAddress(module, "ep_consumer_stolen_size"));
    if (!build || !code || !stolen || build() != 25480438u || code() != 270u || stolen() != 14u) { FreeLibrary(module); return 12; }
    FreeLibrary(module);
    std::puts("ep_consumer_executor_dll_exports_passed");
    return 0;
}
