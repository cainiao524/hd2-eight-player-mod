# 其他共用池成員：可選子物件、模板需求與保留占用

## 結論

後續已接上[四組counter的guarded writers與清零界限](indexed_float_pool_counter_bounds_findings.zh-TW.md)：有限掃描的四個清零store及五條新增路徑，在有效初值等前提下維持1／64／5／1上限。下文記錄本輪當時的caller／模板範圍；完整aliases與回收仍未閉合。

已接上`142D870`中四組其他成員的共用更新helper `142F530`，及其可選第二子物件helper `142F780`。兩個完整roots共141條指令，明確區分主S、可選第二S與可選第三S。

**可選旗標變成零的路徑沒有直接回收相應S。** 因此容量方案不能只把目前顯示／啟用項目相加；先前配置且尚未回收的nodes也可能保留。這是本地路徑的界限，不排除其他caller或事件回呼另行清理。

另從指定模板建立區塊確認`20、21、2F、22`各加入一個node。下述四組callers所要求的模板，在counter符合實體布局、模板等同性與完整配置的條件下，需求式為：

`c20 + c21 + c2F + 2*c22`

套用各組物理記錄上限`1、64、5、1`，此子集合最多要求**72格**。這不包含所有其他成員、先前保留的可選S或整池生命週期峰值，不能據此宣布256格已足夠。

## 1. 共用更新helper的三個S

令`R`為`142F530`的入口R8，`T`為入口R9D。

| 子物件 | 位址 | 配置條件 | 模板選擇 |
|---|---|---|---|
| 主S | `R+10` | 正常走到尾端時，tail-call `142F6E0` | caller傳入T |
| 第二S | `R+88` | 第六參數非零，call `142F780` | `1B + (T==28)` |
| 第三S | `R+100` | 第七參數非零，call `140C2E0` | `2D + (T==28)` |

每個S長`78` bytes，這三個區間在三S布局中前後相接。只有兩S的成員必須使用相容的旗標／布局，不能因helper能接第三S就推定任意record都有該欄位。

`142F530`保存`T`至EBP、R至RSI。第六參數分支在`142F550`，true路徑`142F552 → 142F562`才呼叫第二S helper。第七參數分支在`142F56F`，true路徑才形成`R+100`並在`142F596`配置第三S。重播移除各true edge後，相應配置call不可達。

### Stack參數位置

`push rsi`加`sub rsp,40`使該helper的current RSP比入口低`48` bytes。加上call壓入的return address：

| 參數 | Caller call前RSP | Helper current RSP |
|---|---:|---:|
| 第五個float | `+20` | `+70` |
| 第六個旗標，第二S | `+28` | `+78` |
| 第七個旗標，第三S | `+30` | `+80` |

此處旗標不是玩家索引。`T==28`中的28及模板ID皆為十六進位；沒有把這個比較當成人數上限。

## 2. 關閉旗標沒有直接回收可選S

第二S旗標為零時，控制流從`142F550`跳過`142F780`。稍後仍在`142F6A7..142F6B3`把第二S交給`140D710`，以事件ID`1F`及該旗標更新事件狀態；本路徑沒有call `140C200`或用template 0配置第二S。

第三S旗標為零時，`142F56F`直接跳過第三S配置／更新區塊；沒有相應直接cleanup。兩個新核對roots的直接callees只有`142F780、140C2E0、140D710`，另有尾呼叫`142F6E0`；不能把false分支推定為node已歸還池。

另一方面，`140C2E0`在同一S改用不同模板時會先清理舊模板的nodes；相同ID則早退，池滿也可能保留部分配置。這些[已知配置／清理語義](indexed_float_subobjects_findings.zh-TW.md)仍適用。

容量預算應涵蓋各S在生命週期內可能保留的配置，以及其他caller的回收時機。外部event回呼、並行或重入修改沒有在此執行或完整展開，故本結果是「沒有直接回收的證據」，不是「任何時候都永不回收」。

## 3. 已對應的四組caller

沿用[既有consumer證據](indexed_float_consumers_findings.zh-TW.md)中`142D870`的同一D身分、保存slot與R14恢復關係。各record stride為`180`；下表record base比主S少`10`。

| Call RVA | Record base相對D | 主S | T | Counter欄位 | 物理記錄上限 | 旗標6／7 |
|---|---|---|---|---|---:|---|
| `142E84B` | `8D540` | `8D550` | `20` | `8D6C0` | 1 | 0／0 |
| `142E8D9` | `81C88` | `81C98` | `21` | `87D88` | 64 | 0／0 |
| `142E933` | `87D90` | `87DA0` | `2F` | `88524` | 5 | 0／0 |
| `142E9D6` | `88528` | `88538` | `22` | `886AC` | 1 | 1／0 |

物理上限來自[直接建立／清理清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)，不是此次讀到的counter執行期值。caller按stored count迴圈；本次沒有閉合其writer對上述上限的保證。

最後一組T=`22`不等於`28`，所以第二S=`D+885B0`使用已知一格模板`1B`；第三S旗標為零。前面三組在這些call sites都不要求配置第二／第三S。

## 4. 主模板各一格的來源

仍使用固定initializer root `1258050`；以下每段自selector開始到最後一個已識別emitter call結束，均沒有中途從外部跳入的正常CFG edge。區段外其他writer及live template內容未驗證。

| Template | Emission block，右端不含 | Type | Nodes | 合成fresh狀態的事件數 |
|---|---|---:|---:|---:|
| `20` | `[125F93A,125F974)` | 2 | 1 | 3 |
| `21` | `[125FDA1,125FDDD)` | 2 | 1 | 1 |
| `2F` | `[125FF6F,125FF85)` | 2 | 1 | 0 |
| `22` | `[12600D5,126010F)` | 2 | 1 | 3 |

模板21另使用`1257EF0`的無事件secondary-payload分支；該操作不增加node count。此處的payload與前述「可選第二S」是不同層級的資料。

重播沿用已固定雜湊、完整核對的五個template leaves及Python instruction model，以零／A5合成payload運行各區段；假設fresh zeroed elements與event input `+E4=0`。這些是明列模型前提，沒有重建完整initializer stack或執行native code。模板等同性／初始化順序／後續寫入限制與[玩家模板預算](indexed_float_template_budget_findings.zh-TW.md)相同。

## 5. 對八人容量方案的影響

- 四個caller的指定模板需求已可按`c20+c21+c2F+2*c22`計算，物理上限組合為72格。
- 玩家八筆仍是88格的條件式需求；這兩個子集合之外還有其他成員與可能保留的配置，不能僅相加後宣布整池安全。
- 不能因目前旗標為零或當前counter下降，就自動把舊配置從預算扣除；需找到對應cleanup／改模板的來源。
- 若決定擴池，仍需完整改接node／occupancy backing與所有aliases，並保留有效的used count／cursor和資源所有權。

## 6. 重播與核對

- [重播程式](indexed_float_pool_optional_members_replay.py)
- [正式證據](indexed_float_pool_optional_members_evidence.json)
- [同來源重跑](indexed_float_pool_optional_members_recheck.json)
- [額外原始bytes／caller參數核對](indexed_float_pool_optional_members_review_checks.json)

正式JSON SHA-256：`2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436`。

兩個完整helper roots、四個unwind fragments、141條指令，10項argument reaching-definition檢查，以及兩個可選call的必要branch-edge檢查通過。四個template blocks各做兩組合成重播。主代理另核248條evidence rows、217個不同地址的原bytes，檢查四處template immediate、八個旗標literal與四個counter欄位標記。重跑JSON逐byte一致。

此為主代理的額外核對與人工語義審閱，沒有獨立代理或執行期審查。未查詢／讀取活程序，第四次擷取仍待先前問題的授權。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_optional_members_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_optional_members_new_recheck.json
```

仍待其他成員模板、counter writers／上限、保留與回收時機、所有record aliases、實體生成及原生八人變更與多人驗證。**八人Mod尚未完成。**
