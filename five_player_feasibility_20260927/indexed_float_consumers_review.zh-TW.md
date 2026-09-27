# Indexed-float consumers：獨立審查

## 最終判定

**定稿 schema v2 在本輪限定範圍通過，沒有未解決的阻擋項目。** 已核對同一 D 的 caller 傳遞、`142D870` 兩個四筆迴圈與 stack map 的 index 4 覆寫、`14329B0` 的兩次雙筆展開，以及 `142CB90` 尾部 RVA table 的實際控制流引用。

本審查支持「搬移單一 writer 仍不足以完成此子系統的八槽改造」及文件列出的必要修改項。它不支持完整 consumer 掃描已結束、可直接 patch，或八人聯機已成功。

## 定稿與驗證計數

- 被審查：`indexed_float_consumers_replay.py`、`indexed_float_consumers_evidence.json`、`indexed_float_consumers_findings.zh-TW.md`。
- 正式 evidence schema：**2**。
- 正式 evidence SHA-256：
  `503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578`。
- 作者 replay 重新產生 `indexed_float_consumers_review_recheck.json`，與正式 JSON **逐 byte 完全相同**。
- 獨立核對 **5,231 條 instruction rows**：35 個 code spans 中的 5,229 條，加 caller manager save／restore 的 2 條 pins；逐條比對固定 capture 原 bytes、unwind 起點解碼的邊界與 asm。
- 其中 **12 個選定 roots 共 5,126 條正常程式指令**；其餘為 caller windows／pins，不混稱為 5,231 條完整 roots。
- 另核對 **1 段 51-byte raw tail**：3-byte NOP 加 48-byte／12-DWORD jump table，未把資料 bytes 計入正常指令數。
- 獨立 caller CFG：`725160` 的 **5,507 條指令**全數可由正常 entry 到達，核對 **7 個 reaching-definition 查詢**。
- caller CFG／stack 保存槽補證：`indexed_float_consumers_review_caller_cfg.json`，SHA
  `b1ac8e336b754ee5ec7cc55128ddb3b5670eaf11f9419c38843a5b472cd5ef90`。

主 replay 明列 caller CFG 是驗證此獨立證據的 SHA 與補充 pins，沒有冒稱在主 replay 中重新計算該完整 CFG。此區分正確。

## 1. 同一 D 的來源傳遞成立

前置證據固定：`M=[global3326AA0]`，`U=M+4F90+k*55A698`，`D=U+4C8260`。`k` 是 manager instance ordinal，與 roster network index `n` 分開。

独立以完整 `725160..72B8E0` 正常 CFG 檢查，以下六個 address-formation sites 的 RSI reaching definition 都只有 `727537`：

| 位址形成 | 後續呼叫 |
|---|---|
| `72755D` | `727579 → 14329B0` |
| `7275F3` | `7275FA → 14335F0` |
| `72AC69` | `72AC70 → 142C9B0` |
| `72ACA3` | `72ACC6 → 142BED0` |
| `72ACFC` | `72AD11 → 142D870` |
| `72AD1A` | `72AD38 → 1430450` |

這些位置都以 `RCX=RSI+4C8260` 傳 D，並非僅有相同位移的外觀。

### Manager 迴圈回邊的補證

完整 CFG 也顯示 `727516` 的 R14 有兩個來源：入口 `7251A4 R14=RCX`，以及迴圈後段的 `72B230 R14=[RBP+130]`。`7251A7` 已把 entry RCX 存到該槽。

正常 frame 中 `RBP=RSP+100h`，此槽亦即 `[RSP+230,RSP+238)`。檢查完整 caller 的固定 stack 寫入，包含 RBP／RSP 別名和寫入寬度，唯一重疊寫入為 `7251A7`。因此回圈再進入時仍恢復相同 manager；不能只用「到第一個 caller 的線性前綴沒有改 R14」作所有迭代的證明。定稿已補兩條 save／restore pins 及說明。

`14335F0` 再將 entry D 保存於 R14，傳給 `142FF90`／`1433020`；`142D870` 的 entry D 保存槽及各恢復定義也與正式 CFG 相符。上述寄存器傳遞採正常 Windows x64 nonvolatile 保存慣例，不模擬 exception 路徑。

## 2. `142D870` 的兩個四筆迴圈與 stack 覆寫

### 第一個迴圈

- `142DA78`：`R14=D+810A5`。
- `142DA87/142DA93`：R12D=0、R13D=0。
- `142DAB0` 的 flag 位址 `R14-28D` 即 `D+80E18`。
- `142DF7F/142DF82`：ordinal 加一，record pointer 加 `298`。
- `142DF8E/142DF92`：以 4 為界返回迴圈。

### 第二個迴圈

- `142D8A7` 保存 entry D 到 `[RSP+68]`，正式 CFG 的四條 R14 恢復來源都讀這個槽。
- `142DA9B` 將 `[RSP+60]` counter 設 0。
- `142EBA1` 將還原後的 D 加 `80E30` 作 record 相對基底。
- `142EDB5/142EDBE` 同步前進 record pointer `298`、stack-map pointer 4。
- `142EDC2/142EDC6/142EDC9` 更新 counter 並以 4 為界。

獨立加入寬度與 RBP／RSP 別名核對：`[RSP+68,RSP+70)` 唯一固定寫入是 `142D8A7`；`[RSP+60,RSP+64)` 只有 `142DA9B` 初始寫入與 `142EDC2` 迴圈更新。第二個 counter 沒有被第一個四筆迴圈暗中改成 4。

### index 4 的具體鄰接碰撞

`142EB0E/142EB16` 以兩個 qword 將 `[RBP-60,RBP-50)` 初始化為全 1，恰好四個 DWORD。`142EB33` 另將緊鄰的 `[RBP-50]` 設為 `56D7E815`。

roster 枚舉在 `142EB70` 從記錄 `+3B4` 取 n，只因 n 等於 selected local/current index 而跳過；`142EB7D` 寫：

```text
[RBP + n*4 - 60h] = nonlocal_rank
n=4 → [RBP-50h]
```

`142ED3B` 又把 `[RBP+rank*4-50h]` 當 ID table 讀入 EDI。故 index 4 未被跳過且此路徑到達時，確實覆寫已初始化、稍後可能使用的第一個 ID；不是寫入未命名 padding，也不必等第二個 record 迴圈改成八筆才發生。

這是條件式位址／資料流證據，不代表已觀察第五人執行或特定 crash。

## 3. `14329B0` 的兩次雙筆展開

本項另由 index-slot 審查支線交叉核對原 capture；定稿增加了所有條件寫入位置。

- `14329F1`：RBX 起點 `D+810BC`。
- `1432A00`：ESI=2。
- 每輪讀第一對 `[RBX-298]/[RBX-294]`，第二對 `[RBX]/[RBX+4]`。
- 第一對有條件 qword stores `1432BCE`、`1432C8F`；第二對有 `1432DCA`、`1432E80`。不能只列其中兩條而暗示每次都無條件 store。
- `1432E8B`：RBX 加 `530 = 2*298`；`1432E9A/1432E9E` 迴圈兩次。

展開後覆蓋的 float pairs 為：

```text
D+80E24 / D+80E28
D+810BC / D+810C0
D+81354 / D+81358
D+815EC / D+815F0
```

即四筆 record 的 `+C/+10`。要遍歷八筆，需四次雙筆迭代及正確的新 backing／別名處理；原數字 2 不能被遗漏為與容量無關。

## 4. 尾段是實際被引用的 RVA table

`142D830` 是正常返回。`142D831..142D834` 為 3-byte NOP，`142D834..142D864` 為 12 個 DWORD：

```text
[142CEA5, 142CEB6, 142CEAA, 142CEB1] 重複三次
```

存在直接的分派資料流：

```text
142CE90  EAX -= Ch
142CE93  CMP EAX, Bh
142CE96  unsigned-above → 142CEB6
142CE98  ECX = [R13 + RAX*4 + 142D834h]
142CEA0  RCX += R13
142CEA3  JMP RCX
```

R13 並非整個函式都不變。採這四個唯一 table targets 展開正常 CFG 後，673 條正常程式指令全部可達；`CE98/CEA0/CEA3` 的 R13 reaching definitions 只有 `142CC4D` 與 `142D1B8`，兩者皆以 RIP-relative LEA 形成 image base。

所以把此尾段分類為 NOP／RVA table 有**實際讀取、range guard、基底與跳轉目標證據**。解碼不完整並非唯一理由。定稿把 table bytes 與正常程式分開保存的方式正確。

## 5. 審查期間已修正的前提

1. **缺 local 時不能無條件認為七個 rank 足夠。** `142EA4E` 可令 local=-1。若八個有效 n 為 0..7，枚舉不會跳過任一筆，rank 可為 0..7，共八項。定稿已將「三張 ID 表提供七項」限定為八筆中確有有效 local 的情況，並要求缺 local／invalid local 狀態先驗證、拒絕或使用有界 fallback。
2. **尾段已由未分類保存升級為有引用證據的 table。** 沒有把 data bytes 當指令，也沒有靠 disassembly 失敗推論類型。
3. **同一 manager 的來源鏈含迴圈還原。** 已補 `7251A7/72B230`，並明列獨立完整 caller CFG 證據。
4. **雙筆展開包含四個條件 store。** 文案避免把其中一支當成唯一寫入或稱為無條件更新。

上述修正均已納入被審查的最終 SHA，沒有待作者修正的舊版問題留到整合稿。

## 6. 可接受的結論邊界

- 兩張 D-relative 四格 metadata 表分別從 `8D6C4`、`8D6D4` 起，每項 4 bytes；第一表 index 4 進入第二表，第二表 index 4 進入已使用的 `8D6E4` 狀態。不能原地只增加迴圈次數。
- 同一 D 的已證 readers、writers、初始化、清理與 interior-object address formation 都是八槽改造的必要處理面。
- 三張 ID 表的資源意義和新增合法值仍未知，不能為湊七／八項自行杜撰資源 ID。
- `142EE70` 的外部表索引 q 雖使用已證 D，語義及上游範圍仍未閉合；不能自動等同 roster n。
- generic helper、未納入的 caller／別名、runtime lifecycle、exception、平台及遊戲行為未完成全面驗證。
- 沒有 live query／read、新擷取、patch、遊戲函式執行或總報告修改。

可將最終定稿納入驗證表，但應保留「有限 consumer 集合」與「必要修改項，非完整可運行方案」的標籤。
