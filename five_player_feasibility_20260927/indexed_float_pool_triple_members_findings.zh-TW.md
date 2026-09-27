# 32筆三子物件：模板來源、節點需求及轉換時的額外空間

## 結論

已接上`D+886B0`的32筆記錄、逐筆模板表`D+8B6B0`與counter `D+8B730`。`142D870`對每筆呼叫`142F530`時，第二／第三子物件旗標均為1；其三個S位於record `+10、+88、+100`。

新核對12個模板的建立區段。對已列明的主模板域`24..2C`，單筆最後要求3至5格，32筆全部取各自最大值為**160格的條件式配置需求**。這不是全池占用，也不涵蓋未知caller、未證模板0或其他配置。

**最後需要5格，不代表轉換期間只需5格。** 保留舊子物件的情況下，已保存的更新順序可形成先占6格、最後降回5格的局部模型。若當時只剩5格給這筆記錄，`140C2E0`可能留下partial配置；後續相同模板ID請求直接返回，不會補齊。

這使八人方案多了一個具體要求：容量要涵蓋轉換期間的需求，或明確處理配置失敗與重試。尚未證明全遊戲狀態能走到每個模型情境，也沒有執行native code或八人聯機。

## 1. 三個子物件與記錄邊界

| 項目 | 保存程式中的位置／關係 |
|---|---|
| Record | `D+886B0+n*180`，`n`是此集合的ordinal，不是玩家network index |
| 三個S | record `+10、+88、+100`，每個長`78` bytes |
| Template table | `D+8B6B0+n*4`，32個DWORD |
| Counter | `D+8B730` |
| 更新call | `142E34D → 142F530`，模板在`142E333`載入 |
| 可選參數 | `142E322/142E327`均寫1，啟用第三／第二S |

邊界算術為`886B0+32*180=8B6B0`、`8B6B0+32*4=8B730`；與[建立／清理清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)的32筆×3個S一致。

Builder在`142CF4D`讀count、`142CF53`比較`20h`、`142CF56`以unsigned JAE略過超限新增。有限掃描找到的兩個count writers是`142BFC8`清零及`142D1B2`保存加一後數值。**此guard到commit中包含callee**，因此本次範圍保證明列「callee與其他writer不改count／模板表／caller暫存陣列」的前提，沒有套用前輪五條無call新增區段的更強結論。

## 2. 模板表的來源

Builder `142CB90`有五個直接模板表store：

| Store | 寫入值 |
|---|---|
| `142CFE9` | `27` |
| `142CFF7` | `28` |
| `142D005` | `26` |
| `142D013` | R14D，來自固定`24`或`25`與保存slot的恢復 |
| `142D02A` | caller暫存計數加`29` |

R14D的保存slot `[RSP+38]`在所核對setup／loop phase只有`142CC7E`與`142CD2D`兩個writer，分別保存25／24；`142D1D0`恢復此slot。

### 動態分支與暫存計數

`142D023`讀`[RBP+n*4-60]`，加`29`後寫表；`142D041`才把該slot加一。32個DWORD在`[RBP-60,RBP+20)`，由八個MOVUPS清零；每個初始化都支配該讀取。當前RBP等於RSP+`100`，因此亦按RSP座標核對整個loop phase的其他stack寫入。

在有效count、opaque callee不干擾、只有已找到的count commit遞增之條件下，新append逐筆使用遞增ordinal，每個新的暫存slot讀取前仍為0。因此**這條指定builder路徑的新記錄產生29**；不能由此宣布其他caller或既有記錄不可能使用2A..2C。既有記錄仍需原本有效的模板表內容。

模板initializer另外確實以四次迴圈建立`29、2A、2B、2C`。這裡的`cmp ebx,4`是四種模板，不是玩家容量；沒有理由隨八人擴充直接改成8。

## 3. 節點數量

| 主模板T | 主S格數 | 第二S模板／格數 | 第三S模板／格數 | 完整配置合計 |
|---|---:|---|---|---:|
| `24、25` | 3 | `1B`／1 | `2D`／1 | 5 |
| `26、27` | 2 | `1B`／1 | `2D`／1 | 4 |
| `28` | 2 | `1C`／1 | `2E`／2 | 5 |
| `29..2C` | 1 | `1B`／1 | `2D`／1 | 3 |

新模板全部加入type 2 nodes。1C、2D、2E的合成事件數分別是`[4]、[2]、[2,2]`；24／25每node三個事件，26..28每node三個事件，29..2C每node兩個事件。事件數不是額外pool node數。

使用[原先固定的Python emitter model](indexed_float_template_budget_findings.zh-TW.md)，每個模板各以zero／A5合成payload重播，共24組；沿用fresh template elements與event input `+E4=0`等前提，沒有重建完整實際payload。

2E區段中另有payload setter `1257980/12579A0/12579D0`與兩次`B6C30`。本次完整核42條leaf指令、所有return路徑及直接call入口：這些helper只寫入指定payload或本地stack，不發射node／event；caller的目的指標亦接到本地stack，setter mode均為`FFFFFFFF`。沒有把未核對的外部call當作無效果。

範圍仍限定指定emission blocks及其一致的執行期模板。Builder另有primary ID0請求；**ID0的節點數與其他未知caller不在本次容量上界內**。

## 4. 為何轉換中可能需要第六格

### 更新helper的局部順序

`142F530`先在`142F562`處理第二S，再在`142F596`處理第三S，最後於`142F6D4`尾呼叫主S更新。

若helper入口持有T24配置`[3,1,1]`，下一次要求T28的`[2,1,2]`，第三S增長時主S尚未縮小，可形成`[3,1,2]`共6格。這是**helper入口狀態模型**；完整builder可能已先替換主S，不能直接宣稱所有實際24→28變更都會如此。

### Builder先換主S的另一種順序

Builder `142D0BD`先更新主S，條件成立時再於`142D144`更新第三S。若保留上一組T28配置`[2,1,2]`，新主模板為T24，且第三S分支選2D，則對應計數如下：

| 階段 | 主S | 第二S | 第三S | 合計 |
|---|---:|---:|---:|---:|
| 已有T28配置 | 2 | 1 | 2 | 5 |
| 主S換為T24，第三S尚未縮小 | 3 | 1 | 2 | **6** |
| 第三S換為2D | 3 | 1 | 1 | 5 |
| 後續helper完成其餘更新 | 3 | 1 | 1 | 5 |

這個模型使用已定位的call順序；前後遊戲狀態的全域可達性、外部事件／callee修改與資源釋放效果未驗證。它提供容量方案要考慮的條件情境，沒有證明遊戲目前必然發生耗盡。

### 只餘五格時的結果

兩種順序各做有效容量5／6的計數模型，共四組。容量6時轉換完成、峰值6、最終5。容量5時轉換只有部分node成功，後續釋放空間後最終占用4格，但至少一個S仍未完整配置。

原因是已核對的`140C2E0`先保存requested ID，再逐格配置；池滿保留部分結果。下一次同ID會直接早退。模型再次執行更新後仍只有4格，沒有自動修復。這裡「容量5／6」也可解讀為其他owner占用固定後，留給這筆記錄的有效空間；不是把實際256格pool改成5或6。

## 5. 八人方案的影響與剩餘範圍

- 對本次已列模板域，32筆的最後配置需求上界為160；分別取主／第二／第三S最大值則為`3+1+2=6`，32份為192。**192是各S獨立取最大值的條件上界，沒有證明32份會同時處於該組合。**
- 玩家八份88格、前輪其他四組72格，以及本批160／192都不是整池總上界；不能只相加後選定一個配置大小或推論既有遊戲必定耗盡。
- 保留256格的方案要證明實際共存與轉換餘量。擴池方案需完整改接node／occupancy backing、capacity、aliases及生命週期。
- 若依靠提早釋放或重試解決轉換峰值，必須保留事件狀態、資源所有權與原有更新語義，不能只把requested ID清掉當作已完成實作。
- 下一個離線缺口是其餘20筆雙S成員與單例的模板、ID0的建立結果、其餘直接配置來源與完整caller／cleanup關係。原生handle下游與多人驗證仍待完成。

## 6. 交付與驗證

- [重播程式](indexed_float_pool_triple_members_replay.py)
- [正式v3證據](indexed_float_pool_triple_members_evidence_v3.json)
- [同來源v3重跑](indexed_float_pool_triple_members_recheck_v3.json)
- [v3額外核對](indexed_float_pool_triple_members_review_checks_v3.json)
- [有限欄位引用掃描](indexed_float_pool_triple_refs_discovery.json)

正式v3 SHA-256：`7a5b7ef002c671d698edd6c663b791a7306eda2b09a238b5d8f187393c04bd60`。

三個完整roots共8,299條指令與16個unwind fragments，四個新leaf共42條指令；29項reaching-definition核對、33個起始count的條件歸納、12個模板各兩組合成重播，以及四個配置轉換情境通過。同來源重跑逐byte一致。

主代理另核436條evidence rows／359個不同地址的原bytes、完整root區段SHA及指令數，以直接emitter calls另計node／event數，再按容量算式核四個轉換trace。沒有獨立代理、native或多人審查。v1／v2是本輪保留的中間產物；正式v3補明helper入口模型的限制，加入builder先換主S的另一條模型及來源pins，避免把局部順序推成全域必經流程。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_triple_members_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_triple_members_new_recheck.json
```

本輪全程使用已保存資料，第四次限定live capture仍待先前問題的授權。**沒有可安裝或已驗證的八人Mod。**
