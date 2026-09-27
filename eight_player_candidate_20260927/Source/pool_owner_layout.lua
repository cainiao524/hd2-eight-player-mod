-- Enumerate known S owners from the pinned constructor/cleanup inventory.
-- Pure layout planning: no FFI, process reads, allocation, hooks or game calls.
-- A successful plan proves neither mapped storage nor migration of aliases.
return function(Preflight)
    assert(type(Preflight) == "table" and type(Preflight.target) == "function",
        "pool_preflight dependency required")
    local M, target = {}, Preflight.target()
    local PTR_END, MAX_OWNERS = 140737488355328, 4096
    local S_SIZE, RECORD, ORIGINAL = 0x78, 0x298, 0x80e18
    local PLAYER_S = {0x28, 0xa0, 0x118, 0x1a0, 0x218}
    local INVENTORY_SHA = "7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6"

    local function plain(t)
        return type(t) == "table" and getmetatable(t) == nil
    end
    local function uint(n, limit)
        return type(n) == "number" and n >= 0 and n <= limit and n == math.floor(n)
    end
    local function dense(t)
        if not plain(t) then return nil end
        local count, last = 0, 0
        for k in pairs(t) do
            if not uint(k,MAX_OWNERS) or k == 0 then return nil end
            count = count+1
            if k > last then last = k end
        end
        if count ~= last then return nil end
        return count
    end
    local function reject(code, field, index)
        return {status=code, field=field, index=index, executable=false}
    end
    local function version(v)
        if not plain(v) then return reject("invalid_input","version") end
        for k, value in pairs(target) do
            if v[k] ~= value then return reject("version_mismatch",k) end
        end
    end
    local function copy_version()
        return {build=target.build, exe_sha256=target.exe_sha256,
            game_dll_sha256=target.game_dll_sha256}
    end
    local function pointer(s)
        if type(s) ~= "string" or #s ~= 8 then return nil end
        local a,b,c,d,e,f,g,h = s:byte(1,8)
        local hi = e+f*256+g*65536+h*16777216
        if hi > 0x7fff then return nil end
        local n = hi*4294967296+a+b*256+c*65536+d*16777216
        if n == 0 or n % 8 ~= 0 then return nil end
        return n -- Exactly representable below 2^47 in LuaJIT's number type.
    end
    local function extent(first,size)
        return first and first+size <= PTR_END
    end
    local function address(n)
        local out = {}
        for i = 1,8 do
            out[i] = string.char(n % 256)
            n = math.floor(n/256)
        end
        return table.concat(out)
    end
    local function key(bytes)
        local out = {}
        for i = 8,1,-1 do out[#out+1] = string.format("%02x",bytes:byte(i)) end
        return table.concat(out)
    end
    local function overlaps(a,size,b,other_size)
        return a < b+other_size and b < a+size
    end

    -- config.player_records.base is the record start, not the A0 anchor.
    -- Count 4 at the original base is supported; count 8 requires separate
    -- storage outside the known protected ranges. Unknown D fields remain
    -- outside this finite range check and require a real allocation contract.
    function M.plan(config)
        if not plain(config) then return reject("invalid_input","config") end
        local err = version(config.version)
        if err then return err end
        if not plain(config.player_records) then return reject("invalid_input","player_records") end
        local count = config.player_records.count
        if count ~= 4 and count ~= 8 then return reject("unsupported_record_count","player_records.count") end
        local d, player = pointer(config.d_address), pointer(config.player_records.base)
        -- 8D6E4 is the end of the two known four-entry metadata tables,
        -- not a declaration of D's allocation size.
        if not extent(d,0x8d6e4) then return reject("unsupported_address","d_address") end
        if not extent(player,count*RECORD) then return reject("unsupported_address","player_records.base") end
        local original, relocated = d+ORIGINAL, player ~= d+ORIGINAL
        if not relocated and count ~= 4 then
            return reject("original_storage_requires_four_records","player_records")
        end

        local owners, ranges = {}, {}
        local function add(base,offset,group,ordinal,slot,kind)
            local first = base+offset
            local bytes = address(first)
            owners[#owners+1] = {address=bytes,key=key(bytes),size=S_SIZE,
                group=group,record_index=ordinal,member_index=slot,kind=kind}
            if kind ~= "player" then
                ranges[#ranges+1] = {first=first,size=S_SIZE,label=group..":"..ordinal..":"..slot}
            end
        end
        local function singleton(offset)
            add(d,offset,"singleton_"..string.format("%x",offset),0,0,"fixed")
        end
        local function family(offset,n,stride,members)
            local label = "array_"..string.format("%x",offset)
            for j = 0,n-1 do
                for k = 1,#members do
                    add(d,offset+j*stride+members[k],label,j,k-1,"fixed")
                end
            end
        end
        -- This order is deliberately the common constructor/cleanup visit
        -- sequence, not address order and not an active-count projection.
        singleton(0x80da0)
        for j = 0,count-1 do
            for k = 1,#PLAYER_S do
                add(player,j*RECORD+PLAYER_S[k],"player_records",j,k-1,"player")
            end
        end
        for _,off in ipairs({0x81888,0x81900,0x81988,0x81a00,0x81b10,0x81b88}) do singleton(off) end
        family(0x8b748,20,0x180,{0,0x78})
        singleton(0x8d550); singleton(0x8d5c8)
        family(0x81c98,64,0x180,{0,0x78})
        family(0x87da0,5,0x180,{0,0x78})
        singleton(0x88538); singleton(0x885b0)
        family(0x886c0,32,0x180,{0,0x78,0xf0})

        ranges[#ranges+1] = {first=d+0x36f8,size=0x20,label="pool_descriptor"}
        ranges[#ranges+1] = {first=d+0x3718,size=256*0x208,label="original_pool_nodes"}
        ranges[#ranges+1] = {first=d+0x23f18,size=256,label="original_pool_occupancy"}
        ranges[#ranges+1] = {first=original,size=4*RECORD,label="original_player_records"}
        ranges[#ranges+1] = {first=d+0x8d6c4,size=4*4,label="original_player_metadata_a"}
        ranges[#ranges+1] = {first=d+0x8d6d4,size=4*4,label="original_player_metadata_b"}
        for i = 1,#ranges do
            local r = ranges[i]
            if not (r.label == "original_player_records" and not relocated) and
                overlaps(player,count*RECORD,r.first,r.size) then
                return reject("region_overlap",r.label)
            end
        end
        local reserved, retired = {}, {}
        for i = 1,#ranges do
            local r = ranges[i]
            reserved[i] = {address=address(r.first),size=r.size,label=r.label}
        end
        if relocated then
            for j = 0,3 do
                for k = 1,#PLAYER_S do
                    local bytes = address(original+j*RECORD+PLAYER_S[k])
                    retired[#retired+1] = {address=bytes,key=key(bytes)}
                end
            end
        end
        return {status="known_owner_layout",executable=false,version=copy_version(),
            d_address=config.d_address,owners=owners,known_owner_count=#owners,
            fixed_owner_count=285,player_owner_count=count*5,
            player_records={count=count,base=config.player_records.base,stride=RECORD,
                size=count*RECORD,relocated=relocated},
            protected_known_ranges=reserved,retired_player_owners=retired,
            inventory_evidence_sha256=INVENTORY_SHA,
            scope="Known constructor/cleanup owners and finite protected ranges only; no mapped storage, whole D layout, resource lifetime or alias migration proof."}
    end

    -- Address coverage only. Owner bytes, actual P/N ownership, descriptors,
    -- templates, capture atomicity and provenance must be checked separately.
    -- In particular, call pool_snapshot.validate on the same packet next.
    function M.check_coverage(config,packet)
        local layout = M.plan(config)
        if layout.status ~= "known_owner_layout" then return layout end
        if not plain(packet) then return reject("invalid_input","packet") end
        local err = version(packet.version)
        if err then return err end
        if not pointer(packet.d_address) then return reject("unsupported_address","packet.d_address") end
        if packet.d_address ~= layout.d_address then return reject("d_address_mismatch","packet.d_address") end
        local n = dense(packet.owners)
        if not n then return reject("invalid_input","packet.owners") end
        local expected, retired, seen, extras = {}, {}, {}, {}
        for i = 1,#layout.owners do expected[layout.owners[i].key] = true end
        for i = 1,#layout.retired_player_owners do retired[layout.retired_player_owners[i].key] = true end
        local original = pointer(layout.d_address)+ORIGINAL
        local player = pointer(layout.player_records.base)
        for i = 1,n do
            local owner = packet.owners[i]
            if not plain(owner) then return reject("invalid_input","owner",i) end
            local first = pointer(owner.address)
            if not extent(first,S_SIZE) then return reject("unsupported_address","owner.address",i) end
            local canonical = key(owner.address)
            if seen[canonical] then return reject("duplicate_owner",canonical,i) end
            if retired[canonical] then return reject("retired_player_owner",canonical,i) end
            if layout.player_records.relocated and overlaps(first,S_SIZE,original,4*RECORD) then
                return reject("retired_player_storage_overlap",canonical,i)
            end
            -- Expected S objects intentionally sit inside the player records.
            -- Extra owners must not overlap the header, gaps, or tail either:
            -- those bytes are not among the S ranges checked by pool_snapshot.
            if not expected[canonical] and overlaps(first,S_SIZE,player,layout.player_records.size) then
                return reject("player_storage_overlap",canonical,i)
            end
            seen[canonical] = true
            if not expected[canonical] then extras[#extras+1] = canonical end
        end
        local missing = {}
        for i = 1,#layout.owners do
            local canonical = layout.owners[i].key
            if not seen[canonical] then missing[#missing+1] = canonical end
        end
        if #missing > 0 then
            local result = reject("missing_known_owner","packet.owners")
            result.missing_owner_count,result.missing_owner_keys = #missing,missing
            return result
        end
        return {status="known_owner_addresses_complete",executable=false,
            expected_owner_count=layout.known_owner_count,supplied_owner_count=n,
            extra_owner_count=#extras,extra_owner_keys=extras,
            bytes_validated=false,requires_snapshot_validation=true,
            scope="Addresses only; this does not establish owner bytes, unique node ownership, full pool coverage, capture atomicity or live origin."}
    end
    return M
end
