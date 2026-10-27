#ifndef EP_HOST_MIGRATION_H
#define EP_HOST_MIGRATION_H
#include "ep_host_removal.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpHostMigrationAddresses {
    EpHostLifecycleAddresses host;
    uint64_t ids,pairs,history,timers,lookup,remove_dispatch;
} EpHostMigrationAddresses;
typedef struct EpHostMigrationImage {
    uint32_t bytes,table_offset,function_count,body_offset;
    uint8_t data[8192];
} EpHostMigrationImage;
/* Complete saved 1089720 migration body with its internal switch table.
 * Host records/flags/large records and confirmed peers use host's SAME banks.
 * Native client auxiliary lists also move: +18 IDs (count +10), +40 pairs
 * (count +38), +88 history (count +80), +190 timers (fixed capacity search).
 * Their strides are 8/16/16/16, respectively; counts remain in the client.
 * These names denote layouts, not established protocol or gameplay semantics.
 * The native local pair append, timer values and all record fields survive.
 * Native metadata/service/RPC behavior and four-byte payload widths remain.
 * No fixed-four lookup is used for host or auxiliary member storage here.
 * lookup/remove_dispatch MUST be retained same-owner relocated entry points,
 * never the original helpers or stubs. Their entire calls share the lease.
 *
 * Numeric stage ONLY. The other client auxiliary-list producers/readers, host
 * pending consumers, task payloads and UI still require migration. Import all
 * banks together and exclude writers across the whole call before activation;
 * this candidate does not authorize or implement activation by itself. Native
 * services/callbacks are dependencies, not proof of real host migration.
 * Late errors (no free slot/index, overflow, foreign owner) require nonreturning
 * rejection/quarantine; do not replay a partially applied migration.
 */
EpPropertyResult ep_host_migration_build(const EpHostMigrationAddresses*,EpHostMigrationImage*);
EpPropertyResult ep_host_migration_prepare(const HfApi*,HfMod*,const EpHostMigrationAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
