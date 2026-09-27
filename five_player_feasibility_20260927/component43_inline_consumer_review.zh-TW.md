# 元件 43 內聯 consumer：獨立審查

## 結果

**限定範圍審查通過，未發現需修正的資料流、同 displacement 排除或內層容量結論。** `12A02BB` 取得的 component43 物件基底確實支配後續 pointer／record／record-count 存取；只改接獨立 `9BA430` helper 不能涵蓋這段內聯實作。

受審查：`component43_inline_consumer_replay.py`、`component43_inline_consumer_evidence.json`、`component43_inline_consumer_findings.zh-TW.md`。

正式 evidence SHA256：

```text
f8a4a4e5ca22f490cc80614019fd683f5b532a71e8597dfb6686751c5ba069a3
```

本次只新增本 review；沒有改受審查檔案或總報告，沒有 live/query/capture/patch。

## 1. 原始 bytes 與 CFG 独立核對

未呼叫受審查 replay 的函式；從固定 capture 的原 unwind 表重新找出 root `129FD00` 的全部 fragments，確認與 evidence 完全一致，再由每段入口完整解碼。

- 四個 fragments，合計 **2,821 bytes、687 條指令**。
- 每條 RVA、bytes、instruction SHA256、mnemonic／operands，以及每段和合併 bytes hash 均符合。
- 用 Capstone 的 return／jump 分組独立建立正常 successor graph，與 evidence 的全部正常 edges 一致。
- 由 `12A02BB` 出發、止於 `12A0316/12A031E` 的區段恰為 **85 個指令節點**，與 evidence 完全相同。
- 對已列出的十個 RIP-relative references，逐一核回原始指令並重算 RIP target，均指向 `3326AF0`。沒有冗餘重掃整個 code range；十個引用仍限定為受審查工具所聲明的特定編碼集合。

原 capture 的檔案 SHA256：

- `capture-report.json`：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- `captured-data.bin`：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

## 2. RDI 基底存續與支配關係成立

受審查 replay 以 explicit destination 檢查 RDI。此次另外使用 Capstone `regs_access()`，包含顯式／隱式及 `RDI/EDI/DI/DIL` 各寬度的寫入；該 85 節點區段唯一寫入仍是：

```text
12A02BB  mov RDI,[global3326AF0]
```

再從正常 root 入口 `129FD00` 做可達性檢查，將 `12A02BB` 視為不可經過的節點，以下六個重要存取全數變成不可達：

```text
12A0402  entity pointer
12A0445  record base
12A0451  record count load
12A0492  record count load
12A04A4  record count load
12A04B3  record count increment
```

因此這些存取不只是「從 global load 出發可能到達」，也不能由此 root 的其他正常路徑略過 load 進入。它們沿用同一 S 的結論成立。跨 `4F6A00` call 的存續仍依正常 x64 nonvolatile register 約定，未展開 callee 或驗證執行期行為；原 findings 已揭露此界限。

`12A0325 mov EDI,EBP` 位於區段退出後，確實終止 RDI 作 S 的用途。不能因地址在 `12A0402` 之前就按線性位置誤判它已先破壞 S；實際 jump edges 會在清除 RDI 前進入該內聯分支。

## 3. 元件 ordinal 與單筆記錄資料流

Roster 查找命中後，`12A03CA` 先取得 roster pointer，再在 `12A03D2` 讀 entity+8 的 **ID**。接著以 component43 的 `+50/+58/+5C/+60` map 查找；`12A03F4` 讀 entry+4 才取得 component ordinal。

`12A03F9/12A03FC` 會跳過 `FFFFFFFF` ordinal。`12A0402` 使用 `S+ordinal*8+68` 取 entity pointer，`12A0407` 保存 ordinal 到 R15D。此 ordinal 不是前面 roster scan 的 ordinal，也未被命名為 network index，原 findings 的區分正確。

記錄地址與 count 分別形成：

```text
12A043E: R9  = ordinal * 0x108
12A0445: RDX = S + 0x88
12A044E: RDX = record = S + 0x88 + R9
12A0451 等: count = [S + R9 + 0x188] = [record + 0x100]
```

Count 的四個直接基底存取沒有經 RDX；所以只改 `lea RDX,[S+88]`，會令 record 項目與 count 落在不同布局。將它們列為必須同步改接的位置有明確資料流依據。

## 4. 兩個 16 都不是玩家容量

內聯 record 更新中，項目下標先加倍，再以 scale 8 存取，步幅精確為 **16 bytes**。每項包含 qword key、`+8` DWORD、`+C` DWORD；16 個項目正好佔 `0x100` bytes，之後是 record count。

- 未找到項目時 `12A047A cmp R8D,0x10`、`12A047E je` 在 count **等於 16** 時退出。原碼是 equality guard，不是一般的 unsigned `>=16` guard；在正常 count 域內描述為「滿時離開」正確，但不能延伸成損壞 count 也安全的保證。
- 追加時 `12A048A` 初始化 `+C`，`12A04A0` 設 `+8`，`12A04AF` 寫 key，`12A04B3` 增加該 record 的 count。
- 已有項目時 `12A04CB` 增加 `+C`，`12A04D2` 更新 `+8`。

較早的 `12A0438 cmp R8D,0x10` 則掃描 `4F6A00` 回傳物件 `RAX+8` 起的 qwords，來源不同；它同樣沒有使用 component slot ordinal 作為該計數。把兩個 16 與玩家容量分開是必要且正確的。

## 5. 同 displacement 的排除正確

| 被排除位置 | 確認的基底來源 | 排除理由 |
| --- | --- | --- |
| `12A03AD [R9+88]` | `12A036B` 取得 roster global3326468 | 此處 R9 是 roster，不是 S；也不在上述 85 節點的 S 存續區段。 |
| `12A064C lea RCX,[RSP+88]` | RSP | 是傳給另一個 helper 的 stack 地址。 |
| `12A0659 mov EDI,[RSP+88]` | RSP | 從該 stack 值載入另一個用途的 EDI，不能當作 component record。 |

受審查成果沒有靠 `0x88` 的數字相同就擴大 relocation 清單，也沒有把有限 MOV／LEA 掃描的十個引用當作全部讀寫者。未知 owner aliases、其他編碼與未展開 consumers 仍須保留原有界限。
