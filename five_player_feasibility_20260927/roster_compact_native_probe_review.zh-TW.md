# 原四槽 compact probe：獨立有限審查

## 結論與用途

**未發現使本輪反例無效的具體缺陷。** Probe 確實在 Unicorn 執行固定 capture 的原四槽 x64，包含真正的 `60C410` mover 與 `172F790` map helper。其順序模型與 entity／map 保留性檢查分開，沒有以「符合原程式」代替「原程式保留資料」。

這項研究解決八格 roster 的保留需求：不能把 `60CC70` 單純重定位後宣稱為 lossless compactor。停止條件已達成：反例及有效／失敗 counts 邊界可重現；下一步需 caller／pending 契約，而非繼續擴充同一合成案例。

## 審查與重跑

- 已審 `roster_compact_native_probe.py` SHA-256：`6b961e26ab8896ec54868f0510a727d8d476c3697d48b77b6a50e097f93132b9`。
- 主線 `roster_compact_native_probe_results.json` SHA-256：`a6131b5edb7a717eb0ea9537a27cbc76a4ca518be2bfbe0280411c6211a3af85`。
- 獨立新輸出 `roster_compact_native_probe_review_recheck.json` SHA-256：`fc3e1820c7777b6b2974f1c8fa5e4a429afa22efae86fd02f2a55a5f2e5ba68a`。

重跑成功。兩份 JSON 唯一不同欄位是 `python_version`：主線為 3.12.10，審查使用 bundled 3.12.14；Unicorn 都是 2.1.4。排除該環境欄位後，所有欄位、events、writes、records hashes 與結果逐值相同。本輪沒有覆寫原輸出、修改候選或操作遊戲。

```powershell
& 'C:\Users\OvO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'five_player_feasibility_20260927\roster_compact_native_probe.py' `
  --capture 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output 'five_player_feasibility_20260927\roster_compact_native_probe_review_recheck.json'
```

輸出檔已存在；再次重播須使用新的輸出檔名。

## 原指令與 oracle

`Image` 檢查固定 capture report／data 指紋及 capture identity；五個原 body 各另核完整 SHA。Fixture 將原 bytes 按相同 RVA 放到合成 GAME base，保留原相對呼叫。沒有 emitter 參與，也沒有更改 branch／call 或替換 helper。Code hook 僅觀察狀態及在指定 return sentinel 停機；沒有設定成功返回值或跳過 callee。

順序模型按已核的 `P→i`、`i→P` 與 map value 更新建立**預期最終 bytes**，比對所有已映射的非 stack 完整頁面，包括四槽四組陣列、map、counts、global、entity 與 code pages。另檢查返回 RSP、nonvolatile GPR 及 XMM6–15。這不等於驗證全部 stack bytes 或每一筆中間寫入順序；events／writes 保留了反例的重要中間狀態。

保留性則重新從執行後的 pointer records 解參考 entity IDs，計算遺失 ID、重複 ID，以及 map ordinal 實際指向的 ID。它不從順序模型直接取得成功答案。程式最後的 `preserves == not(P<D<T)` assertion 是對推導邊界的驗證；10 組反例仍明確記為失敗，不會被包裝成 candidate pass。

固定 fixture 的 map 在輸入時有每個 tracked entity 的唯一 entry，完整頁面模型還要求 keys 不變。審查另以結果獨立核對每組：map key 集合等於原 ID 集合、value 集合等於 `range(T)`，且每個 value 指到相同 ID；與原 `map_bijection_preserved` 全部一致。此結论限定目前固定 fixture，不把該 boolean 當作任意輸入 map 的泛用完整性驗證器。

## 案例與計數

| Domain `0<=P<=D<=T<=4` | 組數 | 保留結果 |
|---|---:|---|
| `D==T` | 15 | 保留原 IDs／map |
| `P==D<T` | 10 | 保留原 IDs／map |
| `P<D<T` | 10 | 全部出現遺失及不一致 map |
| 合計 | 35 | 25 保留、10 反例 |

審查確認 35 個 triples 互不重複，完整覆蓋該有限 domain。最小 `T=2,D=1,P=0` 的原 ID `[11,19]` 變成 `[11,11]`，map 仍為 `11→0,19→1`。

另有同一 fixture 的原 `60CA80→60CBA0→60CC70` 三次頂層執行，分別 65／75／166 instructions（含觀察到的停止入口）；故頂層 execution 數是 `35+3=38`。內部 helper 呼叫沒有另計成頂層 execution。合成鏈末段重複最小反例；`counterexample_cases=10` 指 35 組 domain cases，沒有把鏈的重复反例再加一次。

## 範圍聲明

合成鏈證明這三個原 body 在手工選定順序下可產生該狀態。它没有執行真實 caller／dispatch、property 與其他 lifecycle 階段，也沒有證明該順序在遊戲中可達。報告正確標示 `real_dispatch_reachability_proven=false`、`candidate_emitted=false`、`game_process_accessed=false`，並明言不宣稱 shipping game 有可達缺陷。

本輪未驗證八格候選、八個帳號、連線、角色或任務同步；完成的是固定原四槽流程的有條件反例。後續實作仍須選擇有證據的 caller 限制或完整替代演算法，不能以這份 probe 代替 compaction 的成品交付。
