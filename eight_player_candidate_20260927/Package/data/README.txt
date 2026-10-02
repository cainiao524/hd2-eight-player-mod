HD2 Eight Player Native Bridge staging marker

This data folder intentionally contains no gameplay patch. Bingus Shared Loader
and Arsenal can merge data archives and dispatch Lua modules, but they do not
replace native Session/Party/peer admission functions or allocate executable
trampolines. The native bridge payload is staged separately after the exact-build
and native-plan gate passes.
