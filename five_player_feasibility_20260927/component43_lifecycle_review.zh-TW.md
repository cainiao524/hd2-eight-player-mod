# 元件 43 生命週期證據：獨立審查

## 結果

**通過限定範圍審查，未發現需要修正的布局、壓實或 owner 別名結論。** 原始捕捉支持元件位於 owner+0x2A988、下一成員位於 owner+0x2AE30，四筆記錄恰好填滿 0x4A8 span；也支持單向完整記錄壓實與不經元件 global 的兩個 owner 存取。

受審查：`component43_lifecycle_evidence.json`、`component43_lifecycle_findings.zh-TW.md` 及同名 replay。JSON SHA256：

```text
e0e3f9fcfec8359eb3f777a7537a2c53d8635cc1c754d1318c34938b12e22cb9
```

本次只新增本 review，沒有修改受審查檔案或總報告；沒有讀活程序、新捕捉、安裝或修改遊戲。

## 方法與來源核對

沒有執行或呼叫被審查 replay 的內部函式。使用既有 `Image` 原始捕捉讀取器重新驗證來源 SHA／unwind table，對 JSON 所列每個 root 從原 unwind 表独立枚舉**全部** fragments，核對與 JSON 的 fragment 集合完全一致，再由各 fragment 入口完整解碼。

逐條核對 RVA、bytes、instruction SHA256、mnemonic／operands；所有 fragment hash、owner pins、diagnostic 字串也與原始保存 bytes 一致。Initializer 的三個 index 43 賦值和七個缺少賦值的 slot，另由完整 initializer 解碼重新找出，沒有把 JSON 的 null 當成 runtime 值。

- **11 個 roots，共 550 條函式指令。**
- 加上 owner 選定片段為 **614 個不同指令位置**；數字不含三組登錄的 6 條指令，與 findings 相符。
- 原 `capture-report.json` SHA256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- 原 `captured-data.bin` SHA256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

## 1. 邊界與容量算術成立

`568464/56846B` 將 owner+0x2A988 發布到 global3326AF0；`568472/568479` 發布下一個 owner+0x2AE30。Constructor `5528CA/5528D4` 對下一成員呼叫獨立 helper，足以區別真實下一成員與僅推測的記憶體尾端。

独立重算：

```text
0x2AE30 - 0x2A988 = 0x4A8
0x88 + 4*0x108   = 0x4A8
```

若保留原 header／hash 布局，八個 pointers 使記錄起點變成 `0x68+8*8=0xA8`；八筆記錄末端為 `0xA8+8*0x108=0x8E8`，資料增量 `4*(8+0x108)=0x440`。這與 findings 一致。原文已說明它只是布局算術，沒有當成完成的配置或補丁。

Constructor 將 `S+0x50` 指向 `S+0xC`，後者八個 8 bytes buckets 結束於 `S+0x4C`。Header 從 `+0x50` 開始，中間四 bytes 沒有被錯算成 bucket 9；整塊搬遷時 header pointer 必須重新指向新位置的內嵌儲存。

## 2. `9BA8D0` 確為單向完整壓實

參數資料流經原始 bytes 確認：RCX=S，EDX 為目的 ordinal（保存到 ESI），R8D 為來源 ordinal；若相等直接返回。

- `9BA8F8` 讀來源 entity pointer，`9BA8FD` 寫目的 pointer。
- 兩個 ordinal 各乘 `0x108`，定位來源 RAX／目的 R9。
- `9BA919` 設 ECX=2；每輪八次 16 bytes 複製，`9BA976` 減一，合共 `2*0x80` bytes。
- `9BA97C/9BA97F` 再拷貝最後 8 bytes，總長精確為 `0x108`。
- `9BA982..9BA9E2` 從搬入目的的 entity 讀 ID、查 map，最後 `[entry+4]=ESI` 更新目的 ordinal。

沒有雙向交換或清零來源槽。完整 `51C1A0`／`9BAC20` 也確認先經 `172F8A0` 刪除 ID，再依 `+8` 分界更新 counts／選來源；findings 沒有把所有分支誤寫成相同的無條件 copy。

共享 `172F8A0` 的完整 bytes 已另保存於 `component41_lifecycle_evidence_v2.json`，其中包含 key 刪除與有界 backshift；本次不重做其完整資料結構研究。

## 3. Owner 別名並非僅憑相同 offset 推測

以下鏈條均與原始 capture 相符：

1. **同一 owner 的兩個全域**：`FDA352` 形成 context+40；`FDA360` 發布到 global346BFC8；`FDA375→551B60→568230` 保持同一指標；`568242` 發布到 global3326540。
2. **更新**：`FDAEED` 保存 entry context 到 RDI；`FDAF4B/FDAF4F` 以 context+40 呼叫 `571250`；`57128D` 保存到 RDI；`5715CD/5715D7` 直接以 owner+2A988 呼叫 `9BA6C0`。
3. **Count 複製**：`FDC78F` 保存 context 到 RBX；`FDC7A3/FDC7A7` 以 context+40 呼叫 `576CF0`；`576D0D` 保存 owner；`577E7B/577E84` 直接複製 `owner+2A98C → owner+2A990`，即 S+4→S+8。
4. **診斷**：`56A950` 讀 global346BFC8，`56B3DF` 讀 owner+2A988；原 diagnostic 字串與保存 bytes 相符。

`9BA6C0` 外層迴圈比較 `S+8`，每次使用 `+0x68+ordinal*8` 與 `+0x88+ordinal*0x108`。所以只替換 global3326AF0 確實不能覆蓋這些直接 owner 讀寫。

## 4. ABI 與內外層索引界限合理

`51C080/51C110` 分別在 `51C09B/51C12B` 將 RCX 保存為 entity；`9BAAD0/9BAB60` 分別在 `9BAAEB/9BAB7B` 保存 RDX。原文提醒兩組 ABI 不同，有直接指令依據。

單筆 `0x108` 記錄內部 `0x10` 限制與外面的四筆記錄已明確區分；沒有把它當成玩家人數。Hash capacity 8 的敘述也保留「表示容量不等於八人已驗證」的限制，沒有無證增加到 16 的要求。

## 保留範圍

本 review 支持既有必要修改點，沒有提升為完整 relocation manifest、當前 runtime metadata 相同、hash 全滿穩定或八人已可遊玩的證明。其餘 global consumers／大型 callers 仍屬原 findings 已列明的未完成項目；這不影響本次邊界、單向壓實與 owner 別名三項核心結論。
