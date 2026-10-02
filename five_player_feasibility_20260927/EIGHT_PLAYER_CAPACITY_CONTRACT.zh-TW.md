# 八人容量與接納契約

## 狀態

這是與 `v0.14.0-offline` 候選並行的離線契約元件。它沒有讀取遊戲程序、呼叫 FFI、載入 DLL、安裝 Mod 或發布網路封包，不能單獨宣稱第五至第八名玩家已可加入。

目標版本固定為 Steam build `25480438`，並保留既有 EXE／`game.dll` SHA-256 指紋。未知版本必須拒絕啟用。

## 單一容量規則

| 欄位 | 值 |
|---|---:|
| `logical_max_players` | 8 |
| `storage_slots` | 8 |
| 合法 `network_index` | 0–7 |
| 拒絕 | 非整數、負數、8 以上、重複 index |

`network_index`、roster `ordinal`、manager ordinal 和 resource handle 是不同欄位。移除玩家只釋放自己的 slot，保留其他玩家的 ordinal；契約不做未經證明的 dense compaction。

## 已實作介面

- `eight_player_candidate_20260927/Source/eight_player_capacity.lua`：Mod 側純狀態模型、profile／index／count guard、insert／lookup／remove／resource bind、診斷事件與 snapshot。
- `eight_player_candidate_20260927/Source/pool_preflight.lua`：仍負責共用 node pool 的容量預檢；未把 pool 預檢誤當成玩家接納。
- `eight_player_capacity_contract.py`：Python 離線鏡像，供報告和序列化 snapshot 核對。
- `admission_observation.py`：PlayFab lobby、Party network（user／device／endpoint 上限）、host peer、client confirmed-peer、player creation 與 roster 的顯式觀測 schema；不會自行取得任何觀測值。
- `peer_admission_adapter.py`：把同一 observation epoch 的 lobby／Party／host peer／confirmed-peer 接到容量狀態，處理 0–7 allocation、pending bind、generation、離隊與重連；仍是離線候選。
- `../eight_player_candidate_20260927/NATIVE_ROSTER_MASK_READER.zh-TW.md`：`1277920` reader 的離線 B-sidecar 候選與有限指令驗證。

所有拒絕都不修改 roster state，並回傳具體 reason。`snapshot()` 只有在 index、ordinal、active count 和反向映射一致時才會產生。

## 接入順序

native adapter 尚未存在，接入時必須按以下順序調用：

1. 檢查 build profile。
2. 檢查同一 observation epoch 的 lobby／Party admission 結果。
3. 驗證 host peer、confirmed-peer 和 platform member 的 index。
4. 建立 pending roster entry。
5. 完成帶 reservation generation 的角色 resource handle bind 後才發布可控制狀態。
6. 以同一順序執行帶 generation 的 remove、cleanup、reconnect 和 host migration。

host-only 先作為候選路徑。若原版客戶端在 roster、entity replication 或 resource creation 讀取四槽，則必須改成所有客戶端安裝同一版本；不能只依 lobby 名單成功判定 host-only 可用。

## 驗證界限

離線測試只證明契約的輸入拒絕、八槽映射、洞位保留、resource bind、snapshot 一致性及觀測 schema。真實五至八人任務、hot-join、死亡／增援、離隊／重連、撤離／結算仍需要另外授權和八個獨立帳號的實測。
