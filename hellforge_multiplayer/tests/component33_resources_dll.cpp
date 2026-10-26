#include "../mod/src/ep_component33_resources.h"
extern "C" {
__declspec(dllexport) uint32_t c33_resource_bytes(uint32_t c) { return ep_c33_resource_bytes(c); }
__declspec(dllexport) int c33_resource_migrate(const EpC33ResourceBinding* b,const EpC33ResourceSnapshot* s,void* p,uint32_t n) { return ep_c33_resource_migrate(b,s,p,n); }
__declspec(dllexport) int c33_resource_validate(const EpC33ResourceBinding* b,const void* p,uint32_t n) { return ep_c33_resource_validate(b,p,n); }
__declspec(dllexport) int c33_resource_reserve(const EpC33ResourceBinding* b,void* p,uint32_t n,const uint64_t* k,uint32_t c,void* w,uint32_t z) { return ep_c33_resource_reserve(b,p,n,k,c,w,z); }
__declspec(dllexport) int c33_resource_consumer(uint32_t k,const EpC33ConsumerAddresses* a,const EpC33ResourceBinding* b,EpComponent33Image* out) { return ep_c33_resource_consumer(k,a,b,out); }
__declspec(dllexport) int c33_resource_windows(uint64_t g,const EpC33ResourceBinding* b,uint64_t reset,EpC33ResourcePlan* out) { return ep_c33_resource_windows(g,b,reset,out); }
}
