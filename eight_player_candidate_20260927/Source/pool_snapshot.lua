-- Validate copied bytes for the pinned D/P/S/template layout.
-- No reads, callbacks, FFI or writes to a process are performed here.
-- Construct with the reviewed pool_preflight module: factory(Preflight).
return function(Preflight)
    assert(type(Preflight) == "table" and type(Preflight.target) == "function"
        and type(Preflight.plan) == "function", "pool_preflight dependency required")
    local M = {}
    local MAX_CAPACITY, MAX_OWNERS = 4096, 4096 -- Candidate input budgets, not engine limits.
    local PTR_END = 140737488355328 -- Exclusive end of supported low canonical user addresses.
    local NODE, S_SIZE, TEMPLATE, ELEMENT = 0x208, 0x78, 0xa0e8, 0xd68
    local TEMPLATE_RVA, TEMPLATE_COUNT, POOL_OFFSET = 0x3492f20, 73, 0x36f8
    local zero_node = string.rep("\0", NODE)
    -- 142B990 clears each node then calls 1408FE0, which sets A8/AC to 1.0f.
    -- 1408F00 cleanup instead leaves the entire node zero. Other free states
    -- are outside this candidate's supported contract, not proven corruption.
    local initial_node = string.rep("\0", 0xa8) .. "\0\0\128\63\0\0\128\63"
        .. string.rep("\0", NODE-0xb0)
    local target = Preflight.target()

    local function plain(t)
        return type(t) == "table" and getmetatable(t) == nil
    end
    local function uint(n, maximum)
        return type(n) == "number" and n >= 0 and n <= maximum and n == math.floor(n)
    end
    local function dense(t, maximum)
        if not plain(t) then return nil end
        local count, last = 0, 0
        for k in pairs(t) do
            if not uint(k, maximum) or k == 0 then return nil end
            count = count + 1
            if k > last then last = k end
        end
        if count ~= last then return nil end
        return count
    end
    local function fail(code, field, index)
        return {status = code, field = field, index = index, executable = false}
    end
    local function u32(s, offset)
        local a,b,c,d = s:byte(offset+1, offset+4)
        return a + b*256 + c*65536 + d*16777216
    end
    local function pointer(s, offset)
        local lo, hi = u32(s, offset), u32(s, offset+4)
        if hi > 0x7fff or (hi == 0 and lo == 0) then return nil end
        return hi*4294967296 + lo -- Exact: supported pointers are below 2^47.
    end
    local function key(s, offset)
        local out = {}
        for i = offset+8, offset+1, -1 do out[#out+1] = string.format("%02x", s:byte(i)) end
        return table.concat(out)
    end
    local function extent(start, size, alignment)
        return start and start % alignment == 0 and start+size <= PTR_END
    end
    local function overlap(a, b)
        return a.first < b.last and b.first < a.last
    end

    function M.validate(packet)
        if not plain(packet) or not plain(packet.version) then return fail("invalid_input", "version") end
        for field, value in pairs(target) do
            if packet.version[field] ~= value then return fail("version_mismatch", field) end
        end
        if type(packet.d_address) ~= "string" or #packet.d_address ~= 8
            or type(packet.game_base) ~= "string" or #packet.game_base ~= 8 then
            return fail("invalid_input", "addresses")
        end
        local d, game = pointer(packet.d_address, 0), pointer(packet.game_base, 0)
        if not extent(d, POOL_OFFSET+0x20, 8) or not extent(game, TEMPLATE_RVA+TEMPLATE_COUNT*TEMPLATE, 8) then
            return fail("unsupported_address", "d_or_game")
        end
        local pool_address, template_base = d+POOL_OFFSET, game+TEMPLATE_RVA
        if type(packet.descriptor) ~= "string" or #packet.descriptor ~= 0x20 then
            return fail("invalid_length", "descriptor")
        end
        local descriptor = packet.descriptor
        local used, capacity, cursor = u32(descriptor,0x10), u32(descriptor,0x14), u32(descriptor,0x18)
        if capacity == 0 or capacity > MAX_CAPACITY then return fail("unsupported_capacity", "capacity") end
        if used > capacity then return fail("invalid_used", "used") end
        if cursor >= capacity then return fail("invalid_cursor", "cursor") end
        local nodes_address, bitmap_address = pointer(descriptor,0), pointer(descriptor,8)
        if not extent(nodes_address,capacity*NODE,8) or not extent(bitmap_address,capacity,1) then
            return fail("unsupported_address", "backing")
        end
        if type(packet.nodes) ~= "string" or #packet.nodes ~= capacity*NODE then
            return fail("invalid_length", "nodes")
        end
        if type(packet.occupancy) ~= "string" or #packet.occupancy ~= capacity then
            return fail("invalid_length", "occupancy")
        end
        local owner_count, template_count = dense(packet.owners,MAX_OWNERS), dense(packet.templates,TEMPLATE_COUNT)
        if not owner_count or not template_count then return fail("invalid_input", "owners_or_templates") end
        local counts, templates = {}, {}
        for i = 1, template_count do
            local t = packet.templates[i]
            if not plain(t) or not uint(t.id,TEMPLATE_COUNT-1) then return fail("invalid_input", "template", i) end
            if templates[t.id] then return fail("duplicate_template", "template", i) end
            if type(t.bytes) ~= "string" or #t.bytes ~= TEMPLATE then return fail("invalid_length", "template", i) end
            local n = u32(t.bytes,0xa0e0)
            if n > 12 or (t.id == 0 and n ~= 0) then return fail("unsupported_template_count", "template", i) end
            for ordinal = 0, n-1 do
                local typ, events = u32(t.bytes,ordinal*ELEMENT), u32(t.bytes,ordinal*ELEMENT+0xd64)
                if typ < 1 or typ > 4 then return fail("unsupported_node_type", "template", i) end
                if events > 10 then return fail("invalid_event_count", "template", i) end
            end
            counts[t.id], templates[t.id] = n, t.bytes
        end

        local regions = {
            {first=pool_address,last=pool_address+0x20,label="descriptor"},
            {first=nodes_address,last=nodes_address+capacity*NODE,label="nodes"},
            {first=bitmap_address,last=bitmap_address+capacity,label="occupancy"},
            {first=template_base,last=template_base+TEMPLATE_COUNT*TEMPLATE,label="templates"},
        }
        local owner_keys, supplied_owners = {}, {}
        for i = 1, owner_count do
            local s = packet.owners[i]
            if not plain(s) or type(s.address) ~= "string" or #s.address ~= 8
                or type(s.bytes) ~= "string" or #s.bytes ~= S_SIZE then
                return fail("invalid_length", "owner", i)
            end
            local address, canonical = pointer(s.address,0), key(s.address,0)
            if not extent(address,S_SIZE,8) then return fail("unsupported_address", "owner", i) end
            if owner_keys[canonical] then return fail("duplicate_owner", canonical, i) end
            owner_keys[canonical] = true
            regions[#regions+1] = {first=address,last=address+S_SIZE,label=canonical}
            supplied_owners[i] = {key=canonical,bytes=s.bytes}
        end
        table.sort(regions,function(a,b) return a.first < b.first end)
        for i = 2, #regions do
            if overlap(regions[i-1],regions[i]) then return fail("region_overlap",regions[i].label,i) end
        end

        local occupied, node_templates, node_ordinals = 0, {}, {}
        for slot = 0, capacity-1 do
            local flag, offset = packet.occupancy:byte(slot+1), slot*NODE
            if flag ~= 0 and flag ~= 1 then return fail("unsupported_occupancy_byte","occupancy",slot) end
            if flag == 0 then
                if packet.nodes:sub(offset+0x21,offset+0x28) ~= string.rep("\0",8) then
                    return fail("stale_free_node","node.template",slot)
                end
                local free_bytes = packet.nodes:sub(offset+1,offset+NODE)
                if free_bytes ~= zero_node and free_bytes ~= initial_node then
                    return fail("unsupported_free_node_state","node.bytes",slot)
                end
            else
                occupied = occupied+1
                if pointer(packet.nodes,offset+8) ~= d then return fail("node_owner_context_mismatch","node.D",slot) end
                local ptr = pointer(packet.nodes,offset+0x20)
                if not ptr or ptr < template_base or ptr >= template_base+TEMPLATE_COUNT*TEMPLATE then
                    return fail("invalid_template_pointer","node.template",slot)
                end
                local delta = ptr-template_base
                local id, relative = math.floor(delta/TEMPLATE), delta % TEMPLATE
                if relative % ELEMENT ~= 0 then return fail("invalid_template_pointer","node.element",slot) end
                local ordinal = relative/ELEMENT
                if not templates[id] then return fail("missing_template","node.template",slot) end
                if ordinal >= counts[id] then return fail("invalid_template_pointer","node.ordinal",slot) end
                if u32(packet.nodes,offset+0x28) ~= u32(templates[id],relative) then
                    return fail("node_type_mismatch","node.type",slot)
                end
                node_templates[slot], node_ordinals[slot] = id, ordinal
            end
        end
        if occupied ~= used then return fail("occupancy_used_mismatch","used") end

        local normalized, claimed, claim_count, partial = {}, {}, 0, {}
        for i = 1, owner_count do
            local s, canonical = supplied_owners[i].bytes, supplied_owners[i].key
            if pointer(s,8) ~= d then return fail("owner_context_mismatch",canonical,i) end
            if pointer(s,0x20) ~= pool_address then return fail("owner_pool_mismatch",canonical,i) end
            local id, n = u32(s,0x1c), u32(s,0x58)
            if id >= TEMPLATE_COUNT or n > 12 or (id == 0 and n ~= 0) then
                return fail("invalid_owner_state",canonical,i)
            end
            if id ~= 0 and counts[id] == nil then return fail("missing_template",canonical,i) end
            if counts[id] and n > counts[id] then return fail("owner_allocation_exceeds_template",canonical,i) end
            for ordinal = 0, n-1 do
                local slot = u32(s,0x28+ordinal*4)
                if slot >= capacity then return fail("index_out_of_range",canonical,ordinal) end
                if claimed[slot] then return fail("duplicate_node_index",canonical,slot) end
                if packet.occupancy:byte(slot+1) ~= 1 then return fail("index_points_to_free_node",canonical,slot) end
                if node_templates[slot] ~= id or node_ordinals[slot] ~= ordinal then
                    return fail("owner_template_mismatch",canonical,slot)
                end
                local offset = slot*NODE
                if packet.nodes:sub(offset+1,offset+0x18) ~= s:sub(1,0x18)
                    or u32(packet.nodes,offset+0x18) ~= u32(s,0x18) then
                    return fail("node_context_mismatch",canonical,slot)
                end
                claimed[slot], claim_count = canonical, claim_count+1
            end
            if counts[id] and n < counts[id] then partial[#partial+1] = canonical end
            normalized[i] = {key=canonical,requested_id=id,allocated=n}
        end
        local snapshot = {version={build=packet.version.build,exe_sha256=packet.version.exe_sha256,
            game_dll_sha256=packet.version.game_dll_sha256},capacity=capacity,used=used,owners=normalized}
        local admission = Preflight.plan(snapshot,counts,{})
        if admission.status ~= "fits" then return admission end
        return {status="consistent_supplied_bytes",executable=false,snapshot=snapshot,template_counts=counts,
            audit={capacity=capacity,occupied_nodes=occupied,claimed_nodes=claim_count,
                unclaimed_occupied_nodes=occupied-claim_count,partial_owners=partial,
                all_occupied_nodes_accounted=(occupied==claim_count),
                consistency_scope="supplied bytes only; no atomicity, lifetime, live origin or external-alias proof"}}
    end

    function M.validate_and_plan(packet, operations)
        local checked = M.validate(packet)
        if checked.status ~= "consistent_supplied_bytes" then return checked end
        local plan = Preflight.plan(checked.snapshot,checked.template_counts,operations)
        plan.snapshot_audit = checked.audit
        return plan
    end

    return M
end
