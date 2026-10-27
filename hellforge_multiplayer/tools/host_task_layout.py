"""Read private task layout constants from the C/C++ contract (no game data)."""
import re
from generate_loadout_lifecycle import PROJECT
_source=(PROJECT/'mod/src/ep_host_task_layout.h').read_text(encoding='utf-8')
def _constant(name):
    match=re.search(r'^#define EP_HOST_'+name+r' (0x[0-9a-f]+)u$',_source,re.M)
    if not match:raise ValueError('Missing host task layout constant: '+name)
    return int(match.group(1),16)
TASK_STRIDE=_constant('TASK_STRIDE')
SECONDARY_COUNT=_constant('TASK_SECONDARY_COUNT')
SECONDARY_START=_constant('TASK_SECONDARY_START')
PENDING_STRIDE=_constant('PENDING_STRIDE')
PENDING_KEY=_constant('PENDING_KEY')
