# API `+0x30/+0x18` 保存前綴分析

此文件只分析先前同意的一次唯讀擷取所保存的 JSON 與磁碟 EXE；本輪沒有再開啟或讀取遊戲程序。可用 [interface_target_30_analysis.py](interface_target_30_analysis.py) 重播，逐指令證據在 [interface_target_30_evidence.json](interface_target_30_evidence.json)。

## 來源與磁碟比對

- 保存快照 JSON SHA-256：`a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f`。
- 保存的 `helldivers2.exe` RVA `0x3494b0`、256 bytes 已載入程式前綴 SHA-256：`d52d364307cb57a442cc6295a48d840458caf81de9da0ac9e40cb72083d9b144`。
- 磁碟 EXE 完整 SHA-256：`f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`，與快照的檔案指紋一致。PE section 將 RVA `0x3494b0` 對應磁碟 offset `0x348ab0`。該處磁碟 256 bytes SHA-256 為 `fbee52badb3e99fdce736b7e14276f95047d9e1c629bfad3a3554a1b09f5845b`，**從第 0 byte 起就不同**。因此不能以磁碟此處的反組譯取代已保存的 loaded code。

## 保存前綴中的資料流

依 Windows x64 慣例，入口 `ECX` 與 `EDX` 是前兩個整數參數。保存前綴在 `0x3494cb` 將 `ECX` 存到 `EBP`，在 `0x3494cd` 將 `EDX` 存到 `ESI`。兩者沒有在前兩次間接呼叫中直接使用。

在 `0x34952a` 直接呼叫 EXE RVA `0x4acde0` 前，`0x34951a` 將原 `ECX` 的低 32 bits 寫至 caller `[RSP+0x28]`，`0x349513` 將原 `EDX` 的低 32 bits 寫至 `[RSP+0x30]`。這些位置在該呼叫時分別是 Windows x64 第 6、7 個參數槽。指令沒有初始化兩個槽位的高 32 bits；被呼叫者的正式型別未知。

既有固定 `game.dll` 捕捉顯示，此 API 的一條呼叫路徑在 `0x1091845` 從 owner `+0x1b90` 讀 `EDX`，在 `0x1091874` 從 owner `+0x1b94` 讀 `ECX`，`0x109187a` 間接呼叫。零設定分支將前者預設為 `4`，後者預設為 `0x2710`；後者亦可被設定覆蓋，快照沒有保存其實值。這些值不能自行命名為玩家上限或網路埠。

前綴在 `0x3494cf` 設 `R9D=8`、`0x3494d5` 設 `R8D=0x5e0`，供前面的另一個**間接呼叫**使用。該常數 `8` 不能解讀為八人容量。

## 一層直接呼叫

| 保存 call site | 靜態目標 RVA | 保存前綴能證明的資訊 |
|---|---:|---|
| `0x34952a` | `0x4acde0` | 原入口兩個整數參數的低 32 bits 作為第 6、7 個 stack argument；返回 `RAX` 保存在 `RBX`。此呼叫的 `RDX` 經前面兩次間接呼叫後未在前綴中重新設定，值無法確定。 |
| `0x34953c` | `0x349110` | `RCX` 取自 RIP-relative global RVA `0x1a10258`，`RDX` 是 `0x4acde0` 返回值。此第二次呼叫的返回值被忽略；函式最終返回首個直接呼叫的返回值。 |

兩個直接目標都不在已保存的 256-byte loaded 前綴內。磁碟對應位元組可定位，卻沒有任何同位置 loaded bytes 用來核對；在已知入口磁碟內容不等於 loaded code 的情況下，目標實作只能列為**磁碟資料候選**，不能反組譯後當成執行期語義。保存前綴包含 `0x349558` 的 `ret` 與其後 padding，足以完成這個入口的一層參數追蹤，但不能推論後端服務或八人聯機是否可行。快照本身標示 `atomic_snapshot: false`。
