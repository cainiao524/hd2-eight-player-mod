# Rank ID 表：Wwise 音效呼叫與保存資產的映射

## 結論

`142D870` 的三組 rank ID 已接到 Wwise plugin。前兩組是交給相同 event API 的開始／結束狀態事件 hash；第三組在查表後交給同一 plugin 的浮點參數 API。它們不是玩家 entity ID，也不是元件的儲存 ordinal。第三個 API 的精確匯出名稱與每個 hash 的原始資源名稱仍未確認。

**這項命名讓八槽方案可以分別處理「索引表的記憶體容量」和「音效選項如何對應額外玩家」；目前沒有證据可把三個現成選項直接擴寫成七／八個不同有效選項。** 對特定已保存 boot 映射，六個事件 hash 都存在，但第三組的兩個 hash 缺失；不能把這份表描述成三套完整有效的音效組合。

## 固定產物與核對

- [程式重播](indexed_float_rank_ids_replay.py)；[正式證據](indexed_float_rank_ids_evidence.json)。證據 SHA-256：`dfefbca1b590691cf498748d39554a2a020f93e5c8e7bbc6ded6a551df117461`。
- 主代理重播逐 byte 一致，另核對原 capture 的2,071筆遞迴指令記錄／1,924個不同位置，以及9個完整 unwind roots。重播本身列出1,923筆選定 instruction rows；重複引用與額外callsite的計數範圍不同。
- [資產擷取程式](indexed_float_rank_asset_extract.py)與[來源記錄](indexed_float_rank_asset_manifest.json)，後者 SHA：`2f172470d8c13495536e3844b8a51b46821e5f393185cd51f2f363721a03ef01`。
- 保存的[hash_lookup 資產](indexed_float_wwise_hash_lookup_current.bin)，1,048,584 bytes，SHA：`3b34c46a17f0aa1003a30cf23a6010c5f08fddcfc5ab9a9020ffd2ef06091557`。

本支線完成原 capture 與磁碟資產核對，未執行遊戲函式、讀取活程序、播放音效或安裝修改。原支線代理在補寫說明／交叉審查前受到用量限制；本說明由主代理依已落檔證據和原 bytes 接手完成，不將未完成的代理審查記成通過。

## 1. Wwise 名稱的證據

`4EDA90` 的 plugin 初始化以數值 `4B264F2E` 取得介面並保存到 global `3326318`。本地字典的 `wwise_plugin` 用已保存 `AAFF30` 的 MurmurHash64A／upper32 規則計算，得到相同值。

另有獨立 API 用途證據：`FC5550` 將字串 `wwise_trigger_event` 綁到 callback `FC4C50`。完整 callback 以 `AAFF30` 對輸入字串取 hash、右移32，再用 `12556E0` 映射，最後呼叫相同 plugin 的 `+338`。這支持將rank路徑的同一slot稱為event API，沒有只靠slot序號猜名稱。

Rank資料流如下：

| 狀態路徑 | ID來源 | 下游 |
|---|---|---|
| 新的移動條件成立、舊條件不成立 | 第一表 `RBP-70` | `1327F50 → 12556E0 → plugin+338` |
| 新的移動條件成立 | 第三表 `RBP-80` | `12556E0 → 1327FE0 → plugin+380`，另傳計算出的float |
| 新條件不成立、舊條件成立 | 第二表 `RBP-50` | `1327F50 → 12556E0 → plugin+338` |

此處「移動條件」描述record內float pair的差值／狀態判斷，不命名為特定腳步、地圖游標或其他聲音。兩個wrapper都先經plugin `+288`取得物件；沒有證明它為每個rank建立獨立音源。因此重用事件ID會否互相影響，也未經此證據解決。

## 2. Lookup 的實際行為

`1255800` 以 name hash `B9EE36888EF19818`、type hash `E3F2851035957AF5` 取得資源。後者按相同64-bit算法精確匹配 `hash_lookup`。它將資產解析為：

```text
u32 capacity_A
capacity_A × (u32 key, u32 value)
u32 capacity_B
capacity_B × (u32 key, u32 value)
```

兩張map的invalid key設為0、乘數設為2。`12556E0` 查第一張map，以 `(key*2+probe)&(capacity-1)` 探測，遇空key、key匹配或達到capacity便結束。空表／缺key回傳0，命中則回傳完整32-bit value。

`1327F50` 在lookup後直接把EAX傳給event API；第三組的caller也直接把lookup結果傳給浮點API，沒有加入「結果非零才呼叫」的檢查。這只證明0會被傳下去，不證明plugin如何處理0。

## 3. 已安裝資產的具體結果

本機Steam manifest記錄build **25480438**，與保存程式版本一致。以既有唯讀DSAR／DSAA reader取出boot archive `9ba626afa44a3aa3` 的指定資源：archive offset `58935280`、size `1048584`。六個使用到的來源chunk均保存壓縮／解碼SHA，並重讀核對；另掃94個loose patch的metadata，沒有同name/type覆寫，掃描沒有錯誤。

此範圍未窮盡其他bundled duplicates或loader優先序。Steam build相同亦不證明檔案未被改過，或執行期一定選中這份資源。

保存檔中兩張map各有65,536個buckets、20,848個非零key；第二張是第一張key/value的完整反向映射。全部第一張有效key按原lookup規則都能查回對應value。

| rank（零起算） | 第一組事件 hash → ID | 第二組事件 hash → ID | 第三組參數 hash → ID |
|---|---|---|---|
| 0 | `2E1387C5 → 6FAFF85C` | `56D7E815 → 256702C6` | `25065DD3 → 8BFC6B54` |
| 1 | `ED9E2BBD → 8AA7A7C5` | `CE12B5A6 → DF922243` | `6E61441F → 0`（key缺失） |
| 2 | `30E087B2 → 4C1121D2` | `D2D33C0C → AF9C974C` | `833E051C → 0`（key缺失） |

兩個缺失key另做完整key掃描，確定不在這兩張map中，並非僅一次probe未命中。這不代表當前遊戲必然發生錯誤，也不證明0是適合新增rank使用的參數。

本機專用三值 `07A65DB2 / 11D0ACB1 / 18752516` 在第一張map都存在，分別映射到 `2D8EEF0A / 81415B34 / A941F9BE`。它們只在目前slot等於selected local index的分支使用；不能直接當作第4個遠端rank的現成組合。

## 4. 名稱搜尋和八槽決策

有限搜尋涵蓋四份本地字典共156,898行，以及保存readonly中的186,922個ASCII runs。沒有取得九個rank hash的精確原始名稱。這不證明其他bank、字典或執行期資產中不存在名字；本輪沒有繼續猜詞或新增API擷取。

八筆方案仍須：

1. 修正四格stack map與三格rank表的實際記憶體界限。
2. 保留local分支與「找不到local時可能有八個未跳過rank」的條件。
3. 對額外rank明確選擇音效對應方式，並驗證開始／結束與浮點參數的配對及音源隔離；目前沒有足夠證據指定新ID。
4. 不把缺key返回0當成已驗證的fallback，也不以音效查表成功替代第五人生成與同步測試。

這項結果縮小了三組ID的用途範圍，尚未形成八人音效修改或可運行的八人Mod。
