# Player 資源清單與 roster 元件 239：離線證據交會

## 結論與來源界限

**FileDiver 隨附的明文資源快照中，`content/entities/player` 有九個元件索引，包含 `239`。** 同一份快照的 `dummy` 只有 `88`，`avatar_helldiver` 有 49 個元件，沒有 `239`。另一條獨立程式分析已確認：元件 `239` 的 callback 初始化會登錄四槽 roster 插入 `0x540920`。兩份證據共同解釋了 player 資源如何選到已知的玩家名單元件。

這裡的資源清單是 **FileDiver 的參考資料**。尚未證明它與目前安裝的加密檔解密後相同，或與本次遊戲執行期清單相同；不能把此靜態鏈寫成已觀察到玩家建立成功。

本輪沒有讀取遊戲程序、呼叫遊戲函式或修改安裝資料。

## 1. 固定來源及完整格式核對

| 來源 | 大小與 SHA-256 |
|---|---|
| FileDiver `generated_entities.dl_bin` | 46,612,588 bytes；`21377252b81fdbc670eba1e59a8ab64b170323df208f175e708992e4c1fb515e` |
| FileDiver 同名 `.gz` | 926,619 bytes；`5f1f54c39d51ddebdd8611b86701e038cdd9ae1821e03d67ca988962a03d19c7` |
| 本機安裝同名檔 | 46,612,636 bytes；`7df1a07e90c61e0b8398ecbc5c088074655900943bf1cd7e09f69bccedec4a2a` |

`.gz` 解壓後與參考明文逐 byte 相等。安裝檔開頭並非此明文的 `LDLD` header；它的長度恰好多 48 bytes，**不足以證明其明文相同，也不足以證明其明文不同**。本輪沒有解密安裝檔。

[重播程式](spawn_resource_metadata_replay.py) 固定上述 FileDiver 兩個檔案及五份格式／名稱原始碼的 SHA，依 `DLInstanceHeader` 和 `ParseComponentIndices()` 的格式，從頭走到檔案結尾：

- 272 個完整 instance，其中 270 個帶 component index。
- 首個 `EntitySettingsHashmap` 含 4,096 格、每格 32 bytes，共 1,909 個非零資源鍵。
- 每筆非空記錄的清單範圍均核對在首個 instance 內；三個指定資源另重播低 12-bit hash 與線性探查。
- 元件索引是 `uint16` 清單；4,096 是資源 hash 表容量，並非玩家人數。

對照欄位：resource hash `+0`、component list offset／載入後指標 `+8`、count `+0x10`、game-object 值 `+0x18`。程式端 lookup 只讀 count 的低 32 位；參考格式將其宣告為 64 位，本次三筆值沒有高位差異。

## 2. 三個資源的清單

| 資源 | Hash 表槽位／記錄檔案 offset | 元件數 | 包含 239 |
|---|---|---:|---|
| `content/entities/dummy` | 2971／`0x1737C` | 1 | 否；僅 `[88]` |
| `content/entities/player` | 2690／`0x1505C` | 9 | **是** |
| `content/fac_helldivers/cha_avatar/avatar_helldiver` | 2711／`0x152FC` | 49 | 否 |

player 清單位於檔案 `0x28B72`：

```text
3, 33, 41, 43, 226, 238, 239, 250, 260
```

完整三筆記錄 bytes、清單 bytes、索引、名稱對照與指令證據都保存在 [spawn_resource_metadata_evidence.json](spawn_resource_metadata_evidence.json)。三個資源均在其 hash 初始槽位直接命中。

`239` 沒有對應的 data-bearing instance 可供本解析器命名。這表示參考檔未在該表提供它的 data type；**不表示元件不存在**，因為 player 的索引清單明確包含它，而且程式中也有其 callback 登錄。

參考清單不同支持把 player 與 avatar 的後續分派分開分析；不能據此推定所有遠端、復活或替代資源永遠使用同一清單。

## 3. 捕捉程式如何載入及使用 metadata

`0xFDB440` 使用捕捉內的檔名字串 `generated_entities.dl_bin`（RVA `0x225D2A0`），透過既有介面取得資料；在 header 條件及 helper 處理後，將首段 payload 指標存至其入口物件 `+0xF12EA0`。同一函式還處理另一個資料段 `+0xF12EA8`，以及 `generated_entity_deltas.dl_bin`（字串 RVA `0x225D2F0`）到 `+0xF12E98`。

目前沒有替 `0xAACCC0/0xAAEDD0` 或檔案介面正式命名，也沒有把它們說成已執行的解密流程。已固定的是檔名字串、參數、header 條件、payload 指標及物件欄位資料流。

資源 dispatch `0x581320/0x581780` 從 `global[0x346BF98]+0xF12EA0` 取 metadata 表；查到資源後，按 `uint16` 清單分別索引 `+0xF0C110`、`+0xF0CB30`、`+0xF0D550` 回呼表。`0xFDA356` 將原 context 發布至該 global，並由相鄰 `0xFDA352` 把 context `+0x40` 傳给 callback owner 的初始化鏈。

本頁固定 **111 個指令位置、兩個檔名字串**；[獨立審查](spawn_resource_metadata_review.zh-TW.md) 另以不同解析方式重算 instance 與資源清單，核對原始 capture 的 bytes、SHA 及 unwind 邊界。

## 4. 與 callback、屬性及擴容的關係

[Callback 初始化證據](spawn_callback_registration_findings.zh-TW.md) 將元件 239 對應到：

| 階段的已知表 | 元件 239 的 callback |
|---|---|
| `+0xF0C110` | `0x540920`：四筆 roster 插入護欄 |
| `+0xF0CB30` | `0x540AE0 → 0x60C640`：屬性產生 |
| `+0xF0D550` | `0x540B10 → 0x6054F0`：後續處理 |

[屬性資料流](roster_component_binding_findings.zh-TW.md) 另確認：本地 peer 的 network index 由 `0x134F190` 取得，寫到 `roster + ordinal*0x20 + 0x3B4`，並輸出為 `index` 屬性。屬性產生階段受 creation params 首 byte 控制；不能說所有遠端 player 都會被填成本地 index。

因此八人擴容所需處理的具體元件路徑已縮小到實際登錄的 callback 及其欄位讀寫。仍缺少目前資源內容等同性、初始化後實際 callback 表、引擎下游實作、完整儲存搬移方案，以及五／八人實際生成、同步、結算驗證。
