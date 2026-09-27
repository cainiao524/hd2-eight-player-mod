# 20 筆雙 S 記錄的第二 S：有限離線來源收束

## 成品需求、實作決策與停止條件

- 成品需求：八人共用池方案需保留這 20 個第二 S 的實際配置，並有可證的恢復方式；不能由主 S 的一格模板推算第二 S 的需求。
- 實作決策：只沿既有 double-record 欄位引用、已接合同一 D 的直接 callers，以及一次必要的衍生 record 位址追蹤，尋找 `140C2E0／142F6E0／142F530／142F780` 配置入口。
- 停止條件：這個有限集合找到配置來源，或已核完卻仍無法接上來源，即停止此分支。沒有展開所有渲染／helper callees，也沒有重新掃描整個 capture。

**結果：此有限集合沒有定位第二 S 的配置来源。** 新接上的衍生位址鏈把第二 S 傳給 `140D4F0／140DE80`；既有 literal 引用則對應初始化、清理及更新。這不證明其他來源不存在，也不證明第二 S 永遠為空。

## 1. 對象與既有來源範圍

每筆 record `R = D + 8B738 + n*180`，第二 S 為 `R+88 = D+8B7C0+n*180`，實體共有 20 筆。位移、stride、模板 ID 與 RVA 均為十六進位；筆數為十進位。

重播使用 consumer 證據內固定的 12 個同 D roots：`142B990、142BED0、142C9B0、142CB90、142D870、142EE70、142FED0、142FF90、1430450、14329B0、1433020、14335F0`。另核既有 event helper `142FA60` 與已保存完整的 `1431FF0`。總計重新比對 40 個 code spans、5,639 條已保存指令；沿用原證據的 chained-unwind 分段及 code/data 分界。

既有 literal `8B7C0` 引用共 13 處，其中 5 處已有同 D 來源：

| RVA | 本地用途 |
|---|---|
| `142BCD9` | 建立階段以 `140C160` 初始化空 S |
| `142CA67` | 清理階段以 `140C200` 清理 S |
| `142E61D` | 第二 S 的既有索引／事件更新；該組配置 call `142E7F3` 使用的是主 S |
| `142FB30` | 第二 S 傳给 `140D710` 更新事件 |
| `142FDFF` | 第二 S 傳给 `140D710` 更新事件 |

其餘 8 處位於 `182A550、182BFB0、18D2B60` roots，仍缺同 D base provenance。位移相同不足以把它們認作這組 S，也不足以斷言它們必然無關。本輪保留此界限，沒有擴展到這些未接合的物件樹。

## 2. 必要的衍生位址追蹤

`1430450` 的固定 same-D caller 在 `1431117` 呼叫 `1431FF0`：

```text
14304C8  mov rsi, rcx                    ; caller D
14310F0  mov eax, ebx                    ; record ordinal
14310F2  lea r8, [rsi + 8B738]
1431109  lea rcx, [rax + rax*2]
143110D  shl rcx, 7                      ; ordinal * 180
1431111  add r8, rcx                     ; R = D + 8B738 + ordinal*180
1431117  call 1431FF0
1432040  mov rsi, r8                     ; callee keeps R
14321CF  lea rbx, [rsi + 88]             ; second S
14321D6  mov rcx, rbx
14321D9  call 140D4F0
14322AF  mov rcx, rbx
14322F1  call 140DE80
```

完整 root 的正常 CFG 及 15 項 reaching-definition 檢查重新通過，使用 Win64 call 對 volatile registers 的 clobber 規則。這些檢查也涵蓋 `142FA60` 的兩個 literal 第二 S event calls。

`1431FF0` 本地沒有四個選定配置入口的直接 call。`142FA60` 的 21 處直接 call 全部指向 `140D710`。這是本地直接呼叫的結果；没有宣稱 `140D4F0／140DE80` 的任意後代或外部 event callbacks 永遠不配置。

## 3. 同 D 配置入口的有限排除

12 個指定 roots 共找到 21 個直接配置 call；原 bytes、callee、分類與 caller window 保存在 JSON。它們對應已知玩家 S、singleton、其他 record families、三 S 群組及本組的主 S。

`142F530` 確有以 `R+88` 配置第二 S 的通用分支；需第六參數為真，經 `142F780` 呼叫 `140C2E0`。但已接合的五個 callers，其 record base 均不是本組來源：

| F530 call | 相對 D 的 record base | 與目標 `8B738` 的差值 mod `180` |
|---|---|---|
| `142E34D` | `886B0` | `F8` |
| `142E84B` | `8D540` | `08` |
| `142E8D9` | `81C88` | `150` |
| `142E933` | `87D90` | `D8` |
| `142E9D6` | `88528` | `F0` |

在同一 D、整數 ordinal 與正常不回繞位址運算的前提下，五組 `R+88` 的地址形式都不能等於目標第二 S。這項算術排除只針對列出的 caller 參數；不把越界或無效狀態造成的記憶體別名認作正確配置來源。

## 4. 容量／恢復決策與真正缺口

目前仍需以下任一來源才能改變第二 S 的容量或恢復策略：

1. 已證同 D 的配置呼叫，其 S 參數等於 `D+8B7C0+n*180`；或傳入 `142F530` 的 R8 等於 `D+8B738+n*180`，並證明 secondary flag 啟用。
2. 可涵蓋所有相關 aliases／生命週期的契約，證明這些 S 在所需階段始終為空。有限掃描沒有找到配置，不構成該契約。

因此保留所有 20 個第二 S 的實際 template ID 與已配置 nodes；與主 S 合計的 40 個 S 均維持在 owner inventory，不能按 active count 裁掉。不能填零需求、猜成模板 `1B`，或為了恢復擅自使用 ID0 清除。建立時為空與有 cleanup 入口，也不能替代完整配置／保留時點的證明。

本分支已達停止條件。下一步只在出現上列可接合的新來源時重開；不沿未展開的 helper 樹反覆擴搜。未驗證執行期狀態、完整 pool aliases、整池峰值或八人加入成功；候選 Lua 與既有正式證據均未修改。

## 5. 重播與指紋

- [重播程式](indexed_float_double_secondary_replay.py)，SHA-256：`ebda230bde497bc9af37fb1894be01c90e1b661d31611994d6fb78de8e597382`。
- [證據 JSON](indexed_float_double_secondary_evidence.json) 與[同來源重跑](indexed_float_double_secondary_recheck.json) 逐 byte 相同，SHA-256：`532e03af3a6002f775b1c7a2611676c06a21caa0ae7bd62478e316619d2888ea`。
- JSON 固定並驗證 5 份前序證據與 reaching helper 的 SHA-256；重新核對 capture manifest／data 指紋、來源 span bytes 與原指令 rows。
- 主代理另逐讀重播與有限結論，核對來源指紋、40 個 spans，以及 273 條輸出 rows／240 個不同地址的原 bytes；[核對記錄](indexed_float_double_secondary_review_checks.json)保留此範圍。15 項 reaching-definition 結果由作者重播，主代理沒有獨立重算；不宣稱已完成全面獨立語義審查。

以不存在的 output 路徑重跑；程式會拒絕覆寫：

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_double_secondary_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_double_secondary_local_recheck.json
```

本輪只讀已保存檔案，沒有查詢或操作遊戲程序。前三次單次擷取授權已耗用，第四次仍待答覆。
