-- Candidate component for the HD2 eight-player prototype.
-- Pure arithmetic over a validated snapshot; no FFI, hooks or game calls.
-- "fits" is not execution authorization or proof of a consistent live snapshot.
local M = {}
local U32, MAX_ROWS, MAX_STEPS = 4294967295, 4096, 8192
local TARGET = {
    build = 25480438,
    exe_sha256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    game_dll_sha256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}

local function plain(t)
    return type(t) == "table" and getmetatable(t) == nil
end

local function integer(n, maximum)
    return type(n) == "number" and n >= 0 and n <= maximum and n == math.floor(n)
end

local function array_size(t, maximum)
    if not plain(t) then return nil end
    local count, last = 0, 0
    for k in pairs(t) do
        if not integer(k, maximum) or k == 0 then return nil end
        count = count + 1
        if k > last then last = k end
    end
    if count ~= last then return nil end
    return count
end

local function reject(code, field, step)
    return { status = code, field = field, step = step, executable = false }
end

function M.target()
    return { build = TARGET.build, exe_sha256 = TARGET.exe_sha256,
        game_dll_sha256 = TARGET.game_dll_sha256 }
end

-- snapshot = {version=..., capacity=u32, used=u32,
--   owners={{key=canonical_S_identity, requested_id=0..72, allocated=0..12},...}}
-- counts[template_id] is the adapter's validated count for that template.
-- operations is the ORIGINAL ordered sequence of {owner=key, template_id=id}.
-- All participating owners must be present, including those changed repeatedly.
function M.plan(snapshot, counts, operations)
    if not plain(snapshot) or not plain(snapshot.version) then
        return reject("invalid_input", "snapshot.version")
    end
    for key, value in pairs(TARGET) do
        if snapshot.version[key] ~= value then
            return reject("version_mismatch", key)
        end
    end
    if not integer(snapshot.capacity, U32) or snapshot.capacity == 0 then
        return reject("invalid_input", "capacity")
    end
    if not integer(snapshot.used, U32) or snapshot.used > snapshot.capacity then
        return reject("invalid_input", "used")
    end
    if not plain(counts) then return reject("invalid_input", "template_counts") end
    for id, n in pairs(counts) do
        if not integer(id, 72) or not integer(n, 12) or (id == 0 and n ~= 0) then
            return reject("invalid_input", "template_counts")
        end
    end
    local owner_count = array_size(snapshot.owners, MAX_ROWS)
    local operation_count = array_size(operations, MAX_STEPS)
    if not owner_count then return reject("invalid_input", "owners") end
    if not operation_count then return reject("invalid_input", "operations") end
    local owners, order, allocated = {}, {}, 0
    for i = 1, owner_count do
        local source = snapshot.owners[i]
        if not plain(source) or type(source.key) ~= "string" or source.key == ""
            or not integer(source.requested_id, 72) or not integer(source.allocated, 12) then
            return reject("invalid_input", "owner", i)
        end
        if owners[source.key] then return reject("duplicate_owner", source.key, i) end
        if source.requested_id == 0 and source.allocated ~= 0 then
            -- Native C2E0 skips old cleanup when old requested ID is zero.
            return reject("inconsistent_ownership", source.key, i)
        end
        if counts[source.requested_id] and source.allocated > counts[source.requested_id] then
            return reject("inconsistent_ownership", source.key, i)
        end
        owners[source.key] = { requested_id = source.requested_id, allocated = source.allocated }
        order[i] = source.key
        allocated = allocated + source.allocated
    end
    if allocated > snapshot.used then return reject("inconsistent_ownership", "used") end

    local used, peak, first_shortage = snapshot.used, snapshot.used, nil
    local steps = {}
    for i = 1, operation_count do
        local op = operations[i]
        if not plain(op) or type(op.owner) ~= "string" or not integer(op.template_id, 72) then
            return reject("invalid_input", "operation", i)
        end
        local current = owners[op.owner]
        if not current then return reject("unknown_owner", op.owner, i) end
        local needed = counts[op.template_id]
        if needed == nil then return reject("unknown_template", tostring(op.template_id), i) end
        local before, released, added = used, 0, 0
        local same = current.requested_id == op.template_id
        if same then
            if current.allocated ~= needed then
                -- A successful future capacity check cannot make the native
                -- same-ID early return repair an existing partial allocation.
                return reject("partial_same_id_requires_recovery", op.owner, i)
            end
        else
            released, added = current.allocated, needed
            used = used - released + added
            current.requested_id, current.allocated = op.template_id, needed
        end
        if used > peak then peak = used end
        if used > snapshot.capacity and not first_shortage then first_shortage = i end
        steps[i] = { owner = op.owner, template_id = op.template_id, same_id_skip = same,
            used_before = before, released = released, added = added, used_after = used }
    end
    local final_owners = {}
    for i = 1, owner_count do
        local key = order[i]
        final_owners[i] = { key = key, requested_id = owners[key].requested_id,
            allocated = owners[key].allocated }
    end
    return {
        status = first_shortage and "insufficient_capacity" or "fits",
        executable = false, -- No live adapter, synchronization or executor exists yet.
        state_semantics = "full_allocation_plan_not_native_post_state",
        peak_required = peak, final_used = used, first_shortage_step = first_shortage,
        additional_capacity_required = math.max(0, peak - snapshot.capacity),
        unlisted_owner_nodes = snapshot.used - allocated,
        steps = steps, final_owners = final_owners,
    }
end

return M
