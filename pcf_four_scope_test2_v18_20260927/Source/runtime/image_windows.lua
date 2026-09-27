-- Read-only image/hash adapter reused for version checks; no capture output.
-- read() skip reasons: 1 bounds/closed, 2 module changed, 3 region query/layout,
--                     4 page identity/protection, 5 failed/short memory read.
-- Native handles used for hashing are opened and closed within file_hashes().
-- This module does not call native game functions or write to process memory.
return function(profile)
    local ffi = require('ffi')
    assert(ffi.os == 'Windows' and ffi.arch == 'x64' and ffi.abi('64bit'),
           'Windows x64 LuaJIT required')
    local image_size = type(profile) == 'table' and profile.image_size
    assert(type(image_size) == 'number' and image_size == math.floor(image_size)
           and image_size > 0 and image_size <= 0x7fffffff, 'Invalid image size')

    -- Use one uniquely named layout and reuse any compatible declarations already
    -- installed by the shared loader. All imported functions have the Windows ABI.
    if not pcall(ffi.typeof, 'P11ReadOnlyCaptureRegionV1') then
        ffi.cdef [[
            typedef struct {
                void *base; void *allocation_base; uint32_t allocation_protection;
                uint16_t partition; uint16_t reserved; size_t size;
                uint32_t state; uint32_t protection; uint32_t type;
            } P11ReadOnlyCaptureRegionV1;
        ]]
    end
    assert(ffi.sizeof('P11ReadOnlyCaptureRegionV1') == 48
           and ffi.offsetof('P11ReadOnlyCaptureRegionV1', 'size') == 24,
           'Unexpected Windows memory region layout')
    local kernel, bcrypt = ffi.load('kernel32'), ffi.load('bcrypt')
    local function declare(library, name, signature)
        if not pcall(function() return library[name] end) then ffi.cdef(signature) end
    end
    declare(kernel, 'GetModuleHandleA', 'void *GetModuleHandleA(const char *);')
    declare(kernel, 'GetModuleFileNameW', 'uint32_t GetModuleFileNameW(void *, uint16_t *, uint32_t);')
    declare(kernel, 'GetCurrentProcess', 'void *GetCurrentProcess(void);')
    declare(kernel, 'VirtualQuery', 'size_t VirtualQuery(const void *, void *, size_t);')
    declare(kernel, 'ReadProcessMemory', 'int ReadProcessMemory(void *, const void *, void *, size_t, size_t *);')
    declare(kernel, 'CreateFileW', 'void *CreateFileW(const uint16_t *, uint32_t, uint32_t, void *, uint32_t, uint32_t, void *);')
    declare(kernel, 'GetFileSizeEx', 'int GetFileSizeEx(void *, int64_t *);')
    declare(kernel, 'ReadFile', 'int ReadFile(void *, void *, uint32_t, uint32_t *, void *);')
    declare(kernel, 'CloseHandle', 'int CloseHandle(void *);')
    declare(bcrypt, 'BCryptOpenAlgorithmProvider', 'int32_t BCryptOpenAlgorithmProvider(void **, const uint16_t *, const uint16_t *, uint32_t);')
    declare(bcrypt, 'BCryptCloseAlgorithmProvider', 'int32_t BCryptCloseAlgorithmProvider(void *, uint32_t);')
    declare(bcrypt, 'BCryptCreateHash', 'int32_t BCryptCreateHash(void *, void **, void *, uint32_t, const void *, uint32_t, uint32_t);')
    declare(bcrypt, 'BCryptHashData', 'int32_t BCryptHashData(void *, const void *, uint32_t, uint32_t);')
    declare(bcrypt, 'BCryptFinishHash', 'int32_t BCryptFinishHash(void *, void *, uint32_t, uint32_t);')
    declare(bcrypt, 'BCryptDestroyHash', 'int32_t BCryptDestroyHash(void *);')

    local module = kernel.GetModuleHandleA('game.dll')
    assert(module ~= nil, 'game.dll is not loaded')
    local base = tonumber(ffi.cast('uintptr_t', module))
    assert(base >= 0x10000 and base + image_size < 0x800000000000,
           'Unexpected module address')
    local closed = false
    local process = kernel.GetCurrentProcess() -- A pseudo handle, never opened/closed.
    local region = ffi.new('P11ReadOnlyCaptureRegionV1[1]')
    local buffer, count = ffi.new('uint8_t[4096]'), ffi.new('size_t[1]')
    local readable = {[2]=true, [4]=true, [8]=true, [32]=true, [64]=true, [128]=true}
    local api = {base_low=base % 4294967296, base_high=math.floor(base / 4294967296)}
    local function same_module()
        return not closed and kernel.GetModuleHandleA('game.dll') == module
    end
    local function pointer(address) return ffi.cast('void *', address) end

    function api.read(rva, size)
        if closed or type(rva) ~= 'number' or rva ~= math.floor(rva) or rva < 0
           or type(size) ~= 'number' or size ~= math.floor(size) or size < 1 or size > 4096
           or rva > image_size - size then return nil, 1 end
        if not same_module() then return nil, 2 end
        local pieces, cursor, ending = {}, base + rva, base + rva + size
        while cursor < ending do
            if not same_module() then return nil, 2 end
            if tonumber(kernel.VirtualQuery(pointer(cursor), region, 48)) ~= 48 then
                return nil, 3
            end
            local r = region[0]
            local first = tonumber(ffi.cast('uintptr_t', r.base))
            local owner = tonumber(ffi.cast('uintptr_t', r.allocation_base))
            local span = tonumber(r.size)
            local last, protection = first + span, tonumber(r.protection)
            if first < 0x10000 or first > cursor or span <= 0
               or last <= cursor or last > 0x800000000000 then return nil, 3 end
            if tonumber(r.state) ~= 0x1000 or tonumber(r.type) ~= 0x1000000 or owner ~= base
               or math.floor(protection / 256) % 2 ~= 0
               or not readable[protection % 256] then return nil, 4 end
            local amount = math.min(ending - cursor, last - cursor, 4096 - cursor % 4096)
            count[0] = 0
            if not same_module() then return nil, 2 end
            if kernel.ReadProcessMemory(process, pointer(cursor), buffer, amount, count) == 0
               or tonumber(count[0]) ~= amount then return nil, 5 end
            pieces[#pieces + 1] = ffi.string(buffer, amount)
            cursor = cursor + amount
        end
        if not same_module() then return nil, 2 end
        return table.concat(pieces)
    end

    local function file_hash(target_module, label)
        local file, algorithm, hash
        local invalid = ffi.cast('void *', -1)
        local ok, result = pcall(function()
            local path = ffi.new('uint16_t[32768]')
            local length = tonumber(kernel.GetModuleFileNameW(target_module, path, 32768))
            assert(length > 0 and length < 32768, 'Cannot resolve ' .. label .. ' file')
            -- GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, SEQUENTIAL_SCAN.
            -- Denying write/delete sharing prevents concurrent replacement while
            -- this handle is hashing. No path is included in the capture output.
            file = kernel.CreateFileW(path, 0x80000000, 1, nil, 3, 0x08000000, nil)
            assert(file ~= nil and file ~= invalid, 'Cannot open ' .. label .. ' read-only')
            local length64 = ffi.new('int64_t[1]')
            assert(kernel.GetFileSizeEx(file, length64) ~= 0, 'Cannot size ' .. label)
            local file_size = tonumber(length64[0])
            assert(file_size > 0 and file_size <= 67108864, label .. ' exceeds file size bounds')
            algorithm, hash = ffi.new('void *[1]'), ffi.new('void *[1]')
            local name = ffi.new('uint16_t[7]', {83,72,65,50,53,54,0})
            assert(bcrypt.BCryptOpenAlgorithmProvider(algorithm, name, nil, 0) == 0,
                   'SHA256 unavailable')
            assert(bcrypt.BCryptCreateHash(algorithm[0], hash, nil, 0, nil, 0, 0) == 0,
                   'SHA256 creation failed')
            local block, got = ffi.new('uint8_t[1048576]'), ffi.new('uint32_t[1]')
            local total = 0
            while total < file_size do
                local amount = math.min(1048576, file_size - total)
                got[0] = 0
                assert(kernel.ReadFile(file, block, amount, got, nil) ~= 0,
                       label .. ' file read failed')
                assert(tonumber(got[0]) == amount, label .. ' file read was shortened')
                assert(bcrypt.BCryptHashData(hash[0], block, amount, 0) == 0,
                       'SHA256 update failed')
                total = total + amount
            end
            assert(kernel.GetFileSizeEx(file, length64) ~= 0 and tonumber(length64[0]) == file_size,
                   label .. ' changed during hashing')
            local digest, hex = ffi.new('uint8_t[32]'), {}
            assert(bcrypt.BCryptFinishHash(hash[0], digest, 32, 0) == 0, 'SHA256 finish failed')
            for i = 0, 31 do hex[#hex + 1] = string.format('%02x', tonumber(digest[i])) end
            return table.concat(hex)
        end)
        -- Always attempt every applicable release, even if an earlier release
        -- reports an error. Never retain handles between game update frames.
        local cleanup_ok = true
        local function release(fn)
            local released, status = pcall(fn)
            if not released or not status then cleanup_ok = false end
        end
        if hash and hash[0] ~= nil then
            release(function() return bcrypt.BCryptDestroyHash(hash[0]) == 0 end)
        end
        if algorithm and algorithm[0] ~= nil then
            release(function() return bcrypt.BCryptCloseAlgorithmProvider(algorithm[0], 0) == 0 end)
        end
        if file ~= nil and file ~= invalid then
            release(function() return kernel.CloseHandle(file) ~= 0 end)
        end
        if not ok then error(result, 0) end
        assert(cleanup_ok, 'Hashing resource cleanup failed')
        return result
    end

    function api.file_hashes()
        assert(same_module(), 'Version adapter closed or game.dll changed')
        local game_hash = file_hash(module, 'game.dll')
        assert(same_module(), 'game.dll changed during hashing')
        local exe_hash = file_hash(nil, 'host EXE')
        assert(same_module(), 'game.dll changed during hashing')
        return {game_sha256=game_hash, exe_sha256=exe_hash}
    end
    function api.close() closed = true end
    return api
end
