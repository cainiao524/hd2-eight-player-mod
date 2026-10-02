# Live preflight continuation（2026-10-03）

這份證據只核對固定 build 的 live image 與已知 native 邊界，沒有呼叫遊戲函式、寫入記憶體、安裝、注入或多人測試。程序 PID `36900`，build `25480438`；EXE 與 `game.dll` 的 SHA-256 與固定版本相符。

## 已核對

- 六個固定 native site 與五個 session/member site 兩次讀取一致。
- executable image 的 bounded scan 得到 27 條 direct `E8` call edge。
- `0x4804FCF4` confirmed-peer event hash 只在 send-side `0xBE4982` 命中。
- `0xBDE430` generic send dispatcher 的 673-byte live code pin 重讀一致。
- 128 MiB private registry scan 沒有找到已知 receiver、insert、member consumer/state update pointer 或 event hash；同一 PID 再擴大到 1 GiB committed `MEM_PRIVATE`，1,655 個 private regions／262,144 pages，仍為 0 hit。
- signature scan 找到 host-join，當前狀態沒有找到 platform-member-enumerator signature；這是程序狀態的 bounded negative observation，不代表函式不存在。

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
