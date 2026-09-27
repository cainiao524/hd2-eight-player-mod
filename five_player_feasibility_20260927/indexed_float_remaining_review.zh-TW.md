# 雙 float 剩餘路徑：主代理核對記錄

## 審查狀態

三個支線代理已保存程式與證據；在後續交叉審查階段均因用量限制停止。主代理接手完成下列原始資料核對及關鍵語義審閱，沒有把未完成的代理審查標記成通過。

| 支線 | 正式證據SHA-256 | 本次核對 |
|---|---|---|
| external index | `c83db6d2e7c5033b3127d95227f29d24e11605415b55616d9854c2245ed4bf5d` | 重播逐byte一致；原bytes／asm／指令邊界3,397筆遞迴記錄，3,296個不同位置；12完整roots。另獨立重建12個正常CFG、14項reaching-definition查詢及2條必要邊檢查。 |
| subobjects | `5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54` | 重播逐byte一致；原bytes／asm／邊界1,436筆記錄、1,186個不同位置；13完整roots、2個direct-call leaf入口。逐讀初始化、配置、部分失敗與cleanup邏輯。 |
| rank IDs | `dfefbca1b590691cf498748d39554a2a020f93e5c8e7bbc6ded6a551df117461` | 重播逐byte一致；原bytes／asm／邊界2,071筆記錄、1,924個不同位置；9完整roots。另解析保存資產的兩張map及12個key的完整搜尋結果。 |
| helper boundaries | `c70e0f48ce069decf271f9b69631695da41faaa7c5a373263d0f57a315e6e5d6` | 主代理自己撰寫的有限分析；以另一段檢查碼核518筆記錄、440個不同位置及4完整roots。未取得另一代理的獨立語義審查，不宣稱此項已經交叉審查。 |

機器核對的計數與指紋另存於[核對結果](indexed_float_remaining_root_review_checks.json)。不同集合包含重複引用、caller pins與候選函式，不能相加作全遊戲覆蓋量。

## 1. 原始資料核對方法

獨立檢查碼重新讀取固定capture，以unwind fragment起點解碼建立指令邊界，逐筆對照原bytes、SHA和asm。兩個沒有unwind的leaf只接受已保存且重新核回原bytes的直接E8 caller；不從任意候選byte開始解碼。

每個宣稱完整的root都重新列出所有chained unwind fragments，與證據所列集合比較。帶switch table的末段仍先核整段原bytes，程式／資料分界由實際table引用另行支持。這確認保存範圍，沒有以數量或成功JSON輸出替代語義驗證。

## 2. q 來源與必要分支

主代理逐讀`142EED8..142EF9E`：同一global `347CEF0`提供owner，`+16390`是count，`+B3A8`是64-bit查找key，`+16398+p*20`比較peer，`+163AC+p*20`取得32-bit q。ECX寫入後零擴展，q=-1返回，其他值用64-bit乘`298`選D的float pair。這段沒有中途call或`q<4`條件。

獨立重建的CFG確認，移除peer命中邊或q非sentinel邊，都使兩個float讀取不可達。對R9 owner、RDI D與RCX q，以及constructor／migration的其他關鍵暫存器，14個定義集合與作者一致。此分析採正常控制流；非揮發暫存器使用標準ABI前提。Constructor跨`B2ABD0`使用的R8另核該完整helper無call／無R8改寫。

`B90B20`的index來自第五個參數；第六個byte參數不同。Receiver的confirmed table容量與寫入值範圍沒有混為一談。Host migration重用既有index，支持「q不能一律視為0」；未證明所有host setter或封包解碼限制。

## 3. 子物件的所有權與池满

重新審閱`140C160/140C2E0/140C200/1408F00`及D constructor後，以下結論成立：

- Fresh constructor清`0x78`、配置context與D/P指標；不能用它代替active物件的cleanup。
- 每個S的12個DWORD是pool node的索引。配置時複製context、D與template指標至node，沒有在這條路徑發布S自身地址。
- Pool node backing的256筆末端正好接上occupancy backing；不能單改capacity後原地延伸。
- Requested ID在開始配置前已保存；容量0或找不到空位會直接退出，已配置count保留。同ID入口早退，故沒有自動補齊部分配置。
- Cleanup依S的索引先清node資源，再清occupancy／調整used count，最後清S的ID與count。

Active clone會讓兩個S指向相同node，清理一份後另一份的引用即失效。這裡沒有宣稱必然發生兩次外部free，因node cleanup本身會清type／資料；需要保留的是唯一所有權與仍活躍的引用。

240／480格為合法模板count不超過12時，新增20個／全部40個S的索引欄位容量算式；不是目前模板要求、實際峰值佔用或256必定不足的觀測。P used-count、cursor及occupancy初始化的完整上游仍未閉合。

## 4. Rank ID 與磁碟資產

主代理重新讀取lookup／loader及兩個Wwise wrapper：資產中的第一張map供`12556E0`使用，invalid=0、multiplier=2；缺key返回0，兩個rank呼叫路徑均未另檢查返回值。

保存asset按loader實際格式完整解析，兩張map各65,536 buckets、20,848個非零key；九個rank與三個local hash的直接key掃描與作者結果相同。兩個參數key `6E61441F/833E051C`確實不在兩張map中；其餘被列為存在的10個key均出現一次。這與原probe結果一致。

磁碟擷取程式由主代理撰寫，來源chunk有壓縮／解碼指紋及重讀檢查，94個loose patch沒有匹配覆寫。未取得另一代理對擷取程式的完整獨立審查，也未核所有bundled duplicates／runtime loader選擇。結論限定這份保存資產；未斷言原版故障、0的API語義或可直接重用現成ID。

## 5. 結論的實際界限

本輪可用來更新必要改接範圍、索引意義與資源生命週期設計；不能據此將候選方案標為可安裝或已完成。沒有新增live擷取、配置遊戲記憶體、載入補丁或多人驗證。第四次`EXE+1AE380`擷取仍未執行。
