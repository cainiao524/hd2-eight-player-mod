# 共用節點池：四組記錄數量的寫入上限與清零界限

## 結論

後續已接上[32筆三S的模板來源與轉換需求](indexed_float_pool_triple_members_findings.zh-TW.md)，補出最後需求5格、局部轉換峰值6格的條件模型；下文仍記錄本輪四組counter的原始範圍。

已把[前輪四組模板需求](indexed_float_pool_optional_members_findings.zh-TW.md)的物理記錄上限，接到實際counter寫入程式。有限disp32掃描找到四個清零store與五個increment；**五條新增路徑都先做unsigned容量檢查**，對應上限為1、64、5、1。五筆那組有兩條新增路徑，兩者都檢查5。

在counter起初有效、沒有並行／重入／其他alias writer干擾的前提下，這九個已找到的寫入保留數量範圍。這補強了四組指定模板的`c20+c21+c2F+2*c22 ≤ 72`條件式需求；仍沒有證明整個256格池的峰值，也沒有執行八人Mod。

**Counter清零不等於已清理節點。** 已完整核對的無呼叫清零後段有266處直接D寫入，全部避開305個已盤點S及pool區域。清零還會解除建立流程的快取旗標；先前已配置的S仍需由實際cleanup路徑處理，不能只因目前count下降就從容量預算扣除。

## 1. 五條新增路徑及對應陣列

地址／欄位位移為十六進位，表中容量是十進位。D身分沿用[consumer證據](indexed_float_consumers_findings.zh-TW.md)的caller鏈。完整root `142CB90`在`142CBBA`保存入口RCX為RDI；新的reaching-definition核對確認各寫入仍使用該D。

| Counter相對D | 容量 | Count load | Compare／unsigned拒絕 | Increment | Record base／stride | Metadata base |
|---|---:|---|---|---|---|---|
| `8D6C0` | 1 | `142D64B` | `142D65C/142D65F` | `142D6A1` | `8D540 / 180` | 無本路徑metadata store |
| `87D88` | 64 | `142CE38` | `142CE3E/142CE41` | `142CEC3` | `81C88 / 180` | `87C88`，DWORD×64 |
| `88524` | 5 | `142CEE1` | `142CEE7/142CEEA` | `142CF36` | `87D90 / 180` | `88510`，DWORD×5 |
| `88524` | 5 | `142D791` | `142D797/142D79A` | `142D7C5` | `87D90 / 180` | 同上 |
| `886AC` | 1 | `142D5DE` | `142D5E4/142D5E7` | `142D637` | `88528 / 180` | `886A8`，DWORD×1 |

每條路徑均以`cmp count, capacity; jae reject`拒絕`count ≥ capacity`。Accepted路徑用`lea rcx,[n+n*2]; shl rcx,7`形成`n*180`，在record開頭寫入8 bytes，必要時另按`n*4`寫metadata，最後count加一。

三組metadata區都緊接records，且metadata末端就是count欄位；沒有metadata的單筆組則以record末端接count。已逐一列舉所有accepted n，包括兩條五筆路徑，共76種局部輸入，確認兩種indexed stores不碰count欄位、結果不超capacity。

### 控制流程與寫入前提

- 三個完整roots共2,186條指令；`142CB90`的12項switch RVA表另以資料保存，沒有把表當指令。
- 每條新增路徑的accepted edge都是record store及increment可達的必要條件。
- 新增區段沒有另一個跳入入口、沒有迴圈，也沒有call；不能在省略重新load／guard的情況下重複increment。
- 所有非stack memory writes都列入record、metadata或counter三類；count到地址計算的寄存器來源亦核對。
- 起始counter有效、D與stack分離且有效、外部程式不在guard與store間改寫counter，才有這個局部不變量。

**現成guard不會修復已經無效的counter。** 例如count已大於上限，這些新增路徑只會略過新增；其他按stored count讀取的迴圈仍需要有效數量。不能以此推論損壞狀態也安全。

## 2. 清零store與節點所有權

完整`142BED0`在`142BEF6`保存D到RBX。`142BFAC xor ecx,ecx`後，四個count分別在`142BFC2、142BFCE、142BFD4、142BFDA`寫0。

本次另逐一核對`[142BFA2,142C88B)`的無分支／無call後段。該後段全部memory writes都是固定D位移或固定stack位置，其中266處直接D寫入：

- 不重疊[生命週期清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)的305個S，每個S長`78` bytes；
- 不重疊pool descriptor、256個nodes及occupancy的合併區間`D+[36F8,24018)`；
- 因此這段count reset本身沒有清除S的template ID、active node count、indices，也沒有清除pool occupancy／used count。

完整函式在該後段之前仍呼叫`1433460`與`1400AC0`，結尾有cookie check。其所有外部效果未在本次證明，所以結論限於**明確核對的清零後段**，不能擴寫成「整個函式與所有callee永不回收」。

## 3. 建立快取旗標與更新入口

同一D的byte `8D709`控制已定位的builder呼叫：

1. 清零後段在`142BFE0`把旗標寫0。
2. `142D870`在`142D965`讀旗標；旗標非0經`142D970`跳過`142D975 → 142CB90`。
3. `142CB90`走到`142D7CB`時把旗標寫1；其早退路徑不必經過這個store。
4. `142D870`另有`D+80D9C==0`分支，於`142D8E3`呼叫`142BED0`後走共同返回。

這顯示所選記錄建立結果有快取控制，不能假定每次更新都重新建立全部項目，也不能把flag或count清零解釋為S資源已歸還。

旗標有限掃描還有`72336A、724E4E、142C940`三個writer位置，其caller／生命週期語義尚未在本輪閉合。`142C8F0`的22條指令可見直接呼叫`142C9B0`再清旗標，但有限incoming掃描只找到unwind資料、未找到可接合的呼叫來源。它保存為[探索資料](indexed_float_pool_cache_invalidator_discovery.json)，**不列為已證同一D的回收入口，也不宣稱它未被使用**。

## 4. 對八人方案的具體影響

- 四組既有容量1／64／5／1有本機程式guard依據；它們是其他記錄集合，不是玩家槽數，不應隨四人改八人一起翻倍。
- 四組指定模板的72格需求不再只依賴物理布局推測，但仍以有效初值、有限writer集合及模板等同性為條件。
- 玩家八筆88格與這72格不能直接作為總池峰值；還需其他成員、保留的可選S、不同模板及暫存配置。
- 設計新S／搬移舊S時要保存資源唯一所有權；count／cache reset、S cleanup、pool reset必須分別對應實際程式流程。
- 下一個可離線推進的缺口是其餘32筆三S成員的模板來源，以及上述旗標失效／cleanup的caller與物件身分。原生handle下游、完整改接與多人驗證仍未完成。

## 5. 重播、額外核對與界限

- [重播程式](indexed_float_pool_counter_bounds_replay.py)
- [正式證據](indexed_float_pool_counter_bounds_evidence.json)
- [同來源重跑](indexed_float_pool_counter_bounds_recheck.json)
- [額外bytes／opcode／區間核對](indexed_float_pool_counter_bounds_review_checks.json)
- [四欄位有限掃描](indexed_float_pool_counter_refs_discovery.json)
- [旗標有限掃描](indexed_float_pool_counter_cache_refs_discovery.json)
- [清理候選的有限incoming掃描](indexed_float_pool_cache_invalidator_xrefs_discovery.json)

正式JSON SHA-256：`aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4`。

重播包含三個完整roots、16個unwind fragments、2,186條指令，五條guarded append、76個accepted count情境與315項reaching-definition核對。主代理另核2,540條evidence rows／2,190個不同地址的原bytes、五個unsigned JAE opcode與容量literal，以及266處store對306個保護區間的零重疊。重跑JSON逐byte一致，Python語法檢查通過。

此為主代理的額外核對與人工語義審閱；既有三個代理狀態均為用量限制導致的errored，沒有獨立代理審查。所有掃描均限已保存的固定capture，可能漏掉computed aliases、無unwind或未保存程式；沒有執行native code或查詢／擷取活程序。第四次擷取仍待先前問題的授權。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_counter_bounds_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_counter_bounds_new_recheck.json
```

這些結果補充八人配置方案的證據，**不是已完成的八人Mod或多人成功紀錄**。
