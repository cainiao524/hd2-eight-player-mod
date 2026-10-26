#include "../mod/src/ep_component33_consumers.h"
extern "C" __declspec(dllexport) EpPropertyResult c33_consumer_build(uint32_t kind,const EpC33ConsumerAddresses* a,EpComponent33Image* out)
{ return ep_component33_consumer_build(kind,a,out); }
