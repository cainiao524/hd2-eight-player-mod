# Client Sidecar 與四槽 Patch Manifest

這個目錄保存 build `25480438` 的 client confirmed-peer 四槽審查結果，以及一個隔離的八槽資料模型。它涵蓋新增、移除、重排、兩條 reset 路徑、`+0x150` peer-keyed 鄰區、踢出／host migration 交接，以及 player creation gate。

`ep_client_sidecar.dll` 只操作呼叫者配置的 `EP_CLIENT_SIDECAR`。它不尋找遊戲物件、不載入 `game.dll`、不安裝 detour，也不呼叫 Session、Party 或玩家建立函式。移除保留 network index 洞位，generation 防止舊 token 清理新玩家；五組 sidecar 陣列會一起清除，模擬原本分散的固定四槽 reader/writer/cleanup 契約。

`ep_client_bridge_adapter.dll` 是給 Native Bridge 的最小 callback adapter。它把 confirmed-peer insert/remove 接到 sidecar；index 0–3 的建立回傳只表示模型記錄存在，index 4–7 必須另外提供真實 player-creation callback，沒有 callback 時一律回滾／拒絕。這個拒絕是刻意的安全閘門，不能當成第五至第八名玩家已建立。

`client_four_slot_patch_manifest_20261002.json` 是給後續 native bridge 的 machine-readable 接線清單。每個 site 都列出 RVA、root、固定容量證據、sidecar operation、必要 callback 和 fail-closed 條件。`player_creation_gate` 不可用無條件跳轉取代，因為原始 unsigned sentinel 拒絕仍需保留。

## 驗證

`build_x64.bat` 會建立兩個 DLL、執行隔離測試，並輸出 `ep_client_sidecar_synthetic_passed` 和 `ep_client_bridge_adapter_synthetic_passed`。Python 測試會驗證 manifest 覆蓋所有固定四槽流程與 report 雜湊。

這些結果不能證明實際第五至第八名玩家能通過 Session、Party、roster、entity 或任務全流程。要進入實機階段，必須先恢復每個 callback 的真實 ABI、完成 site bytes preflight、把 sidecar 接到 host/client owner lifetime，並通過八個獨立帳號的同任務驗收。
