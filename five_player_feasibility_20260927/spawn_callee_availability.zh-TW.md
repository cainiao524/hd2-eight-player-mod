# EXE `0x1AE380` 下游函式：離線資料可用性

## 結果

**`0x1AE380` 有磁碟 raw backing，但目前識別到的既有 EXE 捕捉沒有保存該函式的載入後位元組。** 不能將磁碟上同 RVA 的資料直接當作已驗證的函式實作。本次没有讀取活程序、增加擷取、修改遊戲或要求新的授權。

## 入口與直接呼叫證據

新保存檔 `spawn_interface_live_20260927_1.json` 的 SHA256：

```text
44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a
```

該檔的 EXE `0x30FF50` 入口逐條解碼為 9 條指令，結束於 `0x30FF71` 的 `ret`。`0x30FF66` 的 `e8 15 e4 e9 ff` 直接呼叫 `0x1AE380`；回來後 `mov eax,[rax]` 取得 DWORD 回傳值。callee 的具體行為仍未由這段 wrapper 證明。

## 固定磁碟映像與 section

已先重新計算磁碟檔案 `F:\Game\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe` SHA256，符合固定值：

```text
f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06
```

檔案長度為 14,957,160 bytes；相關 PE section：

| 項目 | 值 |
| --- | --- |
| Section index | 0（從 0 起算） |
| 原始名稱 bytes | `20 20 20 20 20 20 20 20`，八個空格 |
| VirtualAddress | `0x1000` |
| VirtualSize | `0x13F364C` |
| 虛擬範圍尾端，exclusive | `0x13F464C` |
| SizeOfRawData | `0x663400` |
| PointerToRawData | `0x600` |
| raw-backed RVA 尾端，exclusive | `0x664400` |
| Characteristics | `0x60000020` |
| callee 在 section 內位移 | `0x1AD380` |
| callee 對應檔案 offset | `0x1AD980` |

因此該 callee 入口及接下來 256 bytes 都有磁碟資料。這 256 bytes 的 SHA256 是：

```text
7d39cb972d3a254d57d0b78e277aa191bd7c27e98efdc8bc7e24a69bed31e071
```

但同一 section 的已保存入口 `0x30FF50` 顯示明確差異：磁碟第一個 byte 為 `8B`，新捕捉第一個 byte 為 `48`。完整 4 KiB 也不相同。這證明 **raw offset 可換算不代表該磁碟資料等於載入後程式碼**；並不是已經取得 callee 的磁碟／記憶體差異比較，因為後者尚未保存。本次沒有對 callee 的 raw bytes 作函式語意解讀。

## 既有 EXE 捕捉覆蓋檢查

已重新核對三份捕捉檔案的 SHA、其 EXE 指紋，以及每段 bytes 的长度和 SHA。七個保存窗口如下，範圍皆為起点包含、終點不包含：

| 捕捉 | EXE RVA 範圍 |
| --- | --- |
| interface probe | `0x3494B0 .. 0x3495B0` |
| interface probe | `0x8C6730 .. 0x8C6830` |
| engine callee | `0x4ACDE0 .. 0x4ADDE0` |
| engine callee | `0x349110 .. 0x34A110` |
| engine callee | `0x8CCFA0 .. 0x8CDFA0` |
| engine callee | `0x8E1370 .. 0x8E2370` |
| spawn interface | `0x30FF50 .. 0x310F50` |

**全部不涵蓋 EXE `0x1AE380`。** 對工作區 JSON 的 `base_address`、`module_rva`、`runtime_capture` 標記搜尋只找出這三份 live capture 以及三份衍生 creation-path 證據，後者不是新的 EXE 捕捉。這是已識別捕捉的清單，不能推論整部電腦不存在其他未識別的檔案。

另有原先大型固定捕捉 `existing-code-evidence-25480438`，但其 image 是 **game.dll**（image size `0x4744000`、時間戳與 game.dll 指紋符合原報告），不能把其中相同數字的 RVA 當作 EXE 位元組。

## 產物

- `spawn_callee_availability.py`：只讀磁碟 EXE 與三份固定 JSON 的重播工具，沒有 process API。
- `spawn_callee_availability.json`：section／raw offset、來源 SHA、wrapper 指令、七個窗口及覆蓋結果。

此結果精確收窄剩餘資料缺口：wrapper 的直接下游已知，但 **EXE `0x1AE380` 的載入後函式實作仍不可用**。現有資料不足以繼續判斷它的配置容量、錯誤處理或玩家實體限制。
