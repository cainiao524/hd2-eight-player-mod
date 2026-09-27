# 元件 41 生命週期：主代理獨立核對

受審查檔案：[component41_lifecycle_evidence_v2.json](component41_lifecycle_evidence_v2.json)。

SHA-256：`0f902df704cffb16992d483e099867f5e05708e6d32bdf1672128eca744721df`。

## 核對方式與結果

主代理另外載入固定原始 capture，未呼叫受審查 replay 的驗證函式。依 captured unwind table 重建各 fragment 的指令邊界；無 unwind 的 initializer、兩個 callback wrapper 及取消登錄 leaf，則使用其已保存的直接 call／靜態登錄入口證明。

- 遞迴核對 JSON 的 **1,982 筆指令記錄、1,702 個不同位置**：RVA、bytes、SHA、反組譯均與原始資料一致。記錄含重複的 prior、選定片段與存取清單，不能把 1,982 當作不同指令總數。
- 重新枚舉完整 captured unwind table，確認 **14 個函式根**的 fragment 集合與證據完全一致，並核對每段 SHA；沒有只確認入口而漏掉 chained fragments。
- 核對三個無 unwind leaf，包含 `B389B0` 完整取消登錄範圍；未以第一個 return 截斷後續分支。
- 親讀 constructor／global 發布、外層 owner 的分類整合、屬性套用與取消登錄片段，與成稿中的地址、參數及物件來源相符。

## 會影響布局的結論

重新計算四組陣列的相鄰邊界：

```text
0x68    + 4*8      = 0x88
0x88    + 4*0x9928 = 0x26528
0x26528 + 4*0x58   = 0x26688
0x26688 + 4*0x58   = 0x267E8
0x2A930 - 0x4148  = 0x267E8
```

這支持第三組資料不能省略、整個連續區域已接上下一 owner 成員的結論。

`577dde..577e2a` 直接形成 `owner+4148`，兩次呼叫 copy helper `7af210`，另在 `577e03` 讀絕對 owner 位移 `+4154`，即元件 `+C` 的分類 count。`bd13e7/bd13f5` 又以同一 owner 的 `+4148` 呼叫屬性 writer `7af610`；`55f3a8/af` 使用此地址取消五份 registry 登錄。因此 global 替换不能自動涵蓋這些已證明的別名。

成稿有區分單向 copy、移入時大記錄清零、移出時整筆交換，以及兩份 `0x58` 記錄的產生／套用；沒有把所有行為合併成通用 swap。Map 的八個 buckets 亦沒有被寫成已驗證八人容量或必須擴成十六項。

## 審查界限

沒有發現推翻上述核心布局與生命週期結論的問題。本審查證明固定程式與分析的一致性，未驗證 runtime 指標、目前資產清單、其他尚未窮盡的 consumers 或第五／第八名真人玩家。沒有讀取或修改活程序。
