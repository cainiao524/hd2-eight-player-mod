# 雙 float records 的五個子物件：初始化、搬移與共用池限制

## 結論與範圍

**後續更新：** [指定模板預算](indexed_float_template_budget_findings.zh-TW.md)已從四段建立流程導出每筆11格、新增四筆44格、八筆88格的條件式需求。本文件的240／480格保留為12個索引欄位的物理上界；其他pool用途、峰值、初始化與執行期模板等同性仍未閉合。

**初始來源續查：** [外層zero-fill證據](indexed_float_pool_initial_zero_findings.zh-TW.md)已說明k=0時used count／cursor／occupancy的最初零值來源。這補上更早的配置路徑；本文件所述「局部constructor沒有寫入」仍成立，使用後重入／reset的一致性仍未證明。

**直接清單續查：** [建立／清理清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)已逐項接上305個直接S，其中20個屬玩家記錄；八筆獨立儲存的兩份生命週期投影均為325項。其他owner、外部aliases與實際釋放仍未證明，不能由清單相同就宣稱整池實測歸零。

本支線只讀已固定的離線 capture，沒有查詢程序、擷取記憶體、啟動或修改遊戲。地址均為既有 game image 的 RVA。沿用既有來源鏈中的 `D`，每筆 record 為 `D+0x80E18+i*0x298`；本文件只閉合該 record 的五個 `0x78` 子物件及有限資源清理 callees。

**新增四筆時，五個子物件應各自重新初始化，不能複製既有 active 子物件當作新實例。** 每個子物件持有共用池索引；兩份 active 副本會指向相同資源，清理其中一份即清掉另一份仍引用的 node。把原有四筆移往新儲存則有不同前提：若 `D`、池 descriptor、外部 context 都維持原地址，這批 helper 沒有把 `S` 自身地址存進 node，因此觀察到的內部關係可保留；但仍必須轉移唯一所有權、停用舊副本並改好所有 caller/alias。這不是已證明任意 `memcpy` 搬移安全。

**256 格共用池是新增的容量限制。** 本批 generic helper 沒有以玩家數四為界，但它們也不會自動擴池。每個 `S` 物理上有 12 個 node index，新增 20 個 `S` 的物理需求上界可達 240 格；八筆合計 40 個 `S` 可達 480 格，且池還被其他 `D` 子物件共用。這是欄位容量推算，不是已讀到的模板需求。不能據此宣稱實際一定耗盡，也不能宣稱 256 一定夠。

**池滿可能留下部分配置。** `140C2E0` 在配置前先記住 requested template ID，逐格配置，池滿或容量為零就返回；已配置的索引保留。同 ID 下次呼叫在入口直接返回，不會補齊。八筆方案需處理可用格數與失敗狀態，不能把這個返回當作完成。

## 可重播產物

- `indexed_float_subobjects_replay.py`
- `indexed_float_subobjects_evidence.json`
- 本文件。

正式 JSON SHA-256：`5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54`。

重播核對 13 個完整 unwind roots、2 個由直接呼叫證明入口的 leaf、30 個 code spans、1,181 條 code instructions（CFG 皆可達）、5 個先前證據已涵蓋的 caller pins、122 個語義 pins。三個 cleanup switch tables 另列原 bytes、實際 indexed read / indirect jump，以及 image-base register 的 CFG reaching definitions，沒有用「無法反組譯」作為資料的唯一理由。

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\indexed_float_subobjects_replay.py' `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\indexed_float_subobjects_recheck.json'
```

腳本拒絕覆寫輸出。capture 的 report/data/identity 由既有 `inspect_capture.Image` 固定雜湊檢查；另外驗證兩份前置證據：

| 前置證據 | SHA-256 |
|---|---|
| `indexed_float_storage_evidence.json` | `11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378` |
| `indexed_float_consumers_evidence.json` | `503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578` |

## 1. 實際 constructor 是 `140C160`

`142B990` 的完整 constructor 以 `RBX=D`、`RDI=D+0x36F8=P` 建立子物件。record loop 的 `R14=record+0xA0`，在以下五處呼叫 `140C160`：

| Call RVA | RCX / S | record 內偏移 |
|---|---|---|
| `142BBC6` | `R14-0x78` | `+0x28` |
| `142BBDC` | `R14` | `+0xA0` |
| `142BBF3` | `R14+0x78` | `+0x118` |
| `142BC0D` | `R14+0x100` | `+0x1A0` |
| `142BC27` | `R14+0x178` | `+0x218` |

`142BB94` 的迴圈計數是 4，`142BC2C` 每次加 `0x298`。`142C9B0` cleanup 有相同五個呼叫及四次迴圈（`142C9D5`），並呼叫 `140C200`。新增四筆的 constructor 與 cleanup 均需涵蓋新儲存。

`140C160` 完整 root `[140C160,140C1FC)` 先把 `S[0..0x78)` 清零，再建立以下關係。`140C190` 不是本批已證 caller 使用的函式入口。

| S 欄位 | 初始化值 / 本批用途 |
|---|---|
| `+0x00` | constructor 的 RDX，外部 context A |
| `+0x08` | constructor 的 R9，即 `D` |
| `+0x10` | 第五個參數，外部 context B；caller 取 global `0x347CE90` 指向物件再加 `0x6D30` |
| `+0x18` | 清零；配置 node 時以 DWORD 複製到 `N+0x18` |
| `+0x1C` | 清零；之後保存 requested template ID |
| `+0x20` | constructor 的 R8，即 `P=D+0x36F8` |
| `+0x28..+0x58`（不含末端） | 12 個 DWORD node indices |
| `+0x58` | 活躍 node count，初始 0 |
| `+0x5C`、`+0x74`、`+0x75` | 初始化為 1 的狀態位元組；本支線不臆測完整業務名稱 |

constructor 清零後保留一個按 count 呼叫 `1408FE0` 的程式路徑，但新初始化的 count 是 0。把 constructor 直接套在 active `S` 會先丟掉舊索引，不能代替 cleanup。

## 2. 池的配置與具體相鄰界限

`142BAC6..142BB63` 建立：

| P 欄位 | 用途 | 本 constructor 明確寫入 |
|---|---|---|
| `P+0x00` | node backing pointer | `D+0x3718` |
| `P+0x08` | 每 slot 一 byte 的 occupancy pointer | `D+0x23F18` |
| `P+0x10` | used count | 本支線未閉合初始化來源 |
| `P+0x14` | capacity | `0x100`（256） |
| `P+0x18` | 下一次搜尋起點 | 本支線未閉合初始化來源 |

每 node `0x208` bytes，且：

`D+0x3718 + 256*0x208 = D+0x23F18`

所以第 257 格 node 的起點就是已使用的 occupancy 區。只改 capacity 立即失去此界限，必須重配 backing 並維持 descriptor/相關 consumer 的一致性。這裡不是可直接原地翻倍的空白區。256 次 constructor loop 逐格清 `0x208` bytes 並呼叫 `1408FE0`；這段没有證明 occupancy、used count、搜尋 cursor 何時被初始化，不能把「這裡沒寫」誤讀為它們在執行期未初始化。

同一完整 `D` constructor 還把相同 `P` 傳給 `D+0x80DA0`、`+0x81888` 等其他子物件，以及其他陣列迴圈。故 256 格不是這 20 個 record 子物件的專用配額；本支線不展開那些其他 consumer。

## 3. `140C2E0`：template → pool nodes

完整 root `[140C2E0,140C529)`：

1. 比較 `S+0x1C` 與 requested ID，相同就返回（`140C2E8..2F2`）。舊 ID 非零時先呼叫 `140C200`。
2. `template = image+0x3492F20 + ID*0xA0E8`。`140C319` 先把新 ID 寫入 `S+0x1C`。
3. 按 `[template+0xA0E0]` 的 count 配置，每 element `0xD68`。`12*0xD68=0xA0E0`，與 S 的 12 個 indices 相合；本函式未另外檢查 `count<=12`，模板有效性是前提。
4. 按 P capacity 與 byte occupancy 以 modulo 搜尋空位，設定 occupancy、used count 與 cursor，增加 `S+0x58`，把 pool ordinal 寫到 `S+0x28+elementOrdinal*4`。
5. `N=P.nodes+ordinal*0x208`；把 `S+0/+8/+10/+18` 複製到 `N+0/+8/+10/+18`。`N+0x20` 指向 template element、`N+0x28` 是 element type。type payload 裏還保存 template interior pointers，例如 `element+8`。
6. 呼叫 `1408FE0` 重設 type payload/event 狀態。type 2 可經 `12EE2D0` 取得五個 pointer，寫入 `N+0x68...`；它的內部與資源內容未展開。

**此函式沒有把 S 的地址存進 N。** 它有保存 `D`、外部 context、template interior pointers；因此若只把 record storage 移到別處，而 D/P/templates 穩定，這些 pointer 不因 record 地址改變而自動失效。若連 D 一起搬，`S+8`、`S+20`、P backing 指標及已配置 `N+8` 等都涉及重新接線；不能只修 S 的一個 pointer。

容量為零在 `140C35D` 返回；找滿 capacity 格仍無空位在 `140C38B` 返回。沒有 grow、回滾全部 allocation 或重設 requested ID。已配置數目由 `S+0x58` 保留，cleanup 可遍歷那些已取得的 nodes，但「下一次同 ID 補齊」不成立。

## 4. cleanup 與唯一所有權

`140C200` 逐一用 S indices 找到 N，呼叫 `1408F00(N)`；之後把相應 occupancy byte 清 0，若原先占用则 `P.used_count--`。最後 `S+0x1C=0`、`S+0x58=0`。索引舊 bytes 可以留著，count=0 才使它們不再被此物件清理。

`1408F00` 按 `N+0x28` type 清外部資源，最後 tail-call 已由前置 storage 證據涵蓋的 byte-fill helper，清整個 `0x208` node：

| Type | 有限閉合的 cleanup |
|---|---|
| 1 | `14066A0(N+0x30, [N+8]+8)`；一個 `1403070` entry 及兩個 12-byte entries |
| 2 | `1405580(N+0x30, [N+8]+8)`；兩個 `1403070` entries，並清五個 pointer resources |
| 3 | 以 `N+0x30` 的 context 與 `N+0x40` handle 呼叫 API，再清 handle |
| 4 | `1407960(N+0x30, [N+8]+8)`；四個 12-byte entries，加兩組各兩個 `1403070` entries |

上述 `[N+8]+8` 是先取 `N+8=D`，再取 `[D+8]` 的 resource/context 值。`142BA47..4C` 已證該值由 D constructor 的 API 回傳保存。不能提前銷毀 D，再期待這些 node cleanup 仍有效。

`1403070` 和兩個 inline switch 均按 entry type 選 API slots `0x148/0x118/0x1A8/0x28/0x88/0xA0`，傳入 owner resource/context 及 DWORD handle，再清 12-byte entry。三張六項 RVA 表的讀取與跳躍已閉合。這些 API 的實際執行期 targets 不在此證據內，故沒有冒稱引擎釋放已執行或已實測。

type 4 的四個 entries 是一個 node 的內部資源結構，不是玩家四槽。不要把這個數字直接改為八。

## 5. 其餘指定 helpers

| Helper | 完整已證範圍 | 指標/計數依赖 | 對八筆的意義 |
|---|---|---|---|
| `140C630` | `[140C630,140C69E)` leaf | S count/indices/P → N；template type 2 且 selector 符合時改 `N+0x40` | 不以四玩家限界；需有效索引與 node |
| `140C6A0` | `[140C6A0,140C70E)` leaf | 同上，改 `N+0x44` | 同上 |
| `140D710` | `[140D710,140D8B1)` | S count/indices/P；template events；N event state | 事件數受模板控制，非玩家四槽 |
| `142F6E0` | `[142F6E0,142F77A)` | RDX 是 S；R8D 是 template ID；呼叫 C2E0，再按 count 標記 nodes，tail-call D710 | 入口 RCX 在此 helper 不被讀；不能因 caller 傳 D 就說這裡再直接 index D |
| `1408FE0` | `[1408FE0,14090C6)` | N type；清 type payload / `N+0xB0` 的 `0x140` event bytes | 保留 N 共用 header 的 context/template 關係；不能當成完整 destructor |

兩個 leaf 的入口分別由既有 consumer 的 `142DE4F` / `142DE5E` 直接 E8 call 證明；完整 bytes 及所有內部 branches 收入正式 JSON。

`140D710` 的 event count 來自 `[templateElement+0xD64]`，event stride `0xFC`，起點 `+0x38C`；node 的 event state 起於 `+0xB0`，stride `0x20`。兩邊物理均容十個 (`0x38C+10*0xFC=0xD64`；`0xB0+10*0x20=0x1F0`)。本函式未再 clamp count；同樣是模板有效性的前提。事件變化時的 `72FBE0` 只在此閉合到 global context / event ID 呼叫參數，沒有擴展其內部。

`142F6E0` 讀取第五個浮點參數，與 readonly `0x23C6D70` 的 `1.0f` 比較，以 boolean 決定 event ID `0xA` 的狀態。不是整數玩家 index 或八人容量。

## 6. 八筆方案的具體要求與尚未證明事項

1. 配置八筆 record storage 時，新四筆的五個 S 逐一 fresh-initialize；沿用仍有效的 D、P、context A/B。不要複製舊 S 的 count/indices/active 資源。
2. 原四筆若搬移，必須確保舊位置不再參與 cleanup/update；所有持有原 S 地址的 caller/alias 必須改好。本有限 helper 集合沒有發布 S 自址，但未窮盡全遊戲 alias。
3. 原 constructor 與 cleanup 的四次外層迴圈均須轉到新八筆儲存。其餘已證 record consumers 仍以既有 `indexed_float_consumers` 清單處理；本支線沒有重掃那些 consumer。
4. 容量處置需要實際 template node counts 與共用池佔用預算。若擴池，原 node area 在 256 格末端緊接 bitmap，需重配並同步相關 pointer/consumer；本支線不能只憑 P 有 capacity 欄位就宣稱任意擴池安全。
5. 處理池滿的 partial state 與 same-ID 不重試行為；具體採預留、事前保證容量、或重設/回滾是後續設計決策，沒有在此 patch。
6. 關閉時保持 D/resource context 存活，對每個活躍 S 恰好清理一次，再釋放擴出的 storage。clone 後讓兩份都 cleanup 不成立。

未讀取 writable template globals、live occupancy、API targets 或執行期資源；沒有第 5–8 人測試。因此此結果只把「八筆必須如何保存/清理資源」具體化，不能證明八人連線已成功。
