# Player Capacity Native Bridge staging package

這是可匯入 Arsenal/HD2MM 格式的 staging 骨架，包含 `Player Capacity` 的
Lua 設定契約與 Mod Options Menu 入口；它仍不是已完成的八人聯機發布包。

`data/mods/cainiao/hd2_capacity_contract.lua` 統一 4、5、8、12、16 的容量、
有效容量、pending/apply/rollback 和 metadata 驗證。`hd2_capacity_menu.lua`
只在 Bingus Shared Loader 內註冊選單，Native bridge 未通過時會拒絕修改容量。

Host metadata 會帶出 Peer、Roster、Entity、Resource、Network、verified capacity、
apply generation、apply mode 及版本 fingerprints；Client 會重新計算 effective capacity，
任何欄位缺失、不一致或指紋漂移都拒絕加入。選單註冊使用 Bingus Shared Loader 的
API 1 `after_startup` 入口與 Mod Options Menu API 1，並保留第一個 game update 的
診斷輪詢。

## Bingus Shared Loader Lua 封裝

`build_bingus_archive.py` 會把選單入口與三個 `require` 模組封裝成
`Addon/9ba626afa44a3aa3.patch_0`。只有 `mods/cainiao/hd2_capacity_menu`
帶有 `HD2-Addon` 宣告；契約、Runtime 與 FFI 模組是同一個 archive 內的私有
Lua resource，不會被 Shared Loader 當成四個獨立 addon 啟動。建置器固定
UTF-8 plaintext、Lua envelope、resource hash、Steam build 與相同 GUID，並且
不讀取遊戲目錄、不載入 DLL，也不把 staging 包標成多人完成。

```powershell
python eight_player_candidate_20260927/Package/build_bingus_archive.py `
  --output eight_player_candidate_20260927/Package/build/HD2-Player-Capacity-Bingus-staging.zip
```

這個 ZIP 只提供 Lua 選單和安全的 native control client；找不到已載入且 ABI
相符的 native provider 時，畫面會顯示 `Rejected`，不會套用容量。真實
Session/Party/Peer admission、Player Clone、Entity replication 和八帳號任務
收據仍是獨立的 release gate。

`stage_package.py` 只有在下列條件全部成立時才會產生可啟用 staging 目錄：

- Steam build `25480438`、EXE `1.8.46015.0` 及六份檔案 SHA-256 完全相符。
- native admission plan 的 `executable` 為 `true`。
- plan 宣告八個 host/client slot、trampoline unwind、指令重定位、中段 capacity bridge、allocator sidecar continuation、sidecar lifetime、confirmed-peer dispatch 和 player creation gate。
- 固定 build 的 player-creation ABI、peer／confirmed-peer lifecycle、player-resource reverse cleanup、rollback/quiescence sidecar 與 MenuScreenLoadout relocation 審計存在且通過；staging 會核對八槽 peer map、partial callback 回滾、離隊／重連 generation、`FDC780 → FDC820 → FDDC80` cleanup 與 owner 靜默條件。這些報告只證明離線 evidence 完整，仍會保留 production／multiplayer 的 false gate。
- `Native/Bridge` 提供已測試的 sidecar orchestration candidate，會在 callback 缺失、build/site 不符、資源建立失敗或第九個玩家時 fail-closed，並在 admission 失敗時回滾。
- 額外提供 native bridge payload。

腳本只讀遊戲安裝目錄，輸出 staging 目錄和 `rollback.json`；不覆寫、注入或刪除遊戲檔案。即使 staging 成功，`multiplayer_verified` 仍為 `false`，需要五至八個獨立帳號完成實機驗收後才可另行發布。

Bridge 的合成 harness 只驗證 sidecar 與 callback 契約，不代表真實 Session／Party、game.dll 或多人同任務已接通。只有固定 build、Native ABI、執行緒靜止、owner lifetime、confirmed-peer dispatch 與 Player Clone 建立全部通過後，才可生成可啟用 staging；即使 staging 成功，仍須以八個獨立帳號完成實機驗收。

## 為何沒有把 session admission 寫成 Lua/data patch

Bingus Shared Loader 的 addon 介面能載入 Lua 與 data archive。這條路徑沒有權限取代 PlayFab/Party peer admission、host/client confirmed-peer inline storage、Windows x64 trampoline/unwind 或 player creation gate。把 `MAX_PLAYERS` 或資料陣列改成 8 只會改離線資料，無法讓第五個 peer 得到一致的 network index，也不能安全修復原生 cleanup 和 host migration。因此本骨架把 `data/README.txt` 保留為明確標記，native payload 必須獨立通過固定版本 gate。

## 產生診斷和 staging

```powershell
& 'C:\Program Files\Python312\python.exe' `
  eight_player_candidate_20260927/Package/stage_package.py `
  --game-root 'F:\Game\Steam\steamapps\common\Helldivers 2' `
  --native-plan five_player_feasibility_20260927/native_peer_admission_plan_20261002.json `
  --diagnostics eight_player_candidate_20260927/Package/diagnostics.json
```

目前 plan 尚未可執行，命令會 fail-closed 並留下 blocked 診斷。
