# 模板 ID 0：固定 initializer、同 D caller 與恢復契約

## 有限結論

在固定 build 25480438 擷取的 `1258050` initializer，模板表先整段清零。完整 root 的 66 個直接 `1257720` selector 呼叫經正常 CFG 的 ECX reaching-definition 分類後，61 處為正數常數，另 5 處動態呼叫產生 `29..2C`、`3D`、`3E`、`41..43`、`44`。這條已定位的發射路徑選出 `1..72` 中除 `30` 以外的 71 個 ID，沒有選 ID0。`30` 同樣未選，但不是本輪恢復設計的目標。

**ID0 的本次 initializer 條件結果是 0 個 node、0 個 event。** 成立前提是：保存指令的正常流程及 byte-fill/helper 語義成立；opaque callee 不改 ID0、selector、動態 ID 來源的 stack locals、loop registers 或 target pointers；每一個 emit/payload 寫入都留在所選模板的合法界內；且之後沒有其他 writer 改 ID0。66 次 selector 非零加整段清零，**本身不足以證明 initializer 最終或執行期 ID0 一直為零**。本輪沒有閉合全部 71 種模板的 emit/payload bounds、所有 opaque callees、其他 caller 或後續可寫資料。ID1 的直接 helper 序列已見先 append 再用 last-node，但不能由此推及其餘模板。

這個條件結果足以把 ID0 列作**需快照實際核對的候選空模板**。候選不得依靜態分析自行填入 `counts[0]=0`。目前 `pool_snapshot.lua` 由提供的 template bytes 讀 count，拒絕 ID0 count 非零；`pool_preflight.lua` 也拒絕 ID0 count 非零。只有一致、同版本的 supplied snapshot 才能進入後續算術規劃；這仍不是 live 原生狀態或恢復成功的證明。

## 原始指令與覆蓋範圍

固定來源 `capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`；`captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。`1258050..12616B6` 單一 unwind root 38,502 bytes，SHA-256 `664ced675a9fe5708c57cd8c735065688d8fdc9ce5d6a13908bb3f572ca191ed`，6,440 條指令全部解碼且正常 CFG 可達。先前[模板預算證據](indexed_float_template_budget_evidence.json)、[三 S 證據](indexed_float_pool_triple_members_evidence_v3.json)、[counter 證據](indexed_float_pool_counter_bounds_evidence.json)均以 SHA 固定，再從同一擷取逐條對 bytes。

| RVA | 原始 bytes | 已核對語義 |
|---|---|---|
| `12580E7` | `33d2` | `EDX=0` |
| `12580E9` | `488d0d30ae2302` | `RCX=image+3492F20`，模板表起點 |
| `12580F0` | `41b828e22d00` | `R8D=2DE228=73×A0E8` bytes |
| `12580F6` | `e8a529e300` | 呼叫已核對的 byte-fill helper `208AAA0` |
| `1257722` | `4869d0e8a00000` | selector 以 `ID×A0E8` 定位模板 |
| `1257730` | `890d125b2102` | 把 ID 寫至 selector global `346D248` |
| `125773F` | `c78402e0a0000000000000` | 把所選模板的 `+A0E0` node count 設零 |

`1257720..125803D` 的保存 helper rows 共 628 條；固定 bytes 檢查找到 14 個指向 template base 或 selector global 的 RIP references，位於 selector 與 type1/2/3/4 appender、event、secondary payload helpers。這只排除**直接 RIP 引用**的其他來源，不排除傳入 pointer 後的跨界寫入或 opaque callee。ID1 在 `125C158` 選取後，`125C164` 先呼叫 type3 appender，`125C170` secondary，`125C17C/188/194` 才呼叫 event helper；沒有把「其他模板同樣正確」當作已證。

5 個動態 selector 的有限來源：`125A300` 用 RBX 倒數完成後的 `+3D`；`125A79A` 用另一段 RBX 倒數後的 `+3E`；`125B5E6` 從 `RBP+1FC0/2030/20A0` 的三筆 ID `41/42/43` 迭代；`125B7F7` 用已清零 EAX 的 `+44`；`1260691` 用已清零 R12D 起始的 EBX 四次循環 `+29`。正式 JSON 包含每個來源與 call 的原 bytes、reaching definitions 及每個 ID。這些推導同樣以上述 stack/register 不受 opaque callee 意外改動為前提。

## 同一 D 的 ID0 呼叫

已保存的完整 `142CB90` builder root（673 條指令）有三個直接 `140C2E0` 呼叫：

| RVA | S／ID | ID0 關係 |
|---|---|---|
| `142D0BD` | primary `S=D+886C0+recordOffset`；EDX 讀 `D+8B6B0+n*4` | 動態。已證 builder 正常 append 的 table stores 產生正數模板，前提包括有效 count、未被 callee 改表；若來源損壞或另有 writer，這個 call 仍可能讀 0。 |
| `142D144` | 第三 S；`setbe dl` 後 `add edx,2D` | `2D` 或 `2E`，非 0。 |
| **`142D171`** | primary `S=D+886C0+recordOffset`；`142D16C: 33d2` 清 EDX，`142D16E: 4903ce` 加 recordOffset，`142D171: e86af1fdff` 呼叫 `140C2E0` | **明確要求 ID0**。`142D082/090/09F` 的 fallback 分支可到此；這是實際 caller 語義，不能刪去或一律視為壞資料。 |

同根正常 append 的模板表寫入位於 `142CFE9/CFF7/D005/D013/D02A`，值為 `27/28/26/24或25/29起的正數`；詳細前提沿用三 S 證據。已保存的完整 `142D870` 更新 root（1,186 條指令）七個直接 `140C2E0` 呼叫的 EDX 指令均為 `19/1A/1B`，沒有明確 ID0。此 root 另在 `142E34D → 142F530` 呼叫更新 helper，其主 ID 來自 template table；不得把此表在部分初始化或損壞狀態下必定非零視為本輪證明。`142D870` 不是 D constructor；已證 D constructor 是 `142B990`，本輪沒有掃描它的全部 caller。以上是**兩個已證同 D roots 的有限掃描**，不是全程式所有 caller 的封閉清單。

## 對 preflight 與 partial 恢復的決策

`140C2E0` 的 `140C2E8..2F2` 先比對 `S+1C` 與 requested ID，相等就早返。不同且舊 ID 非零時，`140C306` 呼叫 `140C200` 清理 S 已持有的 nodes；`140C319` 保存新 ID；`140C323/32B` 按模板 `+A0E0` count 決定是否分配。因此：

1. 對**一致且舊 ID 非零**的單一 S，若 supplied ID0 count 確實為零，`S→ID0` 是可規劃的清理轉換：先釋放該 S 已持有格，之後不新增格。它不是整筆 record 的三個 S 同時清理，也不是引擎外部資源已實際釋放的執行期證明。
2. 對**舊 ID0、allocated=0**，再請求 ID0 會直接早返。若舊 ID0 卻持有格，早返不會修好此矛盾；snapshot/preflight 必須拒絕。現有 `pool_preflight.lua` 已拒絕 `requested_id=0` 且 `allocated>0`。
3. 對**舊 ID 非零但只部分配置**且 S/P ownership 仍一致，`舊ID→0→目標ID` 可作待實作恢復方案：第一步清部分格，第二步重新申請。單純重呼叫相同目標 ID 會早返。preflight 必須把兩步按真實順序計入 used/peak，目標配置若仍缺容量還會再次部分成功；必須另有原生執行、同步、失敗回滾與事件／資源狀態恢復設計。現有 plan 的 `state_semantics=full_allocation_plan_not_native_post_state` 正確標示它只是完整配置算術模型。

**停止點：** ID0 可列入候選的 *per-S 清理／轉換操作*，條件是同 build 的 supplied template count0、S/P/indices 唯一所有權與一致性、操作順序、容量，以及所需事件／資源重建均被另行核對。尚缺 live writable ID0 等同性、全部 emit/payload 邊界、後續 writer、完整 caller 與執行期原生恢復；不把 ID0 當通用 reset，也不把這輪離線證據當成八人 Mod 驗證。

## 重跑

[重播程式](indexed_float_template_zero_replay.py)、[正式證據](indexed_float_template_zero_evidence.json)、[同來源重跑](indexed_float_template_zero_recheck.json)。正式與重跑 SHA-256 均為 `d44d5741d7fc0f8b5122f8285c466442f897328c5233348853f8bce53f37125d`；兩次輸出逐 byte 相同。重播只讀固定擷取與已保存 evidence，不開遊戲程序、不做新擷取或 native 執行。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_template_zero_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_template_zero_new_recheck.json
```

輸出必須是尚不存在的路徑。另一代理已對條件範圍及 `140C2E0` 舊／新 ID0 分支作獨立核對；這不等於初始化終態、其他 writer 或原生恢復的完整證明。
