# Player 元件容量的獨立審查

審查對象為 [player_component_capacity_replay.py](player_component_capacity_replay.py)、[player_component_capacity_evidence.json](player_component_capacity_evidence.json) 及 [findings](player_component_capacity_findings.zh-TW.md)。先行比對了 callback disassembly 與 registration pairs 探索檔；正式審查再回到固定原始 capture。沒有修改上述檔案、主要報告或遊戲檔案，沒有讀取活程序。

審查時 evidence JSON SHA-256：

`4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147`

## 結果與已完成的措辭修正

**沒有發現數值、callback 對應、原始 bytes 或儲存重疊算術的阻擋問題。** 九個 callback 共 **428 條指令**及選定的 **18 條 registration 指令**，都與固定捕捉一致。

一項精度問題已回報 root 並在 findings 修正，審查已重讀確認：component 43 的 `0x51C110` **沒有 creation params 首 byte 的分類分支**，會直接走共用初始化。因此不能把所有元件都描述為「有兩類成功分支」或「guard 在該分類條件之前」。成稿現在精確區分為：

- 對有 params 首 byte 分類的入口，四筆檢查在分類之前。
- 43 沒有此分類分支，`0x108` 記錄在共用路徑清零。
- 33／238 的兩個分類分支合流後都清零；41 的大記錄與 250 的記錄清零則受該 byte 控制。

這項措辭不影響四筆 guard 或重疊結論。

## 指令邊界與登錄來源

各 callback 都從其已保存 unwind fragment 起點解碼至結尾，完整長度、SHA、每條 bytes 及 asm 相符。

Registration initializer `0x556D90` 本身沒有 unwind。審查先以有 unwind 的 **`0x568239 → 0x556D90` direct call** 證明入口，再完整解碼其 4,255 條指令至 `ret`，從已證明邊界抽出選定的 LEA／store。沒有將 registration 的任意 bytes 當成函式入口。

新增五個元件的 slot 與 callback 一致：

| Component index | `0xF0C110 + index*8` | Callback |
| --- | --- | --- |
| 33 | `0xF0C218` | `0x51AC70` |
| 41 | `0xF0C258` | `0x51BB50` |
| 43 | `0xF0C268` | `0x51C110` |
| 238 | `0xF0C880` | `0x540660` |
| 250 | `0xF0C8E0` | `0x5432B0` |

九個 callback 的 global 來源及七個 guard 亦重新核對。Guard 的連續機器碼確實是讀取對應 dword 計數、`inc eax`、`cmp eax,4`、`jbe` 跳過 `mov DWORD[0],0`。這是低 32-bit 加一及 unsigned 比較；在正常小計數域具有四筆護欄。沒有把整數繞回或例外處理視為合法第五人入口。

## 重疊計算確認

以下 `i` 均為**元件儲存的零起算索引**；`i=4` 是第 5 筆。它與 network index 沒有被假設成同一值。

| 元件 | 已驗算的衝突 |
| --- | --- |
| 33 | Pointer `0x70+8*4=0x90`，跨度 `[0x90,0x98)` 不碰 record base `0x98`；此 gap 的其他用途未查明。`i=5` 的 pointer 起點才是 `0x98`，直接碰 record 0。 |
| 41 | Pointer `0x68+8*4=0x88` 直接碰大 record 0。大 record `0x88+4*0x9928=0x26528`，恰是第二組 `0x58` stride records 的基底。 |
| 43 | Pointer `0x68+8*4=0x88`，碰 `0x108` stride record 0。 |
| 238 | Pointer `0x948+8*4=0x968`，8-byte span `[0x968,0x970)` 與 record base `0x96C` 重疊 **4 bytes**。 |
| 250 | Pointer `0x70+8*4=0x90`，碰 `0x34` stride record 0。 |

五個 pointer store 都在各自成功路徑的共同後段，不能因某個較大 record 的清零受 params 控制，就認為 pointer overlap 也被排除。

幾個元件先以另一計數選擇分類插入位置，必要時呼叫 helper。因此「第 5 次加入呼叫」不必然直接寫 `i=4`；也可能先搬移原資料。文件目前使用「若擴容後仍使用原布局的 slot 4–7」的表述，符合證據。

## 證據界線

- Reference player 的九個索引與原始 reference bytes 一致；這份 reference 清單尚未證明等於目前 installed encrypted 檔的解密內容或實際 runtime 清單。
- Callback 對應是已確認的靜態初始化；未觀察 runtime table 是否仍保留該值、實際元件選擇或 callback 執行。
- 參考 data type 名稱不能直接當成已獨立命名的 native manager。對 226／238／239 沒有 data-bearing 名稱，不能推成沒有元件。
- Component 3／260 使用物件內欄位容量與 helper；沒有完整分析 helper，不能稱為 unlimited 或八人安全。
- Helper 內部的搬移、移除、重設及其他 consumers 尚未全部解析；本審查沒有擴大調查這些支線。
- 指令中包含零位址寫入，不等於本次實際觸發過崩潰；没有五人或八人 runtime 驗證。

因此，證據支持把新增五個元件列入共同擴容範圍，並否定「只放寬七個常數就維持原布局」的實作假設；它尚未給出完整可套用的 native 修改方案。
