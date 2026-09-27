# 雙 float 物件：兩個下游 helper 的改接邊界

## 結論與範圍

已補上 `142FA60`、`1432F10` 兩個原先未核對的函式本體。前置[consumer 證據](indexed_float_consumers_findings.zh-TW.md)已確認 caller 傳入相同 D；本次保存必要 caller 視窗及兩個完整正常程式本體。

**若維持 D 與其其他欄位的原地址，僅將 `D+80E18` 玩家記錄及兩張 metadata 表改接到新空間，這兩個 helper 本體沒有直接需要改接的該記錄／metadata 陣列位址。** 改接仍要發生在 caller；外部 callees、其他呼叫情境及整個八人流程不在此結論內。沒有執行原生程式或修改遊戲。

## 固定證據

- [重播程式](indexed_float_helper_boundaries_replay.py)
- [正式 evidence](indexed_float_helper_boundaries_evidence.json)，schema 1，SHA-256：`c70e0f48ce069decf271f9b69631695da41faaa7c5a373263d0f57a315e6e5d6`
- 前置 consumer evidence SHA：`503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578`。
- 與前置證據使用相同固定 capture `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`；重播先驗 report/data 與前置 JSON 指紋。
- 四個 root 共368條正常指令：其中兩個已接合 helper 為292條，兩個未接合候選另76條。Caller windows與pins另計，不能將重複引用加總為全遊戲覆蓋率。

重播須指定不存在的新輸出檔：

```powershell
python -B five_player_feasibility_20260927/indexed_float_helper_boundaries_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/indexed_float_helper_boundaries_recheck.json
```

## 1. `142FA60` 接收 metadata 對應的物件編號／類別

在 `142FED0` caller，EDX 來自第一張 metadata 表取得的值，R8D 來自第二張；`142FF3F` 傳 RCX=D。另一 caller `142FF90` 在 `14303B3/3BE` 將 R14D/R13D 分別保存進兩表，再以同一組值和 RCX=D 呼叫 `142FA60`。因此這裡的 EDX 不應直接當作 roster network index。

Helper 先對 EDX=-1 返回，再將 R8D-1 作 unsigned 範圍檢查。`0x16` 是此 selector 範圍上限，允許原始 selector 1..23；它不是玩家上限。

其正常本體以 RBX 保存 D，依 selector 在以下其他區域形成子物件地址：`81988`、`81B10`、`81C98`、`88538`、`886C0`、`8B748`、`8D550`，部分使用 `3*ordinal<<7 = ordinal*180h`，部分為固定地址或 count-driven 迴圈。程式呼叫 `140D710` 處理這些子物件；它們各自的 ordinal 範圍不可等同玩家數。

RBX 的明確改寫只有入口保存與 epilogue 還原；正常 callee 按 Windows x64 ABI 保存此非揮發暫存器。在這個範圍內沒有直接存取玩家 record 起點 `80E18` 或 metadata 表 `8D6C4/8D6D4`。搬移整個 D 或更改其他物件家族則會超出上述保留條件。

### 真正被引用的 selector 表

`142FA8D` 產生 image base；`142FA99` 讀取 `142FE6C` 起的23個DWORD RVA，`142FAA0/FAA3` 加回 image base並跳轉。各目標都落在已確認指令邊界。以這些目標補齊間接跳轉後，正常CFG的240條指令全數可由entry到達。

最後一段 unwind 中，`142FE6B` 是一byte NOP，其後92 bytes是該表。共93 bytes另以資料保存；沒有把能被解碼成指令的表格bytes誤算為程式。這也說明不能僅用「反組譯器能解碼」判定所有 unwind 範圍都是指令。

## 2. `1432F10` 的 RDX 是兩個 float 的位元資料

Helper 入口將 RDX 的八 bytes放到原始stack `+10`；push／sub之後，`1432F2A` 與 `1432F58` 分別以單精度讀取該槽低／高DWORD。所選 caller 也從record float pair或stack上的兩個float形成RDX；不能把此函式的第二參數當整數玩家索引。

完整52條指令中，D相對讀取只有：

| 位移 | 寬度與用途範圍 |
|---|---|
| `8D709` | 一byte分支條件 |
| `24018` | 四byte數值，用於浮點計算 |
| `8D710` | 四byte數值，用於返回結果 |

這些都沒有network index的位址乘法。其他存取是stack、常數或另一global物件；`12D7DE0/1004AC0`仍是外部呼叫邊界，沒有在此宣稱其完整功能或八人相容性。

## 3. 兩個候選仍不算已接合路徑

另保存 `142F860` 的28條與 `1433380` 的48條完整指令。它們有相似的 `298` stride及record位移，也會呼叫已知helper，但本輪沒有建立它們entry RCX來自同一D的實際caller链。

因此正式JSON將它們標為 `same_D_admitted=false`。它們應保留為後續來源核對項，不能因為offset吻合就當作已證必改位置，也不能因未建立caller就稱它們是永遠不會執行的程式。

## 對設計的決策

1. 保留 D 的原地址與非玩家記錄欄位，能保留本次兩個 helper 的直接 D 存取。
2. Caller 中讀取 record pair、兩張 metadata 表及其初始化／清理的位址，仍要共同改接。
3. 其他 `180`-byte 物件家族與 shared pool 保留各自容量及生命週期，不能把它們的selector或ordinal全面改成八。
4. 完整consumer集合、外部calls及兩個候選來源仍未全部收束；本結果只是縮小已確認的直接改接範圍。
