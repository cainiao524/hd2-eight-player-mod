# Live preflight continuation（2026-10-03）

這份證據只核對固定 build 的 live image 與已知 native 邊界，沒有呼叫遊戲函式、寫入記憶體、安裝、注入或多人測試。程序 PID `36900`，build `25480438`；EXE 與 `game.dll` 的 SHA-256 與固定版本相符。

## 已核對

- 六個固定 native site 與五個 session/member site 兩次讀取一致。
- executable image 的 bounded scan 得到 27 條 direct `E8` call edge。
- `0x4804FCF4` confirmed-peer event hash 只在 send-side `0xBE4982` 命中。
- `0xBDE430` generic send dispatcher 的 673-byte live code pin 重讀一致。
- 128 MiB private registry scan 沒有找到已知 receiver、insert、member consumer/state update pointer 或 event hash；同一 PID 再擴大到 1 GiB committed `MEM_PRIVATE`，1,655 個 private regions／262,144 pages，仍為 0 hit。
- signature scan 找到 host-join，當前狀態沒有找到 platform-member-enumerator signature；這是程序狀態的 bounded negative observation，不代表函式不存在。

## 第二批 reread（同一 PID）

第二批檔案 `live_native_sites_20261003_r2.json`、`live_session_member_sites_20261003_r2.json`、`live_call_edges_20261003_r2.json` 及 `live_private_registry_20261003_r2.json` 與第一批逐項比對；固定映像 hash、11 個 native/session site hash、27 條 direct edge、唯一 send-side event hash 及 128 MiB registry 負面結果均一致。`live_preflight_r2_verification_20261003.json` 的 11/11 檢查通過。這是穩定性證據，不是 runtime resolver 或多人驗收。

另以 `capture_live_session_snapshot_20261003.py` 讀取同一 PID 的已知 network context。`live_session_snapshot_20261003_r2.json` 觀察到 1 個 peer，`live_session_snapshot_20261003_r3.json` 觀察到 4 個 peer，四個 network index 為 `0..3`；兩次均只接受公開固定布局中的四筆 roster records，slot `4..7` 明確列為 out-of-contract。`live_session_snapshot_verification_20261003.json` 的 11/11 檢查通過。這確認了四人基線的真實讀取路徑，但沒有提供第五人或八人證據。

`r4` 另保存 `session_owner+0x20` 的 224-byte raw window（hash `6c87dea4699bac3c2eedfa5cea4613523034d5b62dcf6b2a5bdb1a98d0f19819`）；欄位語義仍未解碼。`r5` 在同一 bounded probe 遇到不可讀區域並回報 `blocked_snapshot_read`，證明探針會 fail-closed；它不被計入成功觀察。

後續固定 build 程序 PID `22976` 的 `r6`／`r7` 只補充空 menu 到單一本機 peer 的 session 基線（peer count `0 → 1`、mode `0 → 3`、index `0`）。兩份擷取保持 read-only，沒有第五個 peer、角色建立或多人驗收；原程序沒有被寫入或注入。

同一程序退出後，對 PID `22976` 的六個 native site 重讀以 `WinError 31` fail-closed；[live_native_sites_20261003_r3.failure.json](live_native_sites_20261003_r3.failure.json) 只保存失敗原因與範圍，沒有 native bytes，也不計入成功觀察。

## 判定

`live_preflight_continuation_verification_20261003.json` 的 22 項固定檢查通過，但 `resolver_closed=false`、`installable=false`、`multiplayer_verified=false` 保持不變。這批資料證明固定 build 和 native code identity 穩定，沒有提供 service-side hash→selector registry、第五個 peer 的成功加入、player creation 或角色生命週期證據。

下一個可接受的實作門檻仍是：取得允許的 runtime callback/registry 觀測，完成第五 peer 的 host/client confirmed-peer→player-creation 記錄，再產生可回滾 production hook，最後逐級驗證五至八帳號同任務全流程。

可重播的唯讀工具：

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/tools/capture_native_sites.py --pid 36900 --output five_player_feasibility_20260927/live_native_sites_20261003.json
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/tools/capture_session_member_sites.py --pid 36900 --output five_player_feasibility_20260927/live_session_member_sites_20261003.json
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/tools/scan_live_callers.py --pid 36900 --output five_player_feasibility_20260927/live_call_edges_20261003.json
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/tools/capture_live_dispatcher_data.py --pid 36900 --output five_player_feasibility_20260927/live_dispatcher_data_20261003.json
```
