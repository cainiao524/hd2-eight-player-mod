# Roster property 接收已定位：`60C890` 原樣寫入 32-bit network index

## 結論與新增設計條件

**已關閉這條 property 分派路徑的接收／套用缺口。** `BC2D30` 內 `BD13B3` 直接呼叫 `60C890`，後者使用 entity ID 查 roster 自身的 ID→ordinal map，再以八次 DWORD copy 寫入完整 `0x20` bytes property record。

其中第四個 DWORD 的直接資料流是：

```text
payload + entry_cursor + 0xC
   60C95C: mov ECX,[RDX+RBP]
   60C962: mov [R8+R11+0x3B4],ECX
roster + ordinal*0x20 + 0x3B4
```

**完整 32 bits 原樣保留；callee 沒有 `<4` 判斷、clamp、mask、兩位元／byte 截斷，也不把值換成 ordinal。** 因此索引 4–7 不會在此接收函式被縮窄或改寫。這不表示其他容量限制已解除：本函式的目的地仍是原四槽 record 布局，且依賴已有有效 entity→ordinal。

對八槽重新配置的新增要求：

- `60C890` 的八個目的欄位 store 必須一起跟著 property array 的新基底變更，不能只處理 `+3B4`。
- 直接 caller 使用 `owner+0xEA0818`，不讀 roster global。只換 global3326468 會漏掉此路徑。
- 保留 source buffer cursor 的 `+0x20` 消耗規則，避免後續元件讀錯位置。
- 本函式沒有自行拒絕缺少的 entity ID／越界 ordinal／短 buffer；擴容方案必須保留呼叫前的建立與映射不變條件。

本頁補充而不改寫歷史報告：`roster_property_apply_findings` 所稱「未由五個 lifecycle callbacks 找到接收入口」仍是當時該限定搜尋的結果；現在的入口來自另外的 property 分派 helper。

## 1. 證據來源及驗證

正式產物：

- `roster_property_receive_replay.py`。
- `roster_property_receive_evidence.json`，SHA256：`bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10`。

Replay 使用原固定 game.dll 捕捉；重核下列既有證據檔並逐筆比對合計 **690 筆原 bytes 記錄**：

| 既有檔案 | SHA256 |
| --- | --- |
| `roster_component_binding_evidence_v3.json` | `274833c418bfa7dec4e4097dda5031f3a11e8c69689ae4ed758e75a40481c2e2` |
| `roster_property_apply_evidence_v3.json` | `d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22` |

原來源 SHA256：

- `capture-report.json`：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- `captured-data.bin`：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

接收函式全部四個 unwind fragments 連續涵蓋 `[0x60C890,0x60C9BF)`，共 **303 bytes／72 條指令**；每段 bytes 與 SHA、所有指令、正常 CFG 都保存在正式 JSON。正常 CFG 的邊全部落在已證明的指令邊界，全部 72 條由入口可達；函式內沒有 call。

另固定 **42 條 caller／owner／producer 指令**、八組具體 load/store。只讀保存資料，未讀／查活程序、新擷取、安裝、patch 或進行多人測試；總報告及其他代理檔案未修改。

## 2. Caller 及同一 roster 身分

### 傳入 ABI

`BD13A2..BD13B3` 的完整連續指令為：

```text
BD13A2  mov EDX,[RBP+0x28]         ; entity ID
BD13A5  lea RCX,[RBX+0xEA0818]     ; roster S
BD13AC  lea R9,[RBP+0x20]          ; uint32 cursor*
BD13B0  mov R8,RDI                ; payload base
BD13B3  call 60C890
```

`BC2D85` 取得 RBX 的全域是 `0x346BFC8`。它在 `FDA352/FDA360` 被發布為原 context+0x40，也就是 callback owner O；經 `551B60→568230` 的同一 owner，在 `568EC8/568ECF` 將 `O+0xEA0818` 發布到 **global3326468**。因此此次 RCX 與先前產生／分類搬移所用的 roster 物件相同，並非只有 displacement 相似。

`BC2D96` 將 API 提供的 payload pointer 放入 RDI，`BC2D9A` 把共用 cursor 設為 0。多個 property helpers 共用此 cursor，所以 **`60C890` 的 entry cursor 不應假設仍為 0**。

`BC2D8E` 在主分派前呼叫 `FD9BA0`；它如何將 external handle 轉 entity ID、selector 如何選中此分支，以及前置 helpers 消耗多少 buffer，由 `property_dispatch_findings.zh-TW.md` 上游支線獨立固定。本頁直接證明 caller 讀取 `[RBP+0x28]`，不以這個暫存欄位本身保證 ID 必然有效。

### 有限 caller 掃描

在固定保存 code 範圍，以 E8/E9 直接分支及 unwind 邊界驗證搜尋 `60C890`，取得一個直接 caller：`BD13B3`，unwind root 為 `BC2D30`。這不是「全遊戲只有一種接收方法」的證明；indirect calls、未涵蓋 leaf 或執行期改寫不在此掃描完整性範圍內。

## 3. Entity ID → ordinal，而非 network index 選槽

入口保存：

- `60C89D`：R14=R9，cursor pointer。
- `60C8A0`：RBP=R8，payload base。
- `60C8A3`：R11=RCX，roster S。

查找的 key 是入口 EDX，即 entity ID。Map 欄位：pointer `S+D0`、capacity `S+D8`、invalid key `S+DC`、乘數 `S+E0`。探測在 `60C8F0..60C912`，命中後 `60C9B5` 讀 map entry+4 到 EAX。

`60C92B mov R8D,EAX`、`60C92E shl R8,5` 形成 **ordinal×0x20**。接收的 network index 是稍後 payload 的第四個 DWORD，沒有被拿來選這個 roster record。

因此以下三個量各自獨立：

1. External handle：上游分派參數，經另一個 helper 轉換。
2. Entity ID：此函式入口 EDX，用來查 roster map。
3. Roster ordinal：map value，用來定位 record；record 內第四 DWORD 則是接收的 network index。

## 4. 完整 32 bytes 的欄位對照

令 c 為入口時 `[R9]` 的 uint32 值：

| DWORD | 輸入位置 | 目的欄位（再加 ordinal×0x20） | Load RVA | Store RVA |
| --- | --- | --- | --- | --- |
| 0 | `payload+c+0x00` | `S+0x3A8` | `60C932` | `60C938` |
| 1 | `payload+c+0x04` | `S+0x3AC` | `60C940` | `60C946` |
| 2 | `payload+c+0x08` | `S+0x3B0` | `60C94E` | `60C954` |
| **3** | **`payload+c+0x0C`** | **`S+0x3B4`：network index** | **`60C95C`** | **`60C962`** |
| 4 | `payload+c+0x10` | `S+0x3B8` | `60C96A` | `60C970` |
| 5 | `payload+c+0x14` | `S+0x3BC` | `60C978` | `60C97E` |
| 6 | `payload+c+0x18` | `S+0x3C0` | `60C986` | `60C98C` |
| 7 | `payload+c+0x1C` | `S+0x3C4` | `60C994` | `60C9A2` |

這些均為 DWORD load/store，沒有重解釋數值或轉型的指令。Network index 的 load 與 store 之間唯一指令 `60C95F add EDX,4` 修改的是 cursor 暫存器，不會改 ECX 的資料。

尾部 `60C997 lea EAX,[RDX+4]`、`60C99F mov [R14],EAX` 將 cursor 推進 `0x20`。它是 uint32 cursor 算術；本頁對 buffer 消耗的描述限定有效、不溢位的正常 buffer 範圍。

前四欄與後四欄在 producer 的 type code 不同，但 receiver 都以相同的 32-bit copy 保存 bits。不能僅從這些 MOV 指令進一步猜測所有欄位的正式 SDK 型別。

## 5. 與既有 `index` 產生證據接合

既有 producer `60C640` 從 entity ID 查同一 roster map，將 ordinal 乘 `0x20`，並以 `134F190` 取得本地 network index。此次重核：

```text
60C778  call 134F190
60C77D  mov [roster+ordinal*0x20+0x3B4],EAX
60C784  mov [output buffer+0xC],EAX
60C78B  descriptor hash = 0xB03B8BCE
60C793  descriptor type = 1
```

既有固定雜湊／名稱證據把 `0xB03B8BCE` 接到 `index`；其數值為 network index 則有直接機器碼來源。現在 receiver 對同一第四欄作原樣 DWORD copy，補上了「接收／套用這份記錄時是否窄化」的限定缺口。

這並不代表所有獨立 property 更新消息必然走本函式，也不把 producer descriptors 直接等同未經核對的線上封包格式。真正上游 selector／payload 來源由另外的分派證據支線處理。

### 上游正式證據補充：指定格式下 `index = payload+0x10`

已收到並核對 `property_dispatch_evidence.json` 的固定 SHA256：`9cabca2fa61fd59e9c776230da80ad68716f947c46f56c6b9c203ba011d0d55d`。該支線證明 API 結果的 `+8` DWORD 是 format selector；`0x3A7` 對應 jump table slot `BDAD54`，其中 bytes `8c13bd00` 指向 `BD138C`。

此分支先經 `BD139D → 671860`：雖然只讀一個 byte，cursor 仍增加 4。接著 `BD13B3 → 60C890` 的入口 cursor 因此為 `0x4`，所以此格式中的 network index 地址為：

```text
payload + 0x4 + 0xC = payload + 0x10
```

這是 **API 提供之 payload 的偏移**，不是未核對的網路 transport packet 偏移；`0x3A7` 也是 format selector，不能當作玩家 ordinal 或已證明的 component index。上游證據另外指出建立路徑有「先加入元件、建立 handle map，再套用資料」的順序，但 `FD9BA0` 一般失敗仍可能返回 sentinel，`BC2D30` 沒有後續 ID 有效性檢查，故不能提升為所有呼叫都滿足 membership 前提。

## 6. 接收函式自己的前提與缺少的檢查

這個函式**沒有安全的 map-not-found 返回分支**：

- 輸入等於 invalid entity sentinel，或 map 查無 key，會得到 EAX=`0xFFFFFFFF`。
- `60C928` 的寫入路徑仍會執行，將該值當 ordinal 乘 32；沒有先與 record count 或 4 比較，也沒有跳過寫入。
- 入口沒有 buffer length 參數；函式本體沒有在八次讀取前驗證長度。

因此「它原樣接受 network index 4–7」只描述**已有正確 entity→ordinal 與有效 buffer 時，欄位 copy 的位元寬度**，不代表可向任意不存在的 entity 套用。建立順序、有效映射及上游輸入保障仍是原生程式依賴的條件。

八槽方案不需要為此 receiver 的 network-index scalar 增加位元寬度，但需要確保 ordinal 4–7 有正確配置的 record 空間，以及未破壞 map、cursor 和直接 owner 別名。

## 重播

輸出必須使用新路徑：

```powershell
python -B five_player_feasibility_20260927/roster_property_receive_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-roster-property-receive.json
```
