# 本地 player 建立 gate 的獨立審查

## 審查結論

**通過本次限定範圍的審查，沒有發現推翻核心結論的問題。** 從固定原始捕捉重新解碼並獨立重建正常 CFG 後，確認 `0x1086469 → 0x108646F` 的 accepted 邊支配此函式內的 handle 呼叫 `0x10868BF` 與唯一直接 `FDC140` 呼叫 `0x10868D7`。從 fallback `0x108624D` 出發無法到達兩者，但可到達共同的 ready-helper 呼叫點 `0x108643C`。

此結果支持原 findings 所限定的判斷：**索引 4–7 沿這個正常加入路徑會跳過它的本地 player 資源處理呼叫，因此必須讓這些索引得到等效建立流程，不能只放大外部房間人數。** 它不證明只改 `<8` 已足夠，也不證明全遊戲不存在其他建立／沿用 entity 的路徑。

本次只新增本審查文件；未修改受審查 JSON、replay、findings、總報告或遊戲。未讀活程序，未新增捕捉。

## 1. 受審查對象與原始來源

- `local_player_creation_gate_evidence.json` SHA256：`d101ffbca1faa03318de87424acdfafee58a0d3b86f4f51e9216244a0f5c166a`。
- `local_player_creation_gate_findings.zh-TW.md`。
- 同名 replay 腳本僅作為被審查實作閱讀；独立核對沒有呼叫它的 CFG／reach 函式。
- 原固定捕捉目錄：`C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438`。
- 原 `capture-report.json` SHA256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- 原 `captured-data.bin` SHA256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- 主函式 bytes `[0x1085D70,0x108691D)` SHA256：`19eba7cca1190ffa03ef66e3d92ec0cdf9a3ccdd769253013bdf69041490fe65`。

所有位址均為固定 game.dll 捕捉的 RVA。本次使用既有 `Image` 讀取器檢查來源雜湊、解讀保存的 unwind 表與讀取原 bytes；未將受審查 JSON 的 CFG 主張當成證明。

## 2. 獨立核對方法與數量

1. 由原保存 unwind 表重新列舉 root `0x1085D70` 的 fragments；確認其六段與 JSON 相同且相連。
2. 每段由入口完整解碼，核對解碼 byte 數等於段長。
3. 對全部 565 條指令逐條比對 RVA、原始 bytes、指令 bytes SHA256 及 mnemonic／operands。
4. 以重新解碼的指令建立自己的 successor map：return 無後繼；直接 jump 只到目標；條件 jump 同時包含目標與 fallthrough；其他指令走下一條。所有邊必須落在本函式已解碼的指令入口。
5. 使用獨立 DFS 重算主入口、accepted、fallback 與刪除 accepted 邊後的可達集合。
6. 額外核對 JSON 的 extra pins、保存字串及完整 ready helper 原 bytes；ready helper 257 bytes 全部成功解碼。

核對結果：

| 項目 | 結果 |
| --- | --- |
| 相連 unwind fragments | 6 |
| 主函式指令 | 565 |
| 正常 CFG 從主入口可達指令 | 565 |
| jump 指令 | 36 |
| 正常 CFG edges | 595 |
| 主函式 call 指令 | 28 |
| 直接 `call FDC140` | 1，位於 `0x10868D7` |
| 主函式未解析的 indirect jump | 無；間接 call 依正常返回建模 |

## 3. Accepted 邊支配關係成立

原 bytes 確認：

```text
108645C  shl rdx,5
1086460  cmp dword ptr [rdx+r8+163AC],4
1086469  jae 108624D
108646F  accepted 起點
```

`0x1086212` 先取得 owner 全域 `0x347CEF0`，讀 confirmed 記錄 count；`0x1086228` 取 owner+0xB398 的本地 peer ID。`0x1086238` 在每筆步幅 `0x20` 的記錄比較 peer ID，匹配才到上述 gate。因此 gate 所比較的是匹配記錄的 `+0x14` DWORD（owner+0x163AC），不是該筆記錄的 ordinal／count。

獨立 DFS 結果：

| 主張 | 結果 |
| --- | --- |
| 主入口可達 `10868BF` handle call | 是 |
| 主入口可達 `10868D7` setup call | 是 |
| 刪除 `1086469→108646F` 後可達 handle call | 否 |
| 刪除同一邊後可達 setup call | 否 |
| fallback 可達上述任一呼叫 | 否 |
| accepted 可達 fallback ring 起點 | 否 |

主函式 accepted 區間唯一的條件跳轉是 `0x1086801` 的複製迴圈。`0x10867A5` 把 EDX 設成 6，迴圈內無 call 或其他 RDX 改寫，`0x10867FD` 每次減 1，因此在無異常的正常執行下為固定六次迴圈，不能構成另一條跳過 handle／setup 的分支。

在 `0x10868BF` 返回後，`0x10868CC` 將 EAX 放入 EDX、`0x10868D5` 保留於 EBX；`0x10868C9` 將先前載入的 hash `0xCDC1F82CE3337A82` 放入 R8，接著直接呼叫 `0xFDC140`。隨後 `0x10868EF` 將 EBX 放入 EDX 交給 `0x608B60`。所以 findings 所述同一 handle 值前後傳遞由直接資料流支持。

此圖仍採原 findings 已明列的「被呼叫函式正常返回」條件，不涵蓋例外、非局部跳轉、任意中途入口或執行期改寫。

## 4. Fallback 與共同 ready 流程

### Fallback ring 寫入解讀正確

核對 `0x108624D..0x10863A9`：物件來自全域 `0x346D560`；`0x10862A7/0x10862AC` 寫入 16-bit type 3；目的地址使用 `queue+0x200+writeIndex*0xE8`；`0x1086397` 將下一寫指標與 `0x1F`；追上讀指標時，讀指標同樣遞增並与 `0x1F`。这支持 32 個儲存位置的 ring 寫入，不能把 32 當成玩家容量。

沒有追查該 ring 的消費者，原 findings 也沒有把 type 3 命名成特定 UI／錯誤訊息，範圍合理。

### 共同尾部可達，不保證已送出 ready

Accepted 的 `0x1086918 jmp 0x10863AF` 和 fallback 的順序後繼確實合流。`0x1086401` 的 `0x1086920` 呼叫建立／取得的是 client+0x40 的 16 bytes peer 同步記錄；本次亦核對其記錄地址計算和寫入，沒有第二個直接 `FDC140`。

`0x1086412` 使用 `[rsp+0x40]` 保存的原 entry sender 比較本地 peer 值，**不是使用 accepted 路徑稍後改成 handle 的 EBX**；因此 sender 判斷沒有被 handle 暫存覆寫。比較不相等時 `0x108643C` 才呼叫 ready helper。

`0x1086B70` 只有在 peer 同步記錄全部清除後，才進入發送段；其中字串、`0x37FF1AA7` hash、owner+0xB3A8 目的 peer 與可將 client+0x1D0 設成 5 的指令，均與原 bytes 一致。原文使用「可到達／條件成立時」，沒有把 CFG 可達誤寫成必然發送。

## 5. 必須保留的結論邊界

以下是本次支持的結論所依赖的範圍，不是新增阻擋問題：

- **「Fallback 未建 player」應保持完整限定語**：它不執行此 root 唯一的直接 player 資源處理呼叫。主函式 28 個 calls 並未全部展開，這份 CFG 本身不能證明全遊戲／所有下游絕無建立、沿用或已存在的 player。
- **Ready 是可繼續的流程，不是建立成功訊號**：兩支都可到達 ready-helper call；sender 條件與同步記錄狀態仍可讓 ready 不送出。
- **通過 gate 不等於資源成功建立**：handle／setup 的成功語義及後續元件狀態未在此驗證；對索引 4–7 提供等效建立只是一項必要條件。
- **Unsigned sentinel 行為不能消失**：原 `jae` 也拒絕 `0xFFFFFFFF`；單純移除檢查會擴大到不合法索引，不能從本次結論推出無條件跳過 guard。
- **固定捕捉只證明該映像程式**：不代表目前執行版本、動態 callback tables 或 installed metadata 與保存資料完全等價。

受審查 findings 已表達上述核心範圍，因此本次沒有要求修改其結論，也沒有擴大探索其他遊戲入口。
