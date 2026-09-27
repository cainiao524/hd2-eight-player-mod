# 元件 43：剩餘已識別 global consumer 的內嵌記錄更新

本次僅分析 build 25480438 的固定離線捕捉，沒有查詢或讀取遊戲程序。承接[元件 43 生命週期](component43_lifecycle_findings.zh-TW.md)；正式產物為 [replay](component43_inline_consumer_replay.py) 與 [evidence](component43_inline_consumer_evidence.json)。

## 新增結論

`129FD00` 的 `12A02BB` 載入 global `3326AF0`，以 RDI 保存元件 43 物件 S，隨後直接執行逐 entity 記錄的查找、插入及累加。這段沒有呼叫先前已分析的 `9BA430`，但具有相同的 pointer／record 布局與更新形式。因此**只改接 `9BA430` 不會涵蓋此路徑**。

八槽實作若保持 S 地址、另外配置陣列，必須同時改接這段的 pointer array、record 起點，以及獨立計算的 record 內 count 地址。所有衍生讀寫必須落在同一筆新記錄。

## 位址關係與必要存取

| 步驟 | 已核對指令 | 用途 |
|---|---|---|
| 取得 entity ID | `12A020A` 載入 roster global；掃 `+2C8`、stride `38`；`12A03CA/3D2` 從 roster pointer 取 entity `+8` | 此處取得 entity ID，不把 roster ordinal 當成元件 43 ordinal。 |
| 查元件自身 map | `12A02BB` S；`12A02CB..314` map `+50/58/5C/60`；`12A03F4` entry+4 | 元件 map value 才是下面的 ordinal。`FFFFFFFF` 在 `12A03F9/3FC` 離開此更新。 |
| 取 entity pointer | `12A0402` | `S+ordinal*8+68`。 |
| 建立 record 地址 | `12A043E/445/44E` | `R9=ordinal*108`；`RDX=S+88+R9`。 |
| 讀寫 record count | `12A0451/492/4A4/4B3` | `S+ordinal*108+188`，即 record+`100`。此組地址沒有透過 RDX。 |
| 讀寫項目 | `12A0465/48A/4A0/4AF/4CB/4D2` | `record+item*10` 的 qword key 與 `+8/+C` DWORD。這裡 `10` 是十六進位、即每項 16 bytes。 |

找不到既有項目時，`12A047A` 比較該 record 的項目數與 `0x10`，滿時離開；否則追加 key、兩個 DWORD 並增加 count。找到既有項目時，增加其 `+C` DWORD 並更新 `+8`。**這個 16 是單一記錄內的項目數，不能改成八人上限。** 前面的 `12A0438` 也比較 16，但屬於 `4F6A00` 返回物件的另一組 qword 掃描，不是玩家槽位。

## 控制流程與排除的誤判

完整 root 有四段 chained unwind fragments，共 2,821 bytes、687 條指令。正常 direct CFG 保存於 evidence；從 `12A02BB` 起，到 `12A0316/31E` 為止的 85 個指令位置中，RDI 只有入口這次明確賦值。正常 x64 callee-preserved register 約定下，相關陣列存取沿用同一個 S；本次沒有執行或模擬下游呼叫。

`12A0325` 之後 RDI 已改成別的值，不再沿用為 S。以下相同 displacement 也不能算進元件 43 的陣列改接清單：

- `12A03AD [R9+88]` 的 R9 來自 `12A036B` 載入的 roster global。
- `12A064C/659 [RSP+88]` 是堆疊。

## 覆蓋範圍與仍需完成的事

對保存 code range 的特定 RIP-relative MOV／LEA 編碼重新掃描、再核對 unwind 指令邊界，共識別十個對 `3326AF0` 的引用。此前九個已在生命週期研究分類；本次補上第十個 `12A02BB`。十個引用的角色與原始 bytes 均保存在 JSON。

**這只完成此種掃描已識別的集合。** 其他編碼、raw pointer、傳播別名、間接存取、owner 直接位址及捕捉範圍外的程式仍可能存在，不能把十個引用當成全部存取。實際改接方式、配置與釋放、新舊陣列一致性及多人行為尚未實作或驗證。

正式 evidence SHA-256：

```text
f8a4a4e5ca22f490cc80614019fd683f5b532a71e8597dfb6686751c5ba069a3
```
