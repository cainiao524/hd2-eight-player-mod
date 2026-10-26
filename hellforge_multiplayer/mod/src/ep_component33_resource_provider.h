#ifndef EP_COMPONENT33_RESOURCE_PROVIDER_H
#define EP_COMPONENT33_RESOURCE_PROVIDER_H
#include "ep_component33_resource_call.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_PROVIDER_READ_LIMIT=65536 };
enum { EP_C33_PROVIDER_OK,EP_C33_PROVIDER_ARGUMENT,EP_C33_PROVIDER_CODE,
       EP_C33_PROVIDER_READ,EP_C33_PROVIDER_BUDGET,EP_C33_PROVIDER_LAYOUT,
       EP_C33_PROVIDER_NO_ENTITY,EP_C33_PROVIDER_RESOLVE,EP_C33_PROVIDER_NO_PACKAGE,
       EP_C33_PROVIDER_OWNER };
typedef struct EpC33ResourceProviderOps {
    void* context;
    /* Read-only identity resolution: 1 supplies the engine object (which may
     * be zero), 0 unavailable. Handle 7fff resolves to zero without this call.
     * Must preserve the source's lifetime/exclusion lease and not reenter. */
    int (*resolve)(void*,uint32_t handle,uint64_t* object);
    int (*service)(void*,const EpC33ResourceScopeView*,uint32_t operation,uint64_t key);
} EpC33ResourceProviderOps;
typedef struct EpC33ResourceProviderResult {
    EpC33ResourceCallResult call;
    uint32_t source_status,read_bytes,resolve_calls,reserved;
} EpC33ResourceProviderResult;
/* Explicit opt-in SDK-backed provider for build 25480438. Reads the owned
 * eight-slot S/B selection, package table and threshold records under the
 * existing roster native scope, then uses the frozen executor. SDK read and
 * read_code return ZERO on success. Two complete saved getter bodies must
 * match the SDK's pre-hook code view before data reads. All SDK read requests
 * together, including failed requests, are capped at 64 KiB per call.
 *
 * Does not discover a module/process, install hooks or bind during mod init.
 * resolve/service remain explicit integrations: this API does not establish
 * their game ABI or claim all external writers are excluded. Their internal
 * accesses are NOT part of the SDK read counter. This is not a sampling tool
 * or authorization to run it against a game. Coherence of all source data,
 * resource effects and the original two-lookups-to-one replacement remain
 * the integrating caller's responsibility. Failure before execution leaves
 * resources/revision unchanged; callback faults retain owner quarantine.
 */
int ep_component33_resource_acquire_provider_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,uint64_t target_object,const EpC33ResourceProviderOps*,EpC33ResourceProviderResult*);
/* Standalone release selects a dense ordinal, not an object. Checks the whole
 * S/B identity map, then reads only the package (no resolver or thresholds).
 * deferred must be 0 or 1. resolve may be null; for deferred=1 service may also
 * be null. No existing entry/hook is installed by this explicit API. */
int ep_component33_resource_release_provider_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,uint32_t ordinal,uint32_t deferred,const EpC33ResourceProviderOps*,EpC33ResourceProviderResult*);
/* Explicit UPDATE drain gate: nonempty queue, saved tail matches, and the
 * u32 at *(game+346D530)+190C is zero. No entity/package/threshold lookup.
 * resolve may be null. No scheduling, entry replacement or RESET supplied. */
int ep_component33_resource_drain_provider_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,const EpC33ResourceProviderOps*,EpC33ResourceProviderResult*);
/* Explicit native Win64 adapters for the same providers. Unlike the callback
 * APIs above these INVOKE engine functions. The engine root at game+3326308,
 * resource table +10 (LOAD +2F0, DISPOSE +300), context table +38/+8 and
 * resolver table +40/+160 are read with the SDK under the exact owner scope.
 * Saved call-site bytes are checked and all needed targets frozen BEFORE
 * resource mutation. These reads share the provider's 64 KiB budget; target
 * function internals are not counted. Ordinal-based deferred release makes
 * no engine calls; DEFER by object still invokes the identity resolver.
 *
 * The Win64 argument mapping is derived from saved call sites, not verified
 * callee implementations: service(key,table), context(engine), then
 * resolve(context,handle). Service return values are ignored as in the source;
 * a normal return is NOT proof an asynchronous asset is ready. Engine API,
 * table and code lifetimes must remain stable through the entire call; the
 * caller must exclude all external writers and establish the resolver's
 * read-only semantics. SEH, reentry and nested faults quarantine the owner.
 * No hook, init registration, UPDATE scheduling or RESET is installed here.
 * This API is not a read-only sampler and is not permission to access a game.
 */
int ep_component33_resource_acquire_native_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,uint64_t target_object,EpC33ResourceProviderResult*);
int ep_component33_resource_release_native_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,uint32_t ordinal,uint32_t deferred,EpC33ResourceProviderResult*);
int ep_component33_resource_drain_native_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,EpC33ResourceProviderResult*);
/* DEFER (665940) selects by resolved object, not ordinal; it invokes only
 * context/resolver functions, then queues release without resource services
 * or threshold reads. Same scope, source guards and total SDK read budget. */
int ep_component33_resource_defer_native_call(const HfApi*,HfMod*,uint64_t storage,
    uint64_t owner,uint64_t target_object,EpC33ResourceProviderResult*);
#ifdef __cplusplus
}
#endif
#endif
