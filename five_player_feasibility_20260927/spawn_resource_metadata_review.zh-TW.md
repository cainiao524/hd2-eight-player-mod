# 資源 metadata 的獨立審查

審查對象為 [spawn_resource_metadata_replay.py](spawn_resource_metadata_replay.py) 及 [spawn_resource_metadata_evidence.json](spawn_resource_metadata_evidence.json)。沒有修改這兩個檔案、主要報告或遊戲安裝檔；沒有查詢或讀取活程序。

審查時 evidence JSON 的 SHA-256：

`400bd47c3d75928695f76b64591d56c699ab725581b4d068071c5f293b07cd2a`

## 結果

**未發現可重現的解析數值、保存位元組或指令邊界錯誤。** 目前三個 `installed_asset_equivalence_verified`、`runtime_component_selection_verified`、`eight_player_verified` 均為 false，符合實際證據範圍。

### 1. Reference 檔解析

已核對 evidence 所列七個來源檔案 SHA。Bundled gzip 解壓結果與 bundled plaintext **逐 byte 相等**。

獨立重算沒有匯入 replay 的 parser：從每一筆下一個 `LDLD` magic 相對位置決定是否具有額外 4-byte index，驗證 28-byte header、版本、64-bit 旗標、填充、大小與檔案邊界，直到檔尾。得到：

- **272** 筆 instance。
- 其中 **270** 筆帶有 component index，索引未重複。
- 首筆為 `EntitySettingsHashmap`（`0x80C1CA70`）。
- 4,096 個 32-byte table slots 中有 **1,909** 個非空 resource records。
- 三個指定 resource 的 record bytes、list offset、count、list bytes 及每個 u16 index 都與 evidence 相符。

| Reference resource entry | 列表長度 | 列表含 239 |
| --- | ---: | --- |
| `content/entities/dummy` | 1，列表為 `[88]` | 否 |
| `content/entities/player` | 9，列表為 `[3,33,41,43,226,238,239,250,260]` | **是** |
| `content/fac_helldivers/cha_avatar/avatar_helldiver` | 49 | 否 |

FileDiver 的 `EntitySettings` 結構與本次解析一致：64-bit resource hash、64-bit list offset、64-bit count、32-bit game-object 欄位及 4-byte padding。列表 offset 相對於 instance body；不是相對於整個檔案，也不是直接執行期指標。

### 2. 捕捉的指令與字串

**111 筆／111 個不同指令位置**都與固定舊捕捉的原始 bytes、SHA-256、asm 及 root 相符。每個位置由其 unwind fragment 起點連續解碼核對邊界，沒有用隨意地址直接解碼替代。

兩個字串的原始 bytes、終止零、摘要及文字均相符：

- `0x225D2A0`：`generated_entities.dl_bin`
- `0x225D2F0`：`generated_entity_deltas.dl_bin`

Loader 字串及選擇 u16 callback index 的程式形狀支持「這一類 metadata 的載入與使用方式」。它們沒有提供目前活程序中 metadata 的實際內容。

## 必須保留的限度

### 沒有 data-bearing instance，不代表沒有元件

270 筆帶 index 的 reference instances 中沒有 **239**，因此 `component_239_data_type=null` 是正確結果。然而，同一 reference snapshot 的 player resource list **明確包含 239**。

正確敘述是「本檔没有提供 index 239 的 data-bearing type 映射」。不能改寫成「玩家沒有 index 239 元件」、「該元件不存在／未儲存」或「該 callback 不會執行」。沒有另行資料 instance 可以與只需程式狀態、無此處序列化參數的元件相容，但具體原因尚未證實。

### Reference snapshot 尚未對應到 installed／runtime

Bundled `.gz` 與 bundled plaintext 相等，證明的是 **FileDiver 工作區內兩份 reference 內容**的關係。

目前對 installed encrypted 檔只有 hash 與 length，沒有解密或執行期 metadata 比對。加密內容與 plaintext 的 hash／length 即使不同，也不能據此推斷解密後內容相同或不同。因此不能宣稱：

- 當前安裝版 player resource 恰有九個相同元件。
- 當前 runtime 一定會為 player 選擇 callback index 239。
- 當前 avatar resource 一定不會經其他流程涉及 239。

以上三個列表結論都應加上「在這份 bundled reference entry 中」。已保存的 loader／consumer 指令提供格式和流程上的支持，仍不能替代內容版本等價或實際 callback 執行證據。

### 不是玩家容量

4,096 table slots、1,909 resources、272 instances、270 data-bearing instances，以及 1／9／49 個列表索引，都是 metadata 的不同計數。它們不能解讀成多人遊戲人數上限。這份結果也未解析 component 239 的所有狀態容量，沒有完成八人 Mod 或連線驗證。
