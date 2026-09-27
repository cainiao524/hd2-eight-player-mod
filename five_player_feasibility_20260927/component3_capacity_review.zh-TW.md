# 元件 3 容量證據：獨立審查

## 審查結果

**限定範圍通過，沒有發現需要阻止容量結論整合的錯誤。** 本審查確認 component 3 的已捕捉初始化／追加／搬移路徑採 512 筆資料容量與 1,024 個 map buckets；沒有把固定四筆儲存改八的必要證據。此結論不能擴充成所有下游或八人聯機均安全。

被審查檔案：

- `component3_capacity_replay.py`
- `component3_capacity_evidence.json`
- `component3_capacity_findings.zh-TW.md`
- 正式 evidence SHA-256：`1ed27a70a2a1662c3e324c774da877687ae0388d54fe4320e94057f07fd14330`。

## 核對方式

1. 使用固定 capture 重新執行作者 replay，輸出 `component3_capacity_review_recheck.json`。
2. 重播檔與正式 JSON **逐 byte 完全相同**，SHA 相同。
3. 另用 capture reader 獨立核對 11 個 roots 的完整 unwind fragment 清單；797 條指令逐條比對原 bytes、已證 instruction boundary 及 mnemonic／operands，全數相符。
4. 獨立閱讀配置、grow、copy/map 修復和每 entity tag 迴圈的資料流；沒有只採用作者摘要或以重播成功代替語義審查。

capture 身分：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。全程只讀儲存檔，沒有程序查詢、live read、新擷取、patch 或執行遊戲函式。

## 核對項目

| 項目 | 獨立核對結果 |
|---|---|
| index 3 身分 | registration slot `F0C110+3*8 → 516540`，該函式取 global `3326430`；publication `56825E/568265` 對應 `owner+E8` |
| owner 邊界 | 下一 member `owner+128`，描述區 `0x40` bytes；資料透過 heap pointers，沒有把陣列 inline 接到下一 member |
| 初始化 | `6B576A` 寫 capacity `0x200=512`；`+30` 與 `+38` 兩個 qword 陣列，各要求 4,096 bytes；map backing 1,024 pairs，共 8,192 bytes |
| Map descriptor | 擁有 backing 在 `+10`，descriptor pointer `+18`；bucket count `+20`、sentinel `+24`、multiplier 2 在 `+28` |
| 追加前檢查 | `516557` 比對 map capacity，`516567` 比對資料 capacity；必要時先呼叫各自 grow helper，再追加 |
| 資料增長 | `6B5C90` 的常數是 double 256.0；有限正整數 path 結果仍為 256，再加舊容量，寫 `S+0` |
| 兩組 backing 同步重配 | `6B5D04` 更新 `+30`，`6B5D65` 更新 `+38`；兩邊都以 `new_capacity*8` 要求配置，並將 `old_capacity*8` 傳給 copy helper |
| Map 增長 | `6B5A90` 以 0.5 比例計算增量、加原容量再向上取 2 的冪，遍歷非 sentinel 舊 buckets 重新插入 key 與 ordinal；1,024→2,048 的例子成立 |
| 搬移 | `6B5620` 複製 `+30` entity qword 及 `+38` tag qword；`6B56D2` 將搬入 entity 的 map value 改成 destination ordinal |
| `0x40` 迴圈 | `5166D4..516719` 對同一 entity 的 tag input 作多個 qword OR，EDI 每輪加 4 並比較 64；不是玩家數限制 |
| 未證初始值 | 文件保留 `S+4` high-water 未由此 constructor 證明初始化；沒有誤把所有 header 欄位都稱為清零 |

## 結論的必要界限

- 容量涵蓋該元件的 entity membership，沒有證明是玩家專屬配額，也没有執行期佔用量。
- 外部配置／釋放介面沒有解析或執行，CRT copy helper 全部實作沒有重審。靜態配置大小與呼叫順序不等於當前執行期配置成功。
- `21012E4` leaf 的正整數位元計算足以支持本輪 256／512 等容量例子；NaN 外部尾跳不應被敘述成已完成數學函式全域驗證。
- map lookup／搬移假設正常、有效的 entity membership；這份容量證據沒有保證 malformed ID 或 ordinal 安全。
- 其他 global consumers、併發、完整生命週期和 installed/runtime metadata 等價性未窮盡。作者的 findings／evidence 已保留這些範圍限制。

**整合建議：** 在八槽必要原生修改清單中，component 3 可標成「已核對路徑保留既有容量與增長機制；不需四槽改八槽」。不要把它標成已完成八人功能驗證。
