# 固定版本 live native call-edge／resolver 續查（2026-10-02）

本輪以固定 Steam build `25480438` 啟動原版程序後，對明確指定的 PID `38588` 做唯讀檢查。程序是 `helldivers2.exe`，載入的 `helldivers2.exe` 與 `game.dll` 均通過既有 SHA-256、PE identity 和 code-pin 驗證。未寫入程序、未呼叫遊戲函式、未載入 DLL、未安裝或注入 Mod。

## 新增 live 證據

| 證據 | 結果 |
| --- | --- |
| 固定 native sites 重讀 | `6` 個 game.dll site；每個兩次讀取相同，SHA 與既有 capture 一致 |
| API interface probe | `game.dll+0x3326308` 的 API root、`+0x30/+0x18` 和 `+0xf8/+0xa0` 指標兩次讀取相同 |
| spawn/handle probe | `api+0xc0 → object → vtable+0x18` 指向 `helldivers2.exe+0x30ff50`，4 KB prefix 兩次相同 |
| image data-flow scan | `helldivers2.exe` + `game.dll` 共 33,068 pages；只找到 callback pointer `game.dll+0x214C820 → 0xBABA80` 和 sender hash immediate `game.dll+0xBE4982` |
| API root page | 固定 root page 4 KiB 中 289 個 user-looking qword；173 個指向 `helldivers2.exe`、103 個指向 `lua51.dll`；沒有指向 loaded-image 外 heap 的有效 pointer（其餘是 float-like 小值），因此沒有從這條 API root path 取得 receiver registry |
| config root neighborhood | `game.dll+0x3326340 → 0x15c13120080`；root page 4 個 user-looking qword 均不指向已載入 image，64 KiB／16 pages 內 receiver、consumer、state-update pointer 和事件 hash 均 0 命中 |
| generic send dispatcher code pin | `game.dll+0xBDE430` 的 673-byte body live SHA 與保存的 `ab22276e…` 完全一致，兩次讀取相同；PE raw section bytes SHA `0eea50f7…` 不同（可能包含 relocation，不能直接當 live patch bytes），這只閉合 send-side code identity |
| private registry scan | 295 個 readable `MEM_PRIVATE` regions、128 MiB bounded window、32,768 pages；receiver／consumer／state-update pointers 和 hash 均 **0 命中** |
| direct call-edge scan | 22,271 個 executable pages，91,222,016 bytes，找到 `27` 個 `E8 rel32` direct calls |
| confirmed-peer hash | 在 live `game.dll` 找到唯一 `0x4804FCF4` little-endian occurrence：`game.dll+0xBE4982` |

## 已閉合的 live call edges

掃描直接確認下列 caller 在目前程序狀態中仍呼叫固定 native site：

- `game.dll+0x1092F4E`、`game.dll+0x10944FC` → `game.dll+0x1093590` platform member consumer。
- `game.dll+0x108F078`、`game.dll+0x134E44A`、`game.dll+0x13F788A` → `game.dll+0x10937A0` member state update。
- `game.dll+0x108C960` 的 host branch 及 `game.dll+0xBABAAF` 所在 wrapper → `game.dll+0xB90B20` client confirmed-peer insert；完整 caller 清單和 instruction bytes 見 JSON。
- `game.dll+0x108C...` 的 host join、confirmed-peer sender、migration、remove 等 direct edges 均仍存在，並與既有 site inventory 對應。

`0xBE4982` 位於既有 confirmed-peer sender 的 `mov ecx,0x4804FCF4` 附近，live 結果與靜態 sender capture 一致。這把「send wrapper 使用的事件 hash」與目前載入 image 綁定起來，但仍不是 receiver registry 的證明。

## resolver／dispatcher 結論

目前可以安全說明的是：

1. `platform_member_consumer` 的真實 caller 已由 live direct-call edge 重讀確認，候選 patch 的 caller RVA 不是失效的舊映像。
2. host confirmed-peer sender、client insert、state update 和 player-creation gate 仍位於同一固定 build；可作為後續 trampoline preflight 的 target identity。
3. `0x4804FCF4` 的 send-side hash immediate 在 live image 中只有一個命中，位置是 sender；沒有因此找到 writable receive dispatcher table。
4. API probe 的 `game.dll+0x3326308` 仍能解析出 send/handle 介面，但它不是已證明的 PlayFab/Party 接納器，也不是 receiver hash-to-callback 綁定。
5. 受限私有 heap 掃描沒有找到 receiver、consumer、state-update function pointer 或事件 hash；這是目前程序狀態和 128 MiB address-order window 的負面證據，不能推論其他 heap／未載入狀態不存在。
6. API root page 的一層 qword 分類沒有發現 loaded-image 外的有效物件指標；它支持「目前 API path 只能閉合到既有 image/vtable」的判斷，不能把 Lua 指標或 float-like 值當作 native dispatcher。
7. `0xBDE430` 的 live body 與磁碟 raw body 不相同；本輪只把它當作重定位／載入後差異的診斷，沒有推論加密或修改，也不允許用 raw bytes 直接安裝 patch。
8. 已知的 config-root private object neighborhood 也沒有出現受查 function pointer 或 `0x4804FCF4`；其四個 qword 仍缺乏可識別的 receiver table ABI，因此不能把它升格為 dispatcher。

因此本輪**沒有生成可安裝 patch，也沒有把任何 live pointer 當成 resolver/dispatcher ABI**。仍缺：

- hash `0x4804FCF4` 到 receiver `0xBABA80` 的 writable runtime registry binding；
- host/client sidecar 的 owner lifetime、rollback、migration、cleanup 和 thread quiescence；
- `0x108C18F`／`0x108C3D8` mid-function continuation 的完整 register/stack/unwind ABI；
- index `4..7` 的實際 resource/player creation callback；
- 五至八個獨立帳號同任務紀錄。

## 可重現檔案

- `tools/scan_live_callers.py`：明確 PID、固定 build、只讀 executable-image `E8 rel32` 與 hash 掃描器。
- `live_native_call_edges_20261002.json`：本輪 PID `38588` 的 call edges 和 hash hit。
- `live_native_sites_20261002_6.json`：六個 admission/player sites 的固定版本重讀。
- `interface_probe_live_20261002_2.json`、`spawn_interface_probe_live_20261002_2.json`：API/handle 指標重讀。
- `live_dispatcher_data_20261002.json`：API fixed-path 欄位、image pointer/hash hits 和穩定頁重讀。
- `live_dispatcher_data_20261002_2.json`：同一固定 path 的 API root page 一層 qword 分類（含 Lua 指標分類），未發現有效 heap registry pointer。
- `live_dispatcher_data_20261002_4.json`：再加入 `0xBDE430` generic send dispatcher 的 live code-pin 與磁碟 raw section 對照（673 bytes，live 重讀一致；raw 不同但未推論原因）。
- `live_dispatcher_data_20261002_6.json`：加入 config-root `game.dll+0x3326340` 的 64 KiB neighborhood 與 root-page qword 分類（16 pages，受查 pattern 0 命中）。
- `live_private_registry_20261002.json`：128 MiB readable private-memory bounded scan（零命中）。

所有結果欄位明確標示 `read_only=true`、`calls_made=false`、`writes_made=false`、`eight_player_verified=false`。這些結果縮小了接線範圍，但不能被解讀為五人或八人已成功加入。
