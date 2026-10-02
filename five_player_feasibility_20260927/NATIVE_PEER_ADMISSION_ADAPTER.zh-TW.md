# 原生 Peer Admission Adapter（build 25480438）

本輪在使用者明確授權下保存了一次遊戲程序唯讀擷取。程序 PID、模組基址、指定 native root 的 4 KiB bytes、Party 建立鏈的間接函式指標，以及所有 SHA-256 均保存於 [`live_native_session_capture_20261002.json`](live_native_session_capture_20261002.json)。沒有寫入程序記憶體，沒有安裝 hook，也沒有修改遊戲檔案。

## 已核對的現況

本機 Steam appmanifest 為 build `25480438`。當時載入的模組包括 `helldivers2.exe`、`game.dll`、`PartyWin.dll` 及 `PlayFabMultiplayerWin.dll`。`0x8E15CB` 的 Party 建立間接槽已在載入映像中解析到程序內 thunk；其下游仍是受保護／虛擬化的程序程式碼，不能只以磁碟 bytes 產生可重定位 hook。

已保存的 game native roots：

- `0x108BC70`：host join root。
- `0x108C18F`：四人 remaining-capacity gate。
- `0x108C3D8`：host index allocator，掃描 `host+0x100` 的四個 flags。
- `0x108C760`：confirmed-peer sender。
- `0x1089720`：host migration rebuild。
- `0x108D190`：host peer removal。
- `0xB90B20`：client confirmed-peer insert。
- `0x1087540`：client confirmed-peer remove。
- `0x10845B0`：client confirmed-peer reset。
- `0x1086460`：network index 小於四的 player-creation gate。

## Sidecar 設計

[`native_peer_admission_adapter.py`](native_peer_admission_adapter.py) 對這些 root 建立可審閱的 sidecar 計畫：

- host peer、pending、flag、large-record 和 migration 狀態各保留八槽外部儲存。
- client confirmed-peer 另保留八槽，避免第五筆覆蓋 client `+0x150` 鄰接結構。
- network index 僅接受 `0..7`，ordinal、generation、resource handle 分開保存。
- 離隊保留洞位；重連增加 generation，舊 callback 不能綁到新玩家。
- 只有 confirmed resource handle 才能由 pending 轉 active。

因此不會把一個 `cmp ...,4` 直接改成 `cmp ...,8`。目前已知四槽資料是 inline 結構，單一立即數修改會把第五筆寫入相鄰欄位。必須以完整 trampoline、Windows unwind、sidecar lifetime、confirmed-peer dispatch 和 player-creation gate 改接作為一個提交。

## 離線驗證

```powershell
& 'C:\Program Files\Python312\python.exe' -B -m unittest -v five_player_feasibility_20260927/test_native_peer_admission_adapter.py
```

目前 6/6 通過，涵蓋八個 index、洞位、generation、重複 identity、resource handle、capture schema 和本機四個 build file fingerprint。

`native_peer_admission_plan_20261002.json` 已由本次 capture 產生，但明確標記 `executable=false`、`multiplayer_verified=false`。它是原生改接規格與生命週期候選，不是已安裝的 binary patch。

## 尚未閉合的條件

1. 受保護 native code 的 trampoline 位置、寄存器／stack contract、Windows unwind 註冊。
2. host/client sidecar 的真實 owner lifetime、cleanup、host migration 及 callback 重入契約。
3. PlayFab／Party 實際 join result 與第五名 peer 的 confirmed 接收。
4. 第五至第八名玩家角色建立、entity replication、死亡／增援／重連／撤離／結算的多人測試。

所以本輪把 P1 的程序入口與 adapter 規格推進到可實作邊界，仍不能宣稱八人 Mod 已可安裝或已完成多人驗收。
