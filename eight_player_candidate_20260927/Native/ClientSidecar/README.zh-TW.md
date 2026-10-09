# Client Sidecar 與四槽 Patch Manifest

這個目錄保存 build `25480438` 的 client confirmed-peer 四槽審查結果，以及一個隔離的十六槽資料模型。它涵蓋新增、移除、重排、兩條 reset 路徑、`+0x150` peer-keyed 鄰區、踢出／host migration 交接，以及 player creation gate。

`ep_client_sidecar.dll` 只操作呼叫者配置的 `EP_CLIENT_SIDECAR`。它不尋找遊戲物件、不載入 `game.dll`、不安裝 detour，也不呼叫 Session、Party 或玩家建立函式。移除保留 network index 洞位，generation 防止舊 token 清理新玩家；五組 sidecar 陣列會一起清除，模擬原本分散的固定四槽 reader/writer/cleanup 契約。

`ep_client_bridge_adapter.dll` 現在也要求 caller-provided network-index allocator/release callback。它會先保留 authoritative index，才允許 confirmed-peer append；所有補償、離隊與重連都用同一 index 和 generation，不能由 client sidecar 自行改選本地空槽。

`ep_client_bridge_adapter.dll` 是給 Native Bridge 的最小 callback adapter。它把 confirmed-peer insert、player create、remove 與 owner lifetime callback 都接到 sidecar；所有 index（包括 0–3）都必須經過真實 native create callback，不能把 sidecar 記錄當成已建立角色。native confirm 失敗會保留暫存 identity，交由 Native Bridge 的 remove compensation 清理；native remove 失敗則保留記錄供重試。缺少任一 callback 時初始化直接拒絕。這個拒絕是刻意的安全閘門，不能當成第五至第八名玩家已建立。

`ep_client_adapter_init` 遇到仍 initialized 的 live adapter 會返回 `EP_BRIDGE_ALREADY_READY`，不再用 `memset` 覆寫已保留的 index、client record 或 owner refs；caller 必須先完成 destroy，並以 zero-initialized storage 建立新 adapter。

`client_four_slot_patch_manifest_20261002.json` 是給後續 native bridge 的 machine-readable 接線清單。每個 site 都列出 RVA、root、固定容量證據、sidecar operation、必要 callback 和 fail-closed 條件。`player_creation_gate` 不可用無條件跳轉取代，因為原始 unsigned sentinel 拒絕仍需保留。

## 驗證

`build_x64.bat` 會建立兩個 DLL、執行隔離測試，並輸出 `ep_client_sidecar_synthetic_passed` 和 `ep_client_bridge_adapter_synthetic_passed`。Python 測試會驗證 manifest 覆蓋所有固定四槽流程與 report 雜湊。

這些結果不能證明實際第五至第八名玩家能通過 Session、Party、roster、entity 或任務全流程。要進入實機階段，必須先恢復每個 callback 的真實 ABI、完成 site bytes preflight、把 sidecar 接到 host/client owner lifetime，並通過八個獨立帳號的同任務驗收。

## Allocator-only 越界 index compensation（2026-10-04）

`ep_client_bridge_adapter` 現在會保留 authoritative allocator 回傳的 `index >= 16`，將它放在獨立的 allocator-only retry table，並在 generation `0` 的 `release_index` 中用相同 peer、resource handle 和 index 完成釋放。`Native Bridge` 會在 allocator callback 已回傳 index 但同時回傳錯誤時，也走這條補償路徑。

若 allocator 回傳已被 adapter 保留的 0..15 index，adapter 不會釋放原本的 reservation，也會把 `0xFF` 當作沒有取得新 reservation 的 sentinel，避免 collision 誤刪現有玩家。

這些測試只驗證離線 allocator/sidecar 交易；越界 index 不代表遊戲或 Session/Party 真的允許該 index。
