# 元件 33／250 生命週期證據獨立複核

## 目前結論

**v2 已通過本次範圍內的獨立複核，兩項解讀問題均已修正。** 原版將 `[0x160,0x164)` 列為未分類間隙，但已保存的函式本身證明該處是另一組依 ordinal 存取的 byte 區域；新版已改正，並分開記錄分類增加／減少路徑的 copy、swap 與 primary record 清零行為。

複核範圍限於既有 `component33_250_lifecycle_replay.py`、evidence、固定 capture，以及後續落檔的 findings；沒有新增其他元件探索或 live 存取。這不是八人執行結果驗證。

## 1. 重放與來源核對

- 獨立執行作者 replay，輸出 `component33_250_lifecycle_review_recheck.json`。
- 輸出與原 `component33_250_lifecycle_evidence.json` **逐 byte 完全一致**。
- 原版 SHA-256：`a2ef7535597211ef2a36045161d6517665e3edb44ff72c5fa87272b1b0f64fb9`。
- 除了重跑作者 assertions，另以 `inspect_capture.Image` 獨立讀固定 capture，逐 code body 核 SHA、起訖、指令數、RVA、bytes 與 asm，共 **1883 條指令全部一致**。
- callback initializer 使用已證明入口的 leaf fingerprint；缺少 assignment 的 slot 有清楚保留初值未知，未誤報為 runtime null。
- v2 再次獨立重放至 `component33_250_lifecycle_review_recheck_v2.json`，與正式 `component33_250_lifecycle_evidence_v2.json` **逐 byte 完全一致**，SHA-256 `dfb125ab3edd6b9672eb725981beecb91e1768da9d44b92522e28fd971155280`。
- v2 的全部 1883 條 code-body 指令與上述已獨立核對的原版完全相同；另將新版所有 semantic pins 逐條核回固定 capture 的合法指令邊界、bytes 與 asm。

## 2. 已確認成立的核心結論

### 元件 33

- `5683E6/5683ED` 發布 `global33267B8 = owner+3CA0`，`5683F4/5683FB` 發布下一成員 `owner+3F58`；兩者距離 `0x2B8`。
- `+70` pointer 四項結束在 `+90`。`666DEB` 讀正確 global，entity→ordinal map 的 value 經 `666E50`、`666E56` 成為 index；`666E9E/666EA9` 對 `+90+ordinal` 有明確 byte 讀寫，所以 pointer slot 4 的 `[90,98)` 會覆蓋已使用 byte 區域。
- ordinary ordinals 0–3 的 byte 使用區是 `[90,94)`；原版保留 `[94,98)` 未分類，沒有拿它當四個未使用玩家槽，這個界限合理。
- primary `+98`、stride `0x50`、四項結束 `+1D8`；secondary `+1D8`、stride `0x38`、四項結束 `+2B8`，與下一成員起點相同。
- `665FE0` 明確是 **source→destination copy**：pointer + 0x50 + 0x38，並改写移入 entity 的 map value；它不複製 `+90` byte 區域。
- `666DD0` 的 `+90` byte 路徑只證明 **單向 copy**，不是雙向 swap。暫存一個 byte 的存在，不代表程式真的做了兩側交換。
- owner 初始化、反註冊、批次 partition 路徑使用直接 `owner+3CA0`；tag `0x7C` 寫入 registry 的 `+D18` 與 `+1F80` lists，反註冊的 pair 搜尋與末項覆寫吻合。

### 元件 250

- `568F62/568F69` 發布 `global33266D0 = owner+EB5178`，下一個 `owner+EB52E0` 距離 `0x168`。
- pointer `+70` 四項結束 `+90`，primary `+90` stride `0x34` 四項結束 `+160`；pointer slot 4 直接撞 primary slot 0。
- `+164+ordinal` bytes 有 property writer `543486` 寫入 1、move helper `671686/67168F` 複製、分類路徑完整 swap。四項結束 `+168`，正好到下一個已發布成員起點。
- `671610` 是 **copy**：pointer + 0x34 record + `+164` byte，然後更新 map value；没有把它誤認為逐 byte 交換的理由。
- owner constructor `5566DC/5566E3` 直接傳成員地址給 `671910`，緊接呼叫 `B28040`。作者有驗證 `671910` 不改 RCX 且不呼叫其他函式，因此 registration 得到相同地址。
- tag `0x7F` 註冊八個 lists：`+48/+1218/+1C78/+1D10/+1D68/+1F98/+5900/+5918`；`B38710` 的移除路徑與之相符。只改 global 而不處理 owner aliases 和 registry pointer 不足。

## 3. 已在 v2 更正的兩點（保留審核經過）

### A. 元件 250 `+160` 是第二組 ordinal byte 區域

原版 `manually_derived_layouts.250.unclassified_gap = [160,164)` 已從新版移除，改列獨立 byte array，並補充四個相關 copy pins。

| 指令 | 已確認操作 |
|---|---|
| `671CBB` | RSI 由 global33266D0 取得 |
| `671D4A → 671D0E` | map value 成為 ordinal RBP |
| `671D07` | R14D 由同物件 prefix count `+14` 取得 |
| `671DB4` | 讀 `[RSI+R14+160]` byte |
| `671DBF` | 寫 `[RSI+RBP+160]` byte |
| `671F1B`、`671F67..671F6B` | 另一分支同 global，來源 ordinal 為 prefix-1 |
| `67208E/672099` | 相同 `+160` byte 的單向 copy |

因此元件 250 至少需要維持 **兩組** byte 區域：`[160,164)` 和 `[164,168)`。若原位加長，第一組 ordinal 4 的 `+164` 會撞第二組 ordinal 0；第二組 ordinal 4 的 `+168` 會到下一成員起點。

這不要求替第一組 byte 猜出 boolean 語義，但必須把它列入儲存重配。`+164` 的雙向 swap 可由 `671DF7..671E1A`、`6720D1..6720F4` 完整讀／寫序列證明；`+160` 的上述兩段只有單向 copy。

### B. 元件 250 的兩個分類 callback 對 primary record 行為不同

- `671CA0` 增加分類的分支交換 entity pointers；之後 `671D78..671D90` **清零目標 0x34 record**。index 已在 prefix 邊界時，`671D1C..671D3A` 也清零該筆記錄。這不是完整 primary-record swap。
- `671F00` 減少分類分支，`671FD1..672060` 才有以暫存區實現的 primary record 雙向交換。

若 findings 使用「兩個 swap callbacks」作方便稱呼，仍須具體說明這個差別，不能推論增加分類時會保留兩邊原 primary 資料。

## 4. 完成狀態與界限

已取得完整 `component33_250_lifecycle_findings.zh-TW.md`，確認其使用正式 v2 SHA，明確記錄 `+160/+164` 兩組 byte array、`671610` 不複製 `+160`、分類增加路徑清零 primary record、減少路徑交換 primary record。描述與固定機器碼及新版 JSON 一致。

因此新版可用於本次儲存布局與生命週期總表；舊版布局 JSON 只保留為審核過程記錄。未發現仍需阻擋整合的本輪範圍內問題。

不把 callback assignment 視為已觀察到的執行期呼叫、不把缺少 assignment 視為 null、不把 component ordinal 視為 network index。此複核亦未證明已枚舉全體 aliases／consumers。
