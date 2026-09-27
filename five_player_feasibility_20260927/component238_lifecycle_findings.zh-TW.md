# 元件 238：四組每人儲存、生命週期及 owner 邊界

## 結論與適用範圍

本輪只研究元件 `238`，來源是既有固定 `game.dll` code / readonly / unwind capture；先核對 `player_component_capacity_evidence.json`，再追 callback、搬移與 owner 生命週期。沒有 live query/read、capture、probe 或遊戲 patch。所有地址是固定版本 RVA，未修改總報告。

**不能只擴大 `+0x948` 指標陣列與 `+0x96C` 的 68-byte 記錄。至少還有每個 ordinal 一個 byte 的區域，以及 `+0xA7C` 的 64-byte property 記錄，需要一起重配。** 後者四項結束後只有 4 bytes 就是已證明的下一個 roster 物件。

此元件的系統物件 `S=owner+0xE9FC98`，對外 global 是 `0x33264F8`，registry tag 是 **`0x18`**。初始化會載入 body settings、customization armor sets、passive bonuses 的資源，支持它涉及角色身體／自訂裝備資料；尚未取得正式 component 類別名称。FileDiver 參考 `player` 資源包含 index 238，仍不等於已驗證目前安裝或執行期資源也如此。

## 1. 十张 callback table 的確定結果

沿用已驗證 leaf initializer `556D90..55E1E2`，驗證整段 SHA 和 2127 組 assignment 結構，只輸出元件 238 的八組寫入，不重新輸出整張龐大表。入口由 `568239` 的真實 call 證明。

| Table base | index 238 slot | 明確註冊入口 | 已讀取的程式行為 |
|---|---|---|---|
| `F0B6F0` | `F0BE60` | `5405D0` | 以 total count 追加 pointer 和清零的 0x44-byte 記錄；`count+1<=4`，失敗寫零位址 |
| `F0C110` | `F0C880` | `540660` | 依 creation params byte 0 分類插入，維護三個計數與 high water；相同四項 guard |
| `F0CB30` | `F0D2A0` | `5407E0 → 87B7B0` | 重排參數，建置 64-byte property values 與 12 個 descriptors |
| `F0D550` | `F0DCC0` | `540810 → 874290` | 以 entity ID 查 ordinal，從 property 記錄消費資料並初始化 primary record |
| `F0DF70` | `F0E6E0` | `540820 → 873C10` | 以 entity ID 查 ordinal，存取 primary 和 property 記錄 |
| `F0E990` | `F0F100` | `540740` | 從 map 移除 entity，減少計數，按分類用 `87B5D0` 補位 |
| `F0F3B0` | `F0FB20` | `540830 → 87C120` | 交換 ordinal 的 pointer／0x44／0x40 資料，更新兩個 map value，增加 prefix count |
| `F0FDD0` | `F10540` | **initializer 未寫入** | 無法據此推出 zero、預設函式或執行期入口 |
| `F107F0` | `F10F60` | `540840 → 87C480` | 交換同三組資料、存取 `+0x968+ordinal` byte 區域、更新 map value，減少 prefix count |
| `F11210` | `F11980` | **initializer 未寫入** | 同上，未證明初值或執行期入口 |

因此是 **八個明確 assignment，加兩個已確認沒有 assignment 的 slot**，不能寫成十個非空 callback。未辨識的 callback 階段保留 table 地址與實際行為，不以表排序猜測階段名稱；初始化後改寫或未捕捉程式亦未排除。

## 2. 外層 owner、下一成員與 tag aliases

### 同一物件來源

`FDA352/FDA375` 將 context `+0x40` 傳入 owner constructor `551B60`；`551B7A` 保存其 entry pointer，`551B7D → 568230` 發布內嵌成員 globals。

- `568EBA/568EC1`：`global33264F8 = owner+E9FC98`。
- `568EC8/568ECF`：`global3326468 = owner+EA0818`，後者已確認為 roster。
- 兩者相差 **`0xB80`**。並有 `5565D7/5565DE` 與 `5565EF/5565F9` 分別以這兩個地址呼叫初始化，非僅地址相似。

### 直接 owner aliases

| 路徑 | 用途及地址 |
|---|---|
| `5565D7/5565DE` | 以 `owner+E9FC98` 呼叫 `87BC90` 初始化 |
| `5565E3/5565EA` | 同地址傳給 `B24BD0` 註冊 tag 18 |
| `56534C/565353` | owner destruction 呼叫 `873A70` 清理資源儲存 |
| `565358/56535F` | 同地址傳給 `B2FC70` 移除 registry aliases |
| `569B0A..569B26` | 該物件起始 qword 非零時，清理後以 `873370` 重新載入資源 |
| `57128D/571290 → 5727D6 → 57324A..573254` | owner tick 保存 entry owner 到 RDI 與 `[rsp+68]`；RDI 中途借用後，在 `5727D6` 從該 stack slot 恢復，再形成成員地址，呼叫 `874D80` |
| `57DFB5..57E016` | owner 批次分類搬移，呼叫 `87B5D0` 並更新 counts |
| `BD13BB/BD13C9` | 從 owner global 的內嵌地址呼叫 `87BB30`，反序列化 property record |

批次路徑還有一個直接 alias：**`57DFE6` 讀 `owner+EA0584`，恰為 `S+8EC` 的 prefix count**。即使只搬動部分 header／陣列，也需留意這個非 `S+offset` 形式的使用。

### registry aliases

`B24BD0` 將 `(S, tag=0x18)` pair 加入 `global3326E68` 的七個 16-byte entry lists：

```text
C98, +CC0, +CD8, +CF0, +D18, +4250, +4268
```

`B2FC70..B2FEB0` 逐表按物件 pointer 找 entry，減少 count 並用末項覆寫移除位置。這個無 unwind leaf 的 entry 由 `56535F` call 證明，重放涵蓋兩條 RET 路徑及所有內部跳轉。

**若搬動整個 S，只修改 global33264F8 不夠。** 上述直接 owner 地址、已發布 global、七組 registry aliases 都必須維持同一個有效物件身份；若另設陣列而保留 S，也仍需改寫直接使用固定陣列位移的讀寫者。

## 3. 儲存布局和八項在原位擴張的衝突

下列範圍均相對 S，採用半開區間 `[start,end)`。

| 儲存 | 現有範圍 | 元素寬度 | slot 4 寫入範圍／位置 | 衝突 |
|---|---|---:|---|---|
| Entity pointers | `948..968` | 8 | `968..970` | 原本四個 ordinal byte，以及 primary slot 0 前 4 bytes |
| Ordinal byte 區域 | `968..96C` | 1 | `96C` | primary slot 0 第一 byte |
| Primary records | `96C..A7C` | `0x44` | `A7C..AC0` | property slot 0 全部，再加 slot 1 前 4 bytes |
| Property records | `A7C..B7C` | `0x40` | `B7C..BBC` | 前 4 bytes 尚在下一成員前，之後跨入 roster `S+B80` |

`87C576/87C581` 證明 `S+0x968+ordinal` 已有 byte 讀寫；這裡稱它為 ordinal byte 區域，未證明每個值一定是 boolean 或其完整用途。`87B5D0` 本身沒有複製這個 byte 區域，不能替原程式假定它必須與其他資料以相同方式搬移。

property slot 4 並非只碰到未知 padding：鄰接 roster 初始化 leaf `60C9C0` 在 `60CA39/60CA44/60CA4F/60CA57` 寫入 roster `+8/+10/+18/+20` qwords，這些都落在 hypothetical property slot 4 跨越的區域。因此四組陣列無法原地直接加長。

### 八項所需邏輯資料

每人已定位的四組內容為 `8+1+0x44+0x40=141` bytes；八項合計 **1128 bytes (`0x468`)**，比四項增加 **564 bytes (`0x234`)**。這不含 alignment、改寫機制、其他未窮盡的 consumer，也不是整體八人模組的最小 allocation 大小。

entity→ordinal map 另占八筆 key/value pairs，即 `S+[8F0,930)`，descriptor 位於 `+930`：

- `+938=8` 是 map entry 數。
- `+93C` 為 sentinel，數值來自未捕捉 global。
- `+940=2` 為 hash multiplier；linear probing 使用 `(capacity-1)` mask。
- `172F790` 最多搜尋 capacity 次，若找不到 key 或空項，最終會對零位址寫入，並無動態擴容。
- 八個有效 entity 物理上可填滿八項表；**不能把 map 的 8 直接當成八人資料已可用**。若採用 16 項以維持原本每玩家兩個 map slots 的比例，另需 64 bytes backing。這是具體設計選項，未證明 16 是唯一可行值。

## 4. 初始化、分類插入、移除與搬移

### 初始化

`87BC90` 的真實 entry 由 `5565DE` call 固定。它：

1. 清零 `S+8E4` qword，亦即 total 與 active 兩個 dword。
2. 設定 inline map pointer `S+8F0`、capacity 8、sentinel、multiplier 2。
3. 清理八筆 map pair，然後 tail jump 至 `873370`。

`873370` 會清理 `S+D8` 起的 `0x808` bytes 資源儲存，並載入下列捕捉到的 readonly 字串：

- `generated_body_settings.dl_bin`
- `generated_customization_armor_sets.dl_bin`
- `generated_customization_passive_bonuses.dl_bin`

不能把這個 initializer 說成已清零所有每人資料：這個已讀取區塊沒有完整涵蓋 high water `+8E0`、prefix `+8EC`、ordinal bytes 或所有 property rows 的初值。primary 0x44 row 由 append 清零，property row 另由 property callback 建立；重配必須保留兩階段資料生命週期。

### 三個計數與 high water

| 欄位 | 依指令行為採用的名稱 |
|---|---|
| `+8E4` | total `N` |
| `+8E8` | active 分類終點 `M` |
| `+8EC` | flagged prefix 終點 `A` |
| `+8E0` | `max(old,M)` high water |

這些名稱描述範圍分割，未替 flagged 分類猜測完整網路 authority 含義。

`540660` 的 creation params byte 0 非零時，在 A 插入；若 `A<M`，先把 A 搬到 M。其餘插入 M，然後維護 N/M/A 與 high water。簡單入口 `5405D0` 則直接在 N 追加；兩者都明確檢查 `N+1<=4`。

`540740` 先以 entity ID 呼叫 map removal，取得原 ordinal；再依其是否屬於 active 範圍及 entity `+14 bit0`，縮短對應計數，用 `87B5D0` 將分類尾端或 total 尾端搬到移除位置。這與只增大 append guard 不同，需要維持分類不變量和 map value 一致。

### move helper 與分類 swaps

`87B5D0(S,destination,source)`：

1. source==destination 時直接返回。
2. 複製 source entity pointer 至 destination。
3. 完整複製 primary `0x44` bytes。
4. 完整複製 property `0x40` bytes。
5. 取移入 entity 的 ID，在 S 的 map 找到該 key，把 value 改成 destination ordinal。

`87C120` / `87C480` 另有完整 swap 實作，分別增加和減少 prefix count；不能以為所有搬移都集中於 `87B5D0`。兩者會交换 pointer、0x44 record、0x40 record 並修正兩筆 map value；後者還有前述 ordinal byte 存取。

property callback `87B7B0` 每個 entity 產生 **12 個欄位 descriptors，並非 12 個玩家**，payload 是 `0x40` bytes。`87BB30` 以 map ordinal 反序列化同一種固定大小記錄，故只更改 append 和 move 而遺漏 property writer/reader，仍會使用舊地址。

## 5. 收束後的修改範圍

由本次證據支持的八項重配工作至少包括：

1. 重配 pointer、ordinal byte、primary 0x44、property 0x40 四組內容，避免三層相鄰覆寫。
2. 決定 map backing 是否保留八項滿表或擴為 16 項，維持 descriptor、sentinel、probe mask 與 backing 一致。
3. 一起處理兩個 append、remove、move、兩個分類 swap，以及 property 初始化、後續消費及反序列化地址。
4. 保持 N/M/A、high water、entity→ordinal value 一致；不要將 network index 當作此處的 ordinal。
5. 若整個物件改位置，處理 owner 初始化／析構／重載／tick／批次搬移／反序列化、global 與七張 registry aliases；若只移出陣列，則修正各固定 offset consumer。

這是收束到具體布局與生命週期的研究結果，**仍未窮盡此 global 的所有其他消費者，也沒有 runtime invocation、第五人或八人測試**。

## 6. 產物與重放

- `component238_lifecycle_replay.py`
- **正式版本 `component238_lifecycle_evidence_v2.json`：1652 條 unwind 指令、212 條 proven-leaf 指令、82 個另外固定的 pins**。
- Evidence v2 SHA-256：`ac68b8cc938dc56288c9db7fa9a41d8a64f84fdd353fee6ff3414f6c35e0424b`。
- v2 補齊 owner tick 的 stack-save／restore 鏈：既有 `571290` bytes `48894c2468`（保存 RCX 至 `[rsp+68]`），新增 `5727D6` bytes `488b7c2468`（從 `[rsp+68]` 恢復 RDI），兩者均已核回固定 capture 的合法指令邊界。初版 `component238_lifecycle_evidence.json` 只保留審核經過；其餘分析內容不變。
- `component238_lifecycle_global_xrefs.json`、`component238_lifecycle_owner_scan.json`：篩選過程資料；位移命中本身不作同物件證明。

重放命令，output 必須尚不存在：

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  five_player_feasibility_20260927/component238_lifecycle_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/component238_lifecycle_recheck.json
```
