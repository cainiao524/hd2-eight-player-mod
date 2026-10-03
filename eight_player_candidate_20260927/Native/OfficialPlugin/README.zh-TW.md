# 官方 Stingray Plugin ABI 探針

此目錄保存固定 build `25480438` 的官方 native plugin ABI 探針。`get_plugin_api(unsigned)` 只接受 `api_id == 0`，未知 ID 會回傳 null；公開的 `PluginApi.setup_game` callback 取得 `C_API_ID == 31` 的 `ScriptApi`，再以 `+0x38` 與 `+0x40` 讀取 `Network` 和 `GameSession` table 指標。

目前已在實際遊戲啟動流程觀察到官方 loader 載入 `eight_player_pluginw64_release.dll`，並在 `setup_game` 階段取得非 null 的兩張 table。舊 probe 對 `GameSessionCApi.num_peers()` 的呼叫現已標為 superseded：HD2 的 runtime wrapper/vtable 與公開 SDK 的表布局沒有完成语义绑定，不能把旧 `peer_count` 当作可靠数据。现行探针只在固定 machine-code fingerprint 通过后调用 `NetworkCApi.game_session()` getter 观察 session 指针，不读取 `peer()`、`num_peers()`、`in_session()` 或 `host()`，也不呼叫 `add_peer`、`remove_peer`、`create_game_object` 或其他寫入型 API。舊收據保留於 `five_player_feasibility_20260927/live_official_plugin_probe_20261003_r3.json`，修正說明見 `CAPACITY_PATCH_PEER_OBSERVATION_CORRECTION_20261003.zh-CN.md`。

`unloaded` callback 會清除所有保存的指標，避免使用 stale API。`build_x64.bat` 會建置探針 DLL、synthetic harness 和 `LoadLibrary`/`GetProcAddress` smoke test。

同一 DLL 也會透過 `Native/SessionObservation` 做無函式呼叫的 bounded snapshot：先核對固定 `game.dll` PE identity，再從已保存的 context、roster 與 game-state globals 讀取 local/host/session owner、mode、peer count、最多八筆 `0x20` stride peer record，以及四筆有文檔依據的 `0xC0` stride roster record。roster slot `4..7` 保持 out-of-contract，confirmed-peer window 只保留在外部原始捕獲中，未作語義解碼。任何版本不匹配、count 超過 8、peer index 越界或重複、欄位缺失或重讀變化都 fail-closed；這是 layout 觀察，不是玩家 admission。

ABI 參考：[Autodesk Stingray plugin API samples](https://github.com/AutodeskGames/stingray-plugin-api-samples) 與 [Stingray engine plugin 文件](https://help.autodesk.com/cloudhelp/ENU/Stingray-SDK-Help/sdk_help/extend_engine.html)。

這是版本化的觀察入口，不是八人功能。必須先取得同一 build 的 peer admission、player creation、roster、client cleanup 和 host migration 合約；任何欄位或 callback 未確認時都保持 disabled。

## Consumer executor 整合邊界（2026-10-03）

`ep_official_plugin.dll` 現在會一起編譯 `SessionMembers/ep_consumer_executor.cpp`，並輸出三個明確的橋接入口：`ep_official_plugin_runtime_preflight()`、`ep_official_plugin_runtime_install()` 與 `ep_official_plugin_runtime_remove()`。`preflight` 只做唯讀檢查：固定 build、entry RVA、14-byte target fingerprint、executor ABI、可讀記憶體範圍與五個 callback 是否全部存在；任一項不通過就不會寫入遊戲記憶體。

`runtime_install` 先完整通過相同 preflight，再呼叫可回滾的 consumer executor；`runtime_remove` 只接受自己擁有的 detour。synthetic harness 覆蓋 4 人相容、5--8 人計數、第 9 人拒絕、callback 缺失、target fingerprint 變更、install/remove 還原與 DLL export。這個整合仍未綁定 HD2 的真實 callback、Party admission 或 Player Clone 建立，因此沒有把 `installable`、`runtime_verified` 或 `multiplayer_verified` 門檻改成 true，也沒有將 DLL 放入遊戲目錄。

### Native callback bridge

同一個 OfficialPlugin 也輸出 `ep_official_plugin_runtime_bind_native_callbacks()`、`ep_official_plugin_runtime_get_native_callbacks()` 與 `ep_official_plugin_runtime_unbind_native_callbacks()`。這三個入口只轉接固定 build 的 native callback binder：它會核對 `game.dll` PE timestamp `1790161983` 與 image size `74727424`，並要求 sidecar resolver；未綁定時 getter 會回傳 `EP_CONSUMER_NATIVE_NOT_BOUND`，錯誤參數或 build 不符會拒絕。合成測試驗證 OfficialPlugin 的轉接 export、未綁定 getter、錯誤 bind 與 native callback 自身的 resolver/mode/identity/lookup/status 路徑。這仍然是 ABI 候選，不等同於已驗證的 HD2 player admission 或安裝流程。
