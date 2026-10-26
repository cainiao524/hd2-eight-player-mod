#include "ep_loadout_interactions.h"
extern "C" __declspec(dllexport) int interaction_build(const EpLoadoutInteractionAddresses* a,EpLoadoutInteractionImage* b)
{return ep_loadout_interactions_build(a,b);}
