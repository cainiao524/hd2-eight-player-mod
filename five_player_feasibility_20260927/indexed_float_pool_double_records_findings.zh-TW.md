# 20 筆雙 S 記錄：主模板、來源上限與保留占用

## 本輪可用結論

固定同一 D 的這組記錄起於 `D+8B738`，stride `180h`，物理 20 筆。兩個已初始化且會完整清理的 S 分別位於記錄 `+10`、`+88`，即 `D+8B748+n*180`、`D+8B7C0+n*180`；共 40 個 S。記錄結尾正好是 counter `D+8D538`。

`142D870` 的 `142E7F3 → 142F6E0` 對主 S 要求模板 `1F`。模板 initializer 的相應區段加入一個 type 2 node、三個 events。因此，在 count 有效、執行期模板相同且配置完整的前提下，這條主 S 請求路徑需求為 `count` 格，最多 20 格。

**這不是整組 40 個 S 的總占用上界。** 本輪沒有定位第二 S 的全部模板配置來源。更新中仍讀取其已持有的 indices 與 events，不能把當前 count、事件關閉或找不到配置 call 當成其 nodes 已釋放。

另一個已收束的未知是上游 `18A3450`：caller 確實傳入上限 20，callee 確實限制輸出／回傳數量在 0..20；不再只依 caller 的常數推測。但 append 到 D 時沒有逐筆 `count<20` guard，**只有原 count 為零等前提下，單次重建才由此保持 20 的物理上限。** 反覆重建前一定清零的全域流程仍未證明。

## 1. 原始呼叫與資料流

| 位置 | 已保存指令支持的關係 |
|---|---|
| `142D264 / 142D277` | caller stack buffer 為 `[RBP+A0]`，地址放入第六參數 `[RSP+28]` |
| `142D27F` | 第五參數 `[RSP+20]=14h`，即十進位 20 |
| `142D287` | 呼叫完整可讀的 `18A3450` |
| `18A346A / 18A346C` | ESI=0；R15D 讀第五參數 |
| `18A38D1 / 18A38D4` | `cmp esi,r15d`、unsigned `jae`，超限即跳過配置 |
| `18A38D9 / 18A38E6` | 用舊 ESI 形成 `3*ordinal`，然後唯一一處 `inc esi` |
| `18A392A / 18A392F` | 寫一份 12-byte 結果至 output+ordinal*12 |
| `18A3991` | EAX=ESI，返回實際輸出筆數 |

Callee 五次 push 加 `sub rsp,F0`，使 current RSP 比入口低 `118h`；連同 return address，caller `+20/+28` 對應 callee `+140/+148`。這兩個參數不是玩家人數或玩家 network index。

完整 `18A3450` CFG 已驗證：移除 guard 的通過 edge 後，唯一 INC 不可達；從 INC 之後亦不能不經 guard 再次 INC。ESI 的其他 writer 只有起始清零與返回後的 pop；R15 的其他 writer 只有 epilogue pop。輸出區段無 call。故按正常 ABI、有效 stack／輸出指標與 opaque math helper 不破壞 caller storage 的前提，回傳 0..20，最多寫 240 bytes。

浮點分支在此可視為任意篩選，不需追查其精確數學結果才能證明此容量上限。沒有執行 `210D0B4` 或原生遊戲指令。

## 2. Append 筆數與 counter 的限制

Caller `142CB90` 對返回資料每四筆展開一次，餘數逐筆處理。五個 append increment 位於：

- `142D34C`
- `142D3DD`
- `142D46F`
- `142D501`
- `142D758`

每條路徑讀 `D+8D538`，以 `3*count<<7` 形成 record 位移，寫入 record 開頭的兩個 float，再增加 counter。過濾條件可以略過某筆；每份輸入至多追加一次。對返回 0..20 的所有 21 種情境，分組／餘數投影都恰好訪問 `0..returned-1`。

本段無 call；完整 builder 對這個欄位的直接 writer 只有五個 INC，沒有在本函式內先清 counter，也沒有以 20 檢查 append ordinal。有限 disp32 掃描中，額外 writer 只有 `142BFBC`：另一函式 `142BED0` 的已核對清零後綴將其設為零。

因此可使用的條件為：**若該 pass 開始時 counter=0，且無干擾修改，返回資料有效，則本輪最後 counter 在 0..20。** 若帶著既有 count 再進入，來源上限 20 不會自動轉為剩餘容量。

### 越界地址的合成反例

若 append 讀到原 count=20，第一個位置 store 的地址為：

`D+8B738+20*180 = D+8D538`

這個 qword store 已覆蓋 counter 及相鄰 DWORD，後面的 INC 才再次讀該 counter。**實際最終值不能簡化為 21**，而取決於被覆寫的 float bytes。此為指令及位址算術的條件反例，不是實測到遊戲會到達該狀態。

這使候選程式的處理更明確：採集及 preflight 前應確認 `count<=20`；若要在此 builder 位置介入，必須先建立 reset／重建同步條件，不能只相信來源函式的 20。

## 3. 主模板和第二 S 的實際證據界限

`142E5F1` 到 `142E80F` 依 counter 逐筆處理：

1. 從第二 S `D+8B7C0+n*180` 讀現有 active indices、node template 及 event。部分路徑關閉 event `1F` 並標記 dirty，涉及 opaque 外部 event 呼叫。
2. `142E7DC/7EA` 形成主 S 地址；`142E7ED` 傳模板 `1F`；`142E7F3` 呼叫已核對的 `142F6E0`。

這段直接 calls 只有 `12556E0` 與 `142F6E0`，另有間接外部 calls。沒有第二 S 的直接 `140C2E0`、`140C200`，也沒有把事件狀態設零等同釋放的指令。不能由「本區沒有配置」推得其他 caller 不配置或此 S 永遠空閒。

模板 `1F` 的 emission block 為 `[125F891,125F8CB)`：selector、一次 type 2 append、三次 event append。與已固定五個完整 emitter leaves 相接；zero／A5 合成 payload 的兩次重播均得到 nodes=1、events=[3]。前提沿用 fresh template 與 event payload `+E4=0`，未還原完整 initializer stack，也未取得 live template bytes。

`1430450` 的 `1431117` 另外把同一 record 傳給 `1431FF0`。完整 helper 處理 `R+88` 與 `R+10` 的更新／渲染，沒有直接配置或清理 S。它也有由 `R+178>0` 控制的 `R+100` 可選處理；本組 lifecycle 只建立前兩個 S，不能因通用 helper 有第三段就推定本組另有有效第三 owner。

## 4. 建立、保留與清理

沿用已固定 [直接 lifecycle 清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)，constructor 與 cleanup 都訪問這 20 筆的兩個 S，共 40 項，而不是只訪問當前 count。相同 P 與 context 的條件、有效 indices、unique ownership 及 native resource cleanup 前提亦沿用該證據。

已證 `142BED0` 的無 call 清零後綴會清 count 及記錄位置欄位，但不直接清理 S／pool node。其先前 opaque callees 的效果仍未閉合，不能稱整個函式一定保留所有 nodes；同樣也不能以 count 已變零推定它們已回收。

因此 **snapshot owner 清單要保留這組所有 40 個物理 S**，檢查實際 allocated／indices。當前 count 只決定這些已定位更新迴圈的訪問範圍，不能用來裁掉所有 ownership。

## 5. 這項研究如何推進成品

| 問題 | 本輪結果 |
|---|---|
| 解決的成品需求 | 八人資料與共用池在重建、更新、保留及清理時維持一致，避免額外玩家促使已有 count／node 風險被忽略 |
| 改變的實作決策 | 20 筆保留原容量；主模板可按每筆一格計算；snapshot 收完整 40 owner；count 有效性與重建同步須獨立檢查；第二 S 未分類占用不得扣除 |
| 停止追查條件 | 上游輸出上限、caller 每份至多 append 一次、主模板 cardinality、40 個 S 的直接 lifecycle 已連接；本問題不需繼續追浮點 math 或所有渲染 callees |
| 下一個程式／驗證動作 | 在按布局列出 owner 的採集規格加入這 40 個固定 S，獨立於 active count；若要得出全池靜態上界，再查重建前清零的關係和第二 S 模板來源 |

這裡沒有將 20 當玩家容量，也沒有因八人目標把它改為 40。尚未證明整池峰值、所有 aliases、八名真人聯機或可安裝 Mod。

## 6. 可重跑交付與來源

- [重播程式](indexed_float_pool_double_records_replay.py)
- [正式 v2 證據](indexed_float_pool_double_records_evidence_v2.json)
- [同來源重跑](indexed_float_pool_double_records_recheck_v2.json)
- [本代理額外核對](indexed_float_pool_double_records_review_checks_v2.json)
- [有限欄位引用掃描](indexed_float_pool_double_records_refs_discovery.json)

正式 v2 SHA-256：`324b4d436d28b041963d5cb27db0a3496350c292a0e9b026bc885dc3bfc34650`。

五個完整 roots 共 2,793 條指令，37 項 reaching-definition 核對；其中新增完整 `18A3450` 與 `1431FF0`，其餘原指令逐 byte 對照已固定 evidence。模板重播兩組；返回 count 投影 21 組。所有 report／capture-data／前置檔案／重用模型都有雜湊 gate。

同來源重跑逐 byte 一致。產出代理另核 2,968 條 evidence rows、2,896 個不同指令地址的原 bytes 與反組譯；核 40 個 S 的兩兩區間無重疊，並用合成 float bytes 確認越界位置 store 會先覆寫 counter。對應 review_checks_v2.json 保留為產出代理自查紀錄。

後續由另一個 `singleton_review` 代理獨立只讀複核正式 v2：直接對 pinned capture 核同批 rows／五個完整 roots，重算 37 項 reaching checks，確認 producer 的 INC 與兩個 output store 必經容量 guard、重複 INC 必須再經 guard；另核 caller 的零值／回傳 count／四筆展開及餘數索引。未找到推翻上述有限結論的反例。審查沒有修改檔案、重掃 capture 或執行遊戲；上游 20 不等於 caller 剩餘容量、第二 S 未知與全域重建條件仍保留。

欄位掃描涵蓋 disp32 `[8B730,8D540)`，得到 294 個指令引用，其中許多屬不同物件，沒有把 offset 相同視為同一 D。掃描不能涵蓋所有 computed alias、無 unwind leaf 或未保存 code。本次僅按已接合 callers 認定 base 身分。

初版 evidence 保留為中間產物；v2 增加有限 counter writer 掃描、caller stride reaching checks，並修正「越界後 counter 等於 21」這個不成立的簡化。所有研究均為離線，未查詢或讀取遊戲程序。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_double_records_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_double_records_new_recheck.json
```
