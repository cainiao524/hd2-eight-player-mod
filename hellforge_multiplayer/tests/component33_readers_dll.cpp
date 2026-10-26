#include "../mod/src/ep_component33_readers.h"
extern "C" __declspec(dllexport) EpPropertyResult component33_readers_test_build(const EpComponent33ReaderAddresses* a,EpComponent33ReaderPlan* p)
{ return ep_component33_readers_build(a,p); }
