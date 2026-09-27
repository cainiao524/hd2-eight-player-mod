# roster network index 下游用途：tag DA 容量衝突與可保留預設路徑

後續更新：本頁原先列為容量未知的 `7275FA → 14335F0` 已接到同一物件的初始化與清理，確認四筆區域及 index 4／7 的相鄰欄位衝突。最新結論見[雙 float 儲存續查](indexed_float_storage_findings.zh-TW.md)；以下保留原支線的限定搜尋範圍。

## 範圍與結論

本次只讀取固定離線 `game.dll` code / readonly / unwind capture，透過 `inspect_capture.Image` 驗證來源 SHA；沒有查询或讀取活程序、執行遊戲函式、新增 probe、安裝或修改遊戲。所有位置是此固定版本的 RVA。`roster+0x3B4` 已由前一份 component binding 證據定位為 0x20-byte record 內的 network index；它不等於 roster ordinal。

**新增一個確定需要重排儲存的下游：tag `0xDA` 子物件的四筆 `0x90`-byte 記錄。** 程式從已確認的 roster global 讀取 network index，未檢查 `<4` 即按 index 寫入。若輸入 index=4 且該程式區塊執行，會精確覆蓋父物件已使用的 `+0x318` qword 和 `+0x320` bitset；這比「沒有初始化第五格」更具體。

這是**靜態條件推導**。本研究沒有觀察第五名玩家觸發這條路徑，也沒有證明目前遊戲能產生這項輸入。函式內其他流程條件及真實可見症狀仍未做執行期驗證。

## 1. 同物件來源證明

令父物件為 `P`，子物件為 `S`：

1. `AC5D6B` 將 entry `RCX` 保存為 `R12=P`；`AC5D78` / `AC5D6E` 使用 readonly 字串 `StateGame` / `On Enter`。這是父物件的除錯名稱關聯，並未替 tag DA 猜測具體類別名稱。
2. `AC5D96` 讀 registry global `0x3326E68`。`AC5D9D` / `AC5DA1` 建立 `(P, tag=0xB5)` pair，`AC5E42..AC5E5F` 把該 pair 加入 registry `+0x24F8` 的 16-byte 表。
3. `B61E6A` 讀同一 global，`B61E85..B61E92` 檢查同表 entry 的 `0xB5` tag，`B61EA8` 取回同 entry 指標，`B61EB0` 傳给 `AD4520`。
4. `AD455E` / `AD4561` 保存 `P`。函式中途借用 `R13`，但 `AD488A` 從 `[rsp+0x68]` 恢復 `P`。`AD4C1A` 形成 `RCX=P+0x50`，`AD4C25` 呼叫 `FFD8C0`。
5. `FFD945` 保存 entry 指標 `S`，`FFD948` 註冊 tag `0xDA`；因此 **`S=P+0x50`**。

另有 `AB3138..AB3142` 將 outer `+0x1FA08` 傳給 `AC5D40`，與後述 `12A9CAC` helper 的父物件位置一致。父物件除錯事件字串也包含 `on_synchronized_tasks_done`，但它不等於每一局必定執行此呼叫的證據。

## 2. tag DA 四格結構及第五格的精確衝突

### 原本初始化

`FFD8C0` 的初始化流程：

| 指令 | 已確認用途 |
|---|---|
| `FFDA04` | `R15=S+0x80`，第一筆記錄 |
| `FFDA3E..FFDA43` | 保存平行 dword 陣列指標 `S+0x70` |
| `FFDA48` | 記錄 counter 從 0 開始 |
| `FFE379..FFE37C` | 每輪清零一個平行 dword、指標前進 4 |
| `FFE36A..FFE3AE` | 初始化記錄內旗標、數值、handle 衍生字段 |
| `FFE3B6` | 記錄指標前進 `0x90` |
| `FFE3CC..FFE3D0` | counter `<4` 才繼續 |

所以已初始化的記錄範圍為 `S+[0x80,0x2C0)`，亦即 `P+[0xD0,0x310)`；平行四個 dword 是 `S+[0x70,0x80)`。

### network index 被直接用作陣列下標

`FFE3D6` 明確讀 `global[0x3326468]` 作為 roster。`FFE3E5` / `FFE43A` 以 `roster+0x84` 的 count 控制迴圈；`FFE3FB` 將 ordinal 乘以 `0x20`，`FFE3FF` 讀 `roster+ordinal*0x20+0x3B4` 得到 network index `n`。`FFE407..FFE412` 計算 `18*n`，之後使用 scale 8，即 `0x90*n`。

此段沒有 `n<4`、sentinel 或有效槽位檢查。

| 寫入指令 | 寫入位置 | 寬度／值 | 若 `n=4`，相對父物件的位置 |
|---|---|---|---|
| `FFE415` | `S+n*0x90+0x88` | byte 0 | `P+0x318` |
| `FFE41E` | `S+n*0x90+0x8C` | dword `5.0f` | `P+0x31C` |
| `FFE42A` | `S+n*0x90+0x90` | dword 0 | `P+0x320` |
| `FFE432` | `S+n*0x90+0x89` | 保存的 boolean | `P+0x319` |

相鄰位置並非可自由使用的 padding：

- 在同一父物件初始化 `AC5D40` 中，`AC67EB..AC67F2` 將 outer `+0x10E8` 的 qword 存入 **`P+0x318`**。
- `AC6802..AC6856` 用 `BTS` 和 `POR` 組合資料，最後將 **16-byte bitset 存入 `P+0x320`**。
- 因此第五個 network index 的四次寫入會分別打到該 qword 的低位 byte、高半 dword、第二個 byte，以及 bitset 第一個 dword。

這些指令是同一條父子物件來源鏈的實際字段使用，並非僅以相同位移比對不同物件。

### 八人修改的具體範圍

要提供八筆同等資料，主陣列需容納 `8*0x90=0x480` bytes，平行陣列需 `8*4=0x20` bytes；比目前多 **`0x250=592` bytes 的邏輯記錄內容**。這不是已證明的最小 allocation 大小，尚不包括 alignment、重新指向資料的資訊或其他子系統。

不可只把初始化比較值 4 改成 8：

- 主陣列保持原位置會延伸到 `P+0x550`，蓋過上述已使用欄位。
- 平行 dword 陣列保持 `S+0x70` 並增加四項，會延伸到 `S+0x90`，與主陣列 slot 0 的 `S+0x80` 開始區域重疊。
- 實作需要重排或另設兩個陣列、修正已定位的 writer、initializer 和 reader，然後才調整索引邊界。這次沒有聲稱已窮盡所有這兩個陣列的讀寫入口。

## 3. 其餘已證明同來源的消費者分類

| 路徑 | network index 來源 | index 4–7 的行為 | 八人方案判斷 |
|---|---|---|---|
| `12A9C80 → ACF420` | `global3326468`，經 roster entity map 得 ordinal，再讀 `+ordinal*0x20+0x3B4` | `ACF43F..ACF446` 在任何 slot 存取前回傳 `AL=0` | **某項狀態／向量操作不提供第五格。** 若要等同前四格，需要配合 tag DA 儲存擴充；不是已證明的加入拒絕 |
| `ACA58B → ACF1F0` | 直接讀 `global3326468+0x3B4`，是第一筆 roster 記錄內保存的 network index | unsigned `>=4` 走預設 12-byte 向量；有效 index 才讀 `n*0x90` 字段並正規化三個 float | 可暫保留有界預設路徑，不會在此越界。若需要每位玩家的等同向量結果，仍需擴充 |
| `1277A06 → 1277A2F` | 同 roster global 和 `+D0/D8/DC/E0` map，取得 ordinal 後讀 `+3B4` | 在另一系統的 dword masks 上執行 `bt eax,r8d`；排除 `FFFFFFFF`，沒有 `<4` 限制 | **此 consumer 的 32-bit 寬度容得下 bits 4–7**；沒有證據要求加寬它，但 mask producer 是否建立那些 bits 尚未知 |
| `606AD0 → 606B6B` | 同 roster global 和 map，取得 ordinal 後讀 `+3B4` | 純量返回原值，map 缺項回 `FFFFFFFF`，無四人 clamp | 不需為這個 getter 的純量寬度做修改；若 roster 陣列位置改動仍要修正地址 |

### 操作拒絕與預設值的限制

`ACF420` 的有效分支明確將 `P+0x50` 變成 `S`，計算 `S+0x80+n*0x90`，讀寫向量與狀態旗標並呼叫其他函式；其 index `>=4` 早返 `false` 有實作影響。然而已固定的 caller 在 `12A9CAC` 後沒有檢查 `AL`，而是繼續取另一項資料，因此不能據此推論「第五人加入被拒絕」。尚未賦予這項操作具體遊戲功能名稱。

`ACF1F0` 的預設資料來源是 `0x32A8E60` 和 `0x32A8E68`，**位於此次 capture 未涵蓋的 writable globals**；不知道它是零向量或其他值。此處只證明有界回傳預設值，不保證第五人的遊戲行為可接受。

前一份 `roster_component_binding_evidence_v3.json` 的 `6054F0` 四色表白色 fallback 仍獨立成立，本次沒有重做該分支。

## 4. 唯一保留的未收束陣列入口

`72757E/7275B1` 讀取同 roster global；`7275D0..72760E` 以 count 迭代，`7275D6` 讀 network index，將其放入 `EDX` 呼叫 `14335F0`。該 callee 在 `1433614` 計算 `index*0x298`，`143362F` 將兩個傳入 float 合併成 qword 寫至：

```text
destination + network_index*0x298 + 0x80E24
destination = caller.RSI + 0x4C8260
```

寫入前未見索引範圍檢查。**尚未證明 destination 的可容納項數、相鄰欄位或 UI 語義**，因此不把它列為已證實的另一處四格越界，也不將它當作完成八人容量審核的證據。它是後续有需要時可直接接手的一個具體容量審核入口；本輪沒有擴散成更多候選清單。

## 5. 重放与產物

- `roster_index_usage_replay.py`：只讀固定 capture；建立 11 組證據，驗證指令邊界、關鍵 global、call edge、關鍵指令與 readonly 字串。
- **`roster_index_usage_evidence_v2.json`：目前版本，共 523 條唯一指令。SHA-256 `d7098a7d698aa7daaf53e89c08b19cb01e243860f70fbba518690837baf121ee`。**
- 初版 `roster_index_usage_evidence.json` 保留作過程記錄；v2 追加父指標恢復與 zero-register 控制流程證據。
- `roster_index_usage_field_scan.json`、`roster_index_usage_candidates.json`、`roster_index_usage_slot_system_scan.json`、`roster_index_usage_ctor_xrefs.json`、`roster_index_usage_parent_xrefs.json` 為篩選過程。掃描命中數不可當成已確認 roster 讀者數；最終認定以 replay 的基底來源鏈為準。

重放命令（output 必須是尚不存在的檔案）：

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  five_player_feasibility_20260927/roster_index_usage_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/roster_index_usage_recheck.json
```

本次未修改總報告，未檢查另一支線正在處理的 component 239 其餘 wrappers，未宣稱八人聯機已可運作。
