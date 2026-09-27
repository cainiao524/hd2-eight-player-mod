# 元件 238 生命週期：獨立離線審查

日期：2026-09-27。審查者：`spawn_interface_probe` 子代理。只核對已保存的程式 capture 和本輪 238 產物；沒有查詢、讀取活程序，也没有更改被審查的檔案。

## 審查結論

**目前沒有發現需要撤回的布局衝突或生命週期結論。** 第 5 個指標覆寫 ordinal byte 及 primary record、primary slot 4 覆寫 property record、property slot 4 跨入下一個 roster，均有同一物件 base 和真實指令支持。一般 move 與分類 callback 的不同處理也已正確區分。

原提出的一項證據可讀性補強已完成：正式 v2 的 owner tick pins 現在包含 `5727D6` 的 owner 指標恢復指令。這是使保存證據更完整，並非改變 owner tick 結論；獨立審查已回到固定 capture 核對其來源。

## 檢查對象与方法

- `component238_lifecycle_replay.py`
- 正式 `component238_lifecycle_evidence_v2.json`：SHA-256 `ac68b8cc938dc56288c9db7fa9a41d8a64f84fdd353fee6ff3414f6c35e0424b`
- 初次審查 `component238_lifecycle_evidence.json`：SHA-256 `c7a4addf24b68d372218cd98b6079f8a0ecba363043939b97fa395fc8e37322b`，現只作審計。
- `component238_lifecycle_findings.zh-TW.md`

原始 capture 由 `inspect_capture.Image` 重新驗證固定 report、data SHA 和 capture identity。独立檢查逐項比對 JSON 內的 **1,652 條 unwind-root 指令、212 條已證入口 leaf 指令，以及 81 個額外 pins**：RVA、原始 bytes、反組譯文字全部相符；每個保存 fragment 的 SHA 與對應 unwind root 相符。這 1,945 筆檢查記錄包含重複 pin，不代表 1,945 個唯一程式位置。

隨後獨立比較 v2 與初版：只改動 `pins.owner_tick_alias`，增加已核對的 `5727D6`；其他 top-level 資料均相等。v2 因而為 **82 個額外 pins、1,946 筆檢查記錄**，保留原有 1,652 + 212 條函式指令。新版 findings 的正式檔名、SHA 與 stack-save/restore 說明亦已更新。

此審查沒有把「重播脚本執行成功」當成語意證明。布局、同 base 來源、copy/swap 和 owner 指標傳遞另外直接讀取已固定的程式。

## 1. 指標 slot 4 的衝突成立

`87C49B` 從 global `33264F8` 載入 RBP。entity ID 查表命中後，`87C514` 取 map value 至 EBX，`87C52F` 令 ESI=EBX；`87C4F5/87C4FC` 令 `R15D=[RBP+8EC]-1`。其非相等索引分支：

```text
87C576  movzx ecx, byte ptr [r15 + rbp + 968]
87C581  mov   byte ptr [rsi + rbp + 968], cl
```

這支持把 `+968+ordinal` 視為既有索引 byte 欄位，沒有必要猜測它的遊戲語意。正常四槽 ordinal 0..3 使用 `[968,96C)`。第 5 個指標寫 `[948+4*8,948+5*8)=[968,970)`，會覆蓋四個 byte，再覆蓋 `+96C` primary 第一筆的前 4 bytes。

同時，byte 欄位的 ordinal 4 位址為 `96C`，已是 primary 的第一個 byte。這並非只由一個 `cmp 4` 推論的限制。

## 2. `+A7C` 第二組 record 與下一 owner 成員

`87B5D0` 已明確分開算 destination/source：

- `87B5D2` 保存 EDX=destination；`87B5ED` 保存 R8D=source。
- `87B5F0/87B5F4` 乘 `44`，對 primary record 搬四組 16 bytes 加 4 bytes。
- `87B5E5/87B610` 對各 ordinal 左移 6，形成 `40` stride。
- `87B66B..87B6AA` 搬四組 16 bytes，證明 property record 寬度為 `40`。

以下算式核對無誤：

```text
96C + 4*44 = A7C
A7C + 4*40 = B7C
EA0818 - E9FC98 = B80
```

因此 primary slot 4 `[A7C,AC0)` 覆蓋 property slot 0 全部 64 bytes，再覆蓋 property slot 1 的前 4 bytes。property slot 4 `[B7C,BBC)` 的首 4 bytes 還在下一成員前，其餘進入 roster。

鄰接 roster 不是僅靠位移猜測：`568EBA/568EC1` 和 `568EC8/568ECF` 從同一 owner 分別發布 `+E9FC98` 與 `+EA0818`；初始化另以這兩個固定地址呼叫相應函式。被保存的 roster 初始化 leaf `60C9C0` 的 `60CA39/60CA44/60CA4F/60CA57` 分別寫其 `+8/+10/+18/+20` qwords，均落在 hypothetical property slot 4 覆蓋範圍內。

四組已知 per-ordinal 內容的加總 `8+1+44+40 = 141` bytes（後兩項為十六進位）正確：四項增加到八項多 564 bytes。findings 已將此數字限定為已知邏輯資料，不是完整物件配置或 mod 最低 allocation，界線適當。

## 3. Copy 與 swap 沒有混為同一種操作

一般 move `87B5D0` 會拷貝 entity pointer、68-byte primary、64-byte property，並用搬入 entity 的 ID 查 map，`87B722` 將 map value 改為 destination。其完整函式沒有 `+968` byte 欄位存取。

`87C120` 的非相等索引路徑將 primary 暫存後雙向交換（`87C216..87C2A3`），也雙向交換 property（`87C2D7..87C37A`）；`87C480` 同樣雙向交換這兩組 record（`87C5B9..87C646`、`87C67A..87C71D`），兩者另交換 entity pointers 並修正兩個 map value。因此 238 的這兩條 primary 路徑確實不同於 250 的「增加分類時清零 primary」情況，沒有錯套相似外觀的函式。

`87C480` 的 `+968` byte 路徑本身則是**單向 copy**：將 prefix 尾端 byte 寫到查得的 ordinal，沒有把兩個 byte 完整對調。現有文案稱它「存取 byte」，沒有把所有欄位一概叫 swap，這種寫法準確；後續實作研究仍需保留這個差異。

## 4. Owner 與登錄別名

`B24BD0` 在 global `3326E68` 中保存 `(物件指標,tag=18)`，七張表的起點 `C98,CC0,CD8,CF0,D18,4250,4268` 均由實際位移或 `index*16` 算式核對成立。`B2FC70` 逐表比較相同物件指標，命中後移動末項及減少 count。登錄 tag 並不是 component index 238。

初始化、析構、重載、批次搬移、tick 和反序列化都存在使用固定 owner offset 的證據。它們足以支持「只換 global33264F8 不會自動重導所有路徑」，而不要求先窮盡整個遊戲的每個 consumer。

### 已補存的 tick 恢復指令

現有 pins 保存 `57128D: RDI=RCX` 與 `571290: [RSP+68]=RCX`，以及 `57324A: RCX=RDI+E9FC98`。其間 RDI 實際曾作其他暫存值，因此只看頭尾 pins 不足以直觀看到恢復鏈。

本次獨立核對從固定 root 到 call site 的全部指令，確認這段有：

```text
5727D6  488b7c2468  mov rdi, qword ptr [rsp + 68]
```

在到 `573254` 的線性程式範圍，`571290` 是對 `[RSP+68]` 唯一的明確 MOV 寫入；`5727D6` 是抵達該 tick site 前最後一條 RDI 寫入。以正常 Windows x64 呼叫慣例解讀，該 site 的 base 與保存的 owner 相同。**正式 v2 已加入 `5727D6`，此項完成。**

### 反序列化路徑的非直線程式

`BC2D85` 從 global `346BFC8` 讀到 owner；該 global 與 `FDA360` 發布的 context+40 指標相符。此大型 root 中有多處 `mov rbx,[rsp+40]`，是分支結尾的 nonvolatile restore，再接 RET；例如 `BD0C63..BD0C72`。不能把線性地址上較早的 epilogue，當作之後另一分支 `BD13BB/BD13C9` 的 base 已變。

目前保存的 `BC2D85 → BD13BB → BD13C9` 配合 unwind root 支持所述 owner 路徑；若之後把它升級為自動化 relocation gate，應再加入 CFG 層面的 base 傳遞驗證，而不是只使用根函式相同或 text-order 最近寫入。

## 5. 結論的範圍

這次審查確認固定 capture 內的靜態儲存衝突、相關 callback 寫入和已列出的別名。它没有確認目前安裝版本、執行期資源清單、某 callback 真實被呼叫、第五位玩家建立成功，或八人模組可運作。

原文對 reference metadata、未賦值 callback slots、未窮盡 consumer、map 8 與玩家容量不同、16 buckets 只是設計選項等限制都有保留；沒有發現藉此誇大成 runtime 證明的敘述。
