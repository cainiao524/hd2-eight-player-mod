# PlayerCreationGate：固定 build 的八槽建立 ABI 候選

此目錄把固定 build `25480438` 的 player 建立 gate 與下游建立鏈包成一個**版本門控、可回滾的 ABI adapter**：

```text
0x1086460 gate
    └─ 0xFDC140 resource/component dispatch
         └─ 0x608B60 roster path
```

它不會自己尋找 `game.dll`、開啟遊戲程序、呼叫未知函式或寫入記憶體。所有遊戲特定行為都必須由 caller 提供 callback；所有 patch 寫入都必須由 caller 提供 `quiesce/resume/write` backend。沒有完整下游 provider 時，gate 擴容會拒絕。

## 建立交易

`ep_pc_admit` 使用 caller 提供的權威 network index，不將 roster ordinal 或本地第一個空槽當成替代值。`0..7` 各自保存 generation、peer、resource handle 和 owner epoch；`8` 以上直接拒絕。交易順序為：

```text
retain owner
  → resolve resource
  → dispatch components
  → insert roster
  → active
```

任一步失敗會呼叫 rollback；rollback 失敗會保留 `REMOVING` 槽位與 `rollback_pending` 標記，`ep_pc_depart` 會重試同一個 rollback callback，不會誤走正常離隊 cleanup。所有 callback 完成後若本地 commit invariant 失敗，也會先補償再返回 `EP_PC_INVARIANT_BROKEN`。正常離隊會先清理 roster，再清理 components；清理失敗同樣保留槽位與 owner lease。

## Gate patch 契約

`ep_pc_preflight` 只核對 caller 提供的 image bytes：

- gate `game.dll+0x1086460` 的 9-byte fingerprint，最後 immediate 必須是 `4`；
- 下游 `0xFDC140` 與 `0x608B60` 的 site fingerprint；
- build、callback、quiesce/write backend 完整性。

`ep_pc_install_gate_patch` 還會要求 `downstream_ready` callback 回報所有 resource、component、roster、cleanup backing 已接通，才把 gate immediate 暫時改成 `8`。移除時使用原始 9 bytes 還原。模組本身沒有 `VirtualProtect`、`WriteProcessMemory` 或注入器，因此目前不能單獨安裝到遊戲。

## 建置與範圍

```powershell
cmd /c build_x64.bat
```

`ep_player_creation_gate_synthetic_passed` 覆蓋固定 build/site preflight、下游未就緒拒絕、可回滾 gate、八個權威 index、重複 identity、離隊 cleanup retry、rollback retry、post-callback invariant compensation 及 resource/roster rollback。這些是離線 ABI 測試，不是第五至第八名玩家的實機驗收；`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。
## v3 互斥與生命週期

`EP_PC_VERSION=3` 為所有同步變更操作加入單一 operation guard。`ep_pc_admit`、`ep_pc_depart`、patch 安裝/移除、prepare 和 destroy 在外部 callback 或 quiesce/write 期間保持交易忙碌；同執行緒重入與另一執行緒重疊呼叫都回傳 `EP_PC_BUSY`，不會第二次清理、釋放 owner 或覆寫 live adapter。

`ep_pc_init` 不再覆蓋已初始化的 adapter；呼叫方必須保證 adapter 儲存與 callback owner 在整個交易期間有效，先完成 `ep_pc_destroy` 再重用記憶體。忙碌或未完成的槽位仍需依序完成 departure/rollback，之後才可 destroy。

測試同時覆蓋正常離隊和 failed-admit rollback 的 callback 重入，以及 worker thread 重疊呼叫；兩種情況都確認 cleanup、rollback 和 owner release 僅執行一次。

建立交易在第一次本地 invariant 檢查失敗時也會同步清除剛保留的 `PENDING` 槽位；這條路徑尚未 retain 外部 owner，因此不會虛構 rollback 或 release callback。重複 identity、非法 index 與其他未建立 reservation 的拒絕則直接返回，不會觸碰 slot。
