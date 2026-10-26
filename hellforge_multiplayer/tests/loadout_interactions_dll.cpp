#include "ep_loadout_interactions.h"
extern "C" __declspec(dllexport) int interaction_build(const EpLoadoutConsumerAddresses* a,EpLoadoutInteractionImage* b)
{return ep_loadout_interactions_build(a,b);}
