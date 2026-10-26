#include "../mod/src/ep_component33_image.h"
extern "C" __declspec(dllexport) int component33_image_test_build(uint32_t kind,const EpComponent33Addresses* a,EpComponent33Image* image)
{ return ep_component33_image_build(kind,a,image); }
extern "C" __declspec(dllexport) int component33_owner_test_build(uint64_t game,uint64_t promote,EpComponent33OwnerPatch* patch)
{ return ep_component33_owner_patch_build(game,promote,patch); }
