# Player 建立鏈固定四人讀者審計（固定 build 25480438）

本頁把既有固定擷取中的 `ClientSynchronizer` player 建立 gate、資源參數、元件 callback 與 session member 更新鏈接成一份可重播審計。腳本只讀工作區 JSON，不呼叫遊戲程序、不寫記憶體、不安裝 hook，也不宣稱多人成功。

## 已確認的 index 4–7 行為

`0x1085D70` 內的 gate：

```text
0x1086460  cmp dword ptr [rdx + r8 + 0x163ac], 4
0x1086469  jae 0x108624d
```

這是 confirmed-peer 儲存的 unsigned network index。`0..3` 進入 `0x108646F`，而 `4..7` 直接進入 fallback ring；在這個 root 的正常 CFG 中，後者不會到達 player 資源分派：

| 項目 | RVA／值 | 意義 |
|---|---|---|
| dummy handle 參數 | `0x1086823` = `0xb04d927afb137b9b` | 固定名稱表與 `content/entities/dummy` 相符 |
| player 資源參數 | `0x1086837` = `0xcdc1f82ce3337a82` | 固定名稱表與 `content/entities/player` 相符 |
| handle 呼叫 | `0x10868BF` | accepted path 的間接 handle 方法 |
| player callback | `0x10868D7` → `0xFDC140` | accepted path 的資源／元件分派 |
| roster 呼叫 | `0x10868F1` → `0x608B60` | accepted path 後續 roster 處理 |
| 4–7 分支 | `0x108624D` | 只寫 32 筆 ring；此 root 無 player-resource 呼叫 |

因此只把 gate 的 `4` 改成 `8` 仍不足以建立第五至第八個角色；必須把 index `4..7` 導入等效資源、元件、roster、清理與重連流程。

## 固定四人讀者／護欄清單

下列是目前已有完整 bytes／ABI 證據的容量相關位置。相同函式中其他立即值 `4` 可能是狀態碼或參數值，沒有列為容量護欄。

| RVA | 類別 | 目前行為 |
|---|---|---|
| `0x1086460` | client player 建立 | network index `>=4` 拒絕 accepted resource path |
| `0xB9014B` | index→slot | 映射結果要求 `<4` 才進另一個 slot dispatch |
| `0x13951A9` | reverse lookup | 只搜尋 index `<4` |
| `0x1092ECB` | session member helper | 平台回傳 member count clamp 至 4 |
| `0x1093C91/0x1093C96` | session update | member count clamp 至 4 並寫入 `owner+0x1BB0` |
| `0x1093CB0/0x1093D1E` | session update | 兩個平台列舉 ABI 收到容量 4 |
| `0x51AC89` | component 33 | `count+1 <= 4`，超限走零位址分支 |
| `0x51BB6E` | component 41 | 同上 |
| `0x51C133` | component 43 | 同上 |
| `0x53E1CC` | component 226 | 同上 |
| `0x54067C` | component 238 | 同上 |
| `0x54093C` | component 239／roster | 同上 |
| `0x5432C9` | component 250 | 同上 |

參考 player 資源的 component 3 與 260 走物件欄位／helper 容量路徑，不能因沒有 `cmp ...,4` 就算八人安全。

## 直接實作結論

1. `0x1086460` 的 gate 需要 sidecar／continuation 方案，保留 invalid index、缺失 peer 與 sentinel 的拒絕語義。
2. 七個 component callback 不可直接把立即值 `4` 改成 `8`：原 pointer 陣列與後續輔助記錄在槽位 4–7 有重疊，必須移到統一 owner-keyed 8-slot backing。
3. Session update 的四個容量位點與其餘狀態／參數立即值必須分開處理；現有 sidecar adapter 對部分修改保持 fail-closed。
4. 真正可安裝的 hook 還缺 receive dispatcher／resolver、owner lifetime、cleanup／unwind ABI；本審計不把離線證據當多人成功。

重播：

```powershell
python five_player_feasibility_20260927/player_creation_chain_audit_20261002.py --output five_player_feasibility_20260927/player_creation_chain_audit_20261002.json
$env:PYTHONPATH='five_player_feasibility_20260927'
python -m unittest -v five_player_feasibility_20260927/test_player_creation_chain_audit_20261002.py
```

輸出 JSON 的 `runtime_verified` 與 `multiplayer_verified` 固定為 `false`，直到有對應的授權實機證據。
