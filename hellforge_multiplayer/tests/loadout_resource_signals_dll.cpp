#include "ep_loadout_resource_signals.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int resource_signals_build(const EpLoadoutResourceSignalsAddresses* a,EpLoadoutResourceSignalsImage* b)
{return ep_loadout_resource_signals_build(a,b);}
