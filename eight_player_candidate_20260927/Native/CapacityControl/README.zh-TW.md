# CapacityControl

這是 Lua 設定頁與 Native admission bridge 之間的版本化控制邊界，鎖定
Steam build `25480438`。它不猜測 HD2 的 Session/Party ABI，也不自行尋找或呼叫
遊戲函式；只有已綁定、可檢查 owner 的 provider 才能讓 `ep_control_bind` 成功。

控制流程如下：

1. Lua 只取得固定 ABI 的 snapshot，提交帶有 binding epoch、authority epoch、generation
   和完整容量設定的 request。
2. Native 在提交和實際 apply boundary 重新檢查房主權限、客戶端相容性、版本、任務狀態、
   quiescence、所有層級的 reservation，以及 sparse network index。
3. provider 必須同步完成 Session/Party、Peer、Roster、Entity、resource 與 metadata 的
   commit；任一部分失敗就呼叫 rollback。
4. rollback 失敗會留下 fault bit，阻止後續 admission、reconnect 和 destroy，直到外部
   provider 修復並明確清理。

這個目錄的 fixture 只使用隔離的 caller-owned sidecar，沒有載入 `game.dll`、注入、
寫入遊戲記憶體或建立網路連線。`test_capacity_control.py` 的三項測試只證明控制
邊界、原子提交、回滾和容量拒絕；它不代表實機多人支援。

## 尚未宣稱的部分

真實 provider 尚未閉合 Session/Party allocator、confirmed-peer receiver、Player Clone、
client entity replication、thread quiescence 和八帳號任務生命週期，因此正式啟用閘門仍為
`executable=false`、`installable=false`、`multiplayer_verified=false`。
