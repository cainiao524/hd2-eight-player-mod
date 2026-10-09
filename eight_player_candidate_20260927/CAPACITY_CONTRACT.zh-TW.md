# 可配置玩家容量契約

## 目前狀態

這份契約已接入 Lua 設定模型、Mod Options Menu adapter 與離線 Native C ABI。
它不是遊戲程式內的容量證明；`native_runtime_verified` 和
`multiplayer_verified` 在真實 callback、客戶端與多人任務通過前必須保持 `false`。

## 容量規則

支援的設定值為 1～目前已驗證容量。內建選項為 4、5、8、12、16，硬儲存上限為
16。實際有效容量由以下欄位取最小值：

```text
effective_max_players = min(
    configured_max_players,
    peer_capacity,
    roster_capacity,
    entity_capacity,
    resource_capacity,
    network_capacity,
    verified_capacity
)
```

玩家索引是 `0..effective_max_players-1`。network index、roster ordinal、manager
ordinal、platform member index 和 entity handle 不得共用同一欄位。重複 index、超界
index、缺失資源或部分初始化都必須拒絕並回滾。

## 設定與權限

- 只有房主可套用容量；客戶端只讀取 Session metadata。
- `Require Same Mod Version` 預設開啟。
- 任務中不得降低容量。
- 任務中增加容量需要 `Next Mission`、完整資源預留與 thread quiescence。
- 任一版本、ABI、容量或 callback 不符時，不進行部分套用。

## Metadata

Host metadata 必須至少包含：

```text
schema_version
build
mod_version
configured_max_players
effective_max_players
peer_capacity
roster_capacity
entity_capacity
resource_capacity
network_capacity
generation
allow_join_in_progress
require_same_mod_version
```

客戶端在建立 Player Clone 前驗證 metadata。拒絕結果要包含明確 reason code，並
寫入 host/client 診斷日誌。

## 啟用邊界

`player_capacity_menu.lua` 只註冊選項、顯示狀態並轉送 request。真正的 Session、
Party、Peer、Roster、Player Clone 與 Entity replication 由 Native bridge 負責。缺少
Native bridge、版本指紋不符、ABI 未證明或 owner 尚未 quiescent 時，選單仍可顯示，
但不得聲稱容量已改變。
