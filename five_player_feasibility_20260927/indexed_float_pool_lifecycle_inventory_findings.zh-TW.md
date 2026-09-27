# 共用池直接子物件清單：305 項建立／清理對應與八筆搬移條件

## 結論

**後續容量補證：** [可選成員與四組主模板](indexed_float_pool_optional_members_findings.zh-TW.md)已接上其他清單成員的`142F530/142F780`更新路徑。四種主模板各一格，但false旗標路徑沒有直接回收相應可選S；估算池容量時仍需計入未回收的既有配置。

完整 `142B990` constructor 中，直接呼叫 `140C160` 建立的 **305 個 S 子物件**，與完整 `142C9B0` cleanup 中直接呼叫 `140C200` 的 **305 個 S**，位址及順序完全相同，各位址恰好出現一次。

其中玩家記錄有 `4*5=20` 個 S，其餘直接成員有285個。八筆方案把玩家記錄增為 `8*5=40` 個 S 後，這份生命週期清單需要 **325 項**。305／325是持有節點索引的子物件數；實際pool node占用仍由活躍模板與當前狀態決定。

Python位址推演得到：

| 情境 | 建立／清理項數 | S 的 `78`-byte 範圍重疊 |
|---|---:|---:|
| 原四筆、原儲存 | 305／305 | 0 |
| 假設只把玩家迴圈改八筆，保留原基底 | 325／325 | **27 組** |
| 假設八筆玩家記錄改至獨立儲存，建立／清理都改接 | 325／325 | 0 |

後兩種只是合成位址投影，沒有改遊戲 bytes、建立 native hook 或執行引擎資源操作。最後一列只證明這兩條直接生命週期清單可在位址上對齊，尚未涵蓋所有 readers/writers、外部aliases與實際資源釋放。

## 1. 完整直接成員清單

地址相對已證明的同一 D。每個 S 大小 `0x78`；不同欄位群沒有在此猜測業務名稱。

| 成員起點／群組 | 外層次數 | 外層 stride | 每筆 S 偏移 | 原 S 數量 |
|---|---:|---:|---|---:|
| `80DA0` | 1 | — | `0` | 1 |
| 玩家 record `80E18` | **4** | `298` | `28、A0、118、1A0、218` | **20** |
| 獨立 `81888、81900、81988、81A00、81B10、81B88` | — | — | 各一個 | 6 |
| `8B748` | 20 | `180` | `0、78` | 40 |
| 獨立 `8D550、8D5C8` | — | — | 各一個 | 2 |
| `81C98` | 64 | `180` | `0、78` | 128 |
| `87DA0` | 5 | `180` | `0、78` | 10 |
| 獨立 `88538、885B0` | — | — | 各一個 | 2 |
| `886C0` | 32 | `180` | `0、78、F0` | 96 |
| **合計** | | | | **305** |

所有 constructor calls 均驗證：`R8=P=D+36F8`、`R9=D`、RDX=同一 context A、第五參數=global `347CE90` 所指 context 加 `6D30`。這裡的context位址使用合成值追蹤等同性，沒有讀取該writable global的實際內容。

最後一組的32次並非可直接搜尋到的共同 MOV immediate：constructor在前面的5次迴圈將R13減到零，再以 `142BE26: lea r15d,[r13+20]` 建立32次；cleanup以同理減至零的RSI，於 `142CB1D: lea edi,[rsi+20]` 建立32次。投影實際執行這些計數／分支，沒有把寄存器名直接當作固定容量。

constructor另外直接清零並初始化256個nodes，及清零四筆`298`-byte record。這些 node 初始化操作的數目，在假設八筆場景仍為256；它們與玩家外層迴圈是不同的容量來源。

## 2. 八筆時需要共同變動的生命週期位置

| 用途 | 原指令位置 | 原意義 |
|---|---|---|
| 建立記錄 anchor | `142BB8D` | `R14=D+80EB8`，即 record base 加 A0 |
| 建立外層次數 | `142BB94` | R12D=4 |
| 清理記錄 anchor | `142C9CE` | `RBX=D+80EB8` |
| 清理外層次數 | `142C9D5` | ESI=4 |

這四處是已知必須共同適配的生命週期位置，**不是完整patch清單**。其他[float consumers](indexed_float_consumers_findings.zh-TW.md)、外部index、metadata與rank來源仍需改接。

只增加次數時，第五筆的第一個S起於 `D+818A0`，與原本 `D+81888` 的S重疊96 bytes；後者接著又與其他新增S產生重疊。27組只是S區間的衝突計數；record整塊清零、其他欄位及既有float writer的覆寫風險另已在前置證據指出，不能把27當作全部記憶體風險數。

八筆獨立儲存情境將兩個anchor指向同一合成sidecar的`+A0`，同時把兩個次數改成8；所有其他直接成員仍維持原地址。結果新舊兩份清單均為325項且次序相同、S區間無重疊。這要求真正的實作在清理前保留sidecar、D、P及context的有效生命週期，並使所有用戶讀寫同一份record。

## 3. 從清單對應到池回收：仍需哪些前提

依[已核對的140C200與1408F00](indexed_float_subobjects_findings.zh-TW.md)，S cleanup會對各index取node並清理資源；occupancy原為非零時清成零並減少used count；最後把S的template ID及active count設為零。count=0也有清ID/count的快速路徑。

因此，若同時滿足以下條件，清理直接清單可回收其全部所屬nodes：

- 每個active node恰由一個列出的S擁有；沒有active clone或重複index。
- S count有效，所有indices在pool範圍內，且對應occupancy已標記。
- used count與occupancy一致；D／資源context仍有效。
- cleanup callees正常返回，沒有並行或回呼重新配置／修改同一pool。

若另外能證明沒有清單之外的owner持有nodes，才可進一步推得整池used count=0、occupancy全零。本次沒有證明最後這項全遊戲封閉性，亦沒有執行API釋放。

### Search cursor不必因清理而變成零

`140C200`本地清理指令沒有重設P search cursor。已核對的配置流程在`140C363`讀cursor，以`(cursor+probe) % capacity`搜尋，配置成功於`140C398`保存`(slot+1) % capacity`。所以在capacity不變、cursor合法、occupancy一致且沒有外部修改的前提下，保留非零cursor本身不妨礙再次配置；空池會從該合法cursor取得第一格。

這與[初始整塊清零](indexed_float_pool_initial_zero_findings.zh-TW.md)是不同的生命週期條件。新增S或清理S不能以重設used count／清bitmap取代node資源回收。

## 4. 容量與八人實作的下一步

指定玩家模板的條件式需求仍是[每筆11格、八筆88格](indexed_float_template_budget_findings.zh-TW.md)。現在把其他直接使用者具體列為285個S；它們的同時占用、清單以外的使用者與額外暫存，合計仍需在保留256格池時不超過168格。

下一步可以按上述成員群追其模板選擇與同時活躍條件，避免對所有成員套用物理12格上限就直接決定配置大小。必要時擴池仍須解決node backing、occupancy、P及所有aliases，並處理partial allocation與同ID不重試。

## 5. 重播與審查

- [位址投影重播程式](indexed_float_pool_lifecycle_inventory_replay.py)
- [正式證據](indexed_float_pool_lifecycle_inventory_evidence.json)
- [同來源重跑](indexed_float_pool_lifecycle_inventory_recheck.json)
- [額外bytes／fragment／所有區間兩兩比較](indexed_float_pool_lifecycle_inventory_review_checks.json)

正式JSON SHA-256：`7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6`。

兩個完整roots共有381條指令，與固定capture及前置證據逐byte／反組譯一致。位址投影分別從`142BA7B`與`142C9BF`開始，在epilogue前停止；constructor的D／context／zero seeds另保存來源pins。各場景用零／CC初始bytes重播，constructor與cleanup的實際訪問序列均與另一份幾何清單一致。

模型只處理整數位址／計數／分支，callee以已列contract處理，呼叫後使volatile GPR與flags未知。SIMD結果不作引擎計算，另核對被忽略的SIMD stores不供給任何後續scalar位址／迴圈讀取。這些限制是投影範圍，不能解讀為引擎呼叫成功。

主代理另核388條evidence rows、381個不同位置的原bytes與完整fragments，對所有S區間做兩兩比較，獨立得出0／27／0組重疊。重跑JSON逐byte相同。沒有獨立代理語義審查，也沒有native執行或第5–8人聯機測試。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_lifecycle_inventory_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_lifecycle_inventory_new_recheck.json
```

本次沒有查詢／讀取活程序，第四次擷取仍待先前問題的授權。**八人Mod尚未完成；此輪完成直接生命週期清單與搬移條件的離線核對。**
