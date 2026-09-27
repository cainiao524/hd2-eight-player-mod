# 七個單例 S：指定模板需求與兩個 count-one guard

## 實作結論

這七個已初始化、會完整清理的 S 使用同一個 D 共用池。在已定位的呼叫、有效 counters 與相同模板資料前提下，完整配置需求合計 **12 格**。這是指定 ID 的子集合需求，沒有將它當作整池容量或實際 heap 占用上界。

| S 相對 D 位移 | 已定位配置 call | 模板 ID | 模板節點數 | 訪問條件 |
|---|---|---|---:|---|
| `80DA0` | `14304E3 → 140C2E0` | `16` | 2 | 該 caller 路徑 |
| `81888` | `142DFAC → 140C2E0` | `1A` | 3 | 該 caller 路徑 |
| `81900` | `142E00F → 140C2E0` | `1B` | 1 | 該 caller 路徑 |
| `81988` | `142E2F5 → 142F6E0` | `1D` | 3 | `D+81AF8` count 迴圈 |
| `81A00` | `142E0B1 → 140C2E0` | `1B` | 1 | 同上，先處理 secondary S |
| `81B10` | `142E5D5 → 142F6E0` | `1E` | 1 | `D+81C80` count 迴圈 |
| `81B88` | `142E391 → 140C2E0` | `1B` | 1 | 同上，先處理 secondary S |

對當次已定位請求可寫為 `2+3+1+4*c81AF8+2*c81C80`。兩個 count 在有效初值及已列出的不干擾條件下為 0 或 1，故最高 12。**Count 變零只會跳過這些更新，不證明舊節點已清理。** 採集規格仍須列出全部七個 S 並核對 active indices。

同 ID 的配置呼叫可能直接返回；若先前是 partial，這個 12 格預算不表示它會自動補齊。未知舊 ID、其他 writer、全池其他 owner 及重入情況均未納入此上界。

## 1. 模板的實際 emission

沿用已核對的完整 `1258050` initializer 與五個 emitter leaves，重播以下直線區段：

| ID | 區段，末端不含 | Types | 各節點 event 數 |
|---|---|---|---|
| `16` | `125E511..125E58B` | `2,1` | `1,1` |
| `1A` | `125F0E5..125F14C` | `2,2,2` | `1,1,1` |
| `1D` | `125F6DF..125F779` | `2,2,2` | `3,3,3` |
| `1E` | `125F7E4..125F81E` | `2` | `3` |

每區段 selector 一次，helper calls 僅使用已核對的五個入口。Secondary payload helper `1257EF0` 不增加 node 數。每區段以零／A5 合成 payload 各重播一次，結果一致；template `1B` 的一格沿用固定[玩家模板證據](indexed_float_template_budget_findings.zh-TW.md)。

仍有明列前提：fresh emission storage、有效 event payload secondary count，以及 runtime 模板相同；沒有重新建立整個 initializer stack，也未證明後續其他寫者不會修改模板。全 initializer 的正常 CFG 用於排除從區段外跳入其中；opaque 原生 helper 未被執行。

## 2. 兩個一筆上限

| Counter | Reset | 讀取／比較／unsigned JAE | Increment | Record 位置 store |
|---|---|---|---|---|
| `81AF8` | `142BFAE` | `142D528 / 142D52E / 142D531` | `142D570` | `142D568` 寫 `D+81978+3*n*128` |
| `81C80` | `142BFB6` | `142D580 / 142D586 / 142D589` | `142D5C4` | `142D5BC` 寫 `D+81B00+3*n*128` |

兩個 guard 都比較 1，拒絕 unsigned count≥1；通過時只可能 n=0，增加到 1。位置 store 與 increment 都必經 guard 通過 edge，append 區段無 call、無循環、無其他入口，非 stack store 只有位置與 counter。有限 disp32 掃描中只找到各一個 reset 與 increment；computed aliases／未保存 code 不在此證明內。

`81978+180=81AF8`，`81B00+180=81C80`，因此這是各一筆的物理界限。Guard 會跳過無效初始 count，沒有把它修回 0 或 1。

## 3. S 地址及迴圈來源

沿用[同 D consumer 證據](indexed_float_consumers_findings.zh-TW.md)的 caller 身分；本輪另核完整 `142BED0/142CB90/142D870/1430450` 共 3,574 條指令，以及 56 項 reaching-definition。

- `14304AE` 以入口 D 形成 `D+80DA0`；RCX 與模板 `16` 的來源接到 `14304E3`。
- `142D8A7` 把入口 D 存於 `[RSP+68]`。所有已核對 restore 都從該槽取值；完整 caller 的 RSP 與 `RBP=RSP+100` 直接寫入只有這一處覆蓋該槽。
- 兩個單例迴圈初始 index 的 R12 reaching definitions 全部為 XOR zero。R13 的 LEA→ADD→RCX，以及 primary S 的 RDX 載入 stride→加固定偏移→加 D 鏈均已核對。
- 四個配置 call 都必經對應 count 的通過 edge。各自的外層 index stack 槽只有初始化與 increment 後更新；stride `[RSP+70]` 只有各自的一個 store。檢查包含 RBP 別名，且按迴圈區段分開，沒有把內層重用的其他槽當成不變。

在 counter 為 0／1 且執行期間未被 opaque callee、其他執行緒或重入修改的前提下，訪問 ordinal 分別為空集合／`[0]`。這項前提仍需實際同步設計。

## 4. 對候選程式的決策

| 研究要求 | 決策 |
|---|---|
| 成品需求 | 擴到八名玩家時仍正確計算共用池占用、保留與清理 |
| 改變的實作 | 這七個 S 保持既有數量；採集列出全七個，不按目前 count 裁剪；指定模板需求可接入 preflight |
| 停止條件 | 指定模板數、caller S 身分、兩個物理一筆界限及保留限制已足夠決定上述資料契約；不繼續追不影響容量的 payload 數學 |
| 下一步 | 由候選 owner layout 自動列地址，交給 snapshot validator；取得可信資料及同步條件後再規劃原生配置 |

有限掃描也找到其他直接位移引用；相同位移不等於同一 D。未接合的 caller 不加入本輪模板集合，不把未找到其他寫者宣稱為不存在。

## 5. 驗證與交付

- [重播程式](indexed_float_pool_singletons_replay.py)
- [正式 v3 證據](indexed_float_pool_singletons_evidence_v3.json)
- [同來源重跑](indexed_float_pool_singletons_recheck_v3.json)
- [核對記錄](indexed_float_pool_singletons_review_checks_v3.json)
- [有限位移掃描](indexed_float_pool_singletons_refs_discovery.json)

正式 v3 SHA-256：`379977cc2a1f193646d9ae8ab7143694c3db20676f133b7c762e6860eb2f1d41`。兩次輸出逐 byte 一致。

獨立代理核對 v1/v2 的原 bytes、模板 calls、reaching chains 及 RSP／RBP stack writes；主代理把建議加入 v3 的 gate，再核最終 rows、算式、來源及重跑一致。較早 v1/v2 保留為中間產物。全程只有保存資料及合成模型，沒有查詢程序、執行原生配置或多人測試。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_singletons_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_singletons_new_recheck.json
```
