# 玩家記錄模板的節點預算：每筆 11 格，新增四筆 44 格

## 結論與適用條件

**後續來源補證：** [owner setup與初始zero-fill](indexed_float_pool_initial_zero_findings.zh-TW.md)已定位`553EB4 → 1258050`的靜態初始化call，並接上共用池最初清零來源；未觀察live模板或後續writer，因此以下預算前提仍保留。

在已保存程式的四段模板建立流程中，玩家記錄使用的模板 `0x17 / 0x18 / 0x19 / 0x1B` 分別加入 **5 / 1 / 3 / 1 個 nodes**。一筆玩家記錄的五個子物件使用 `17、18、1B、19、1B`，故完整配置需要 **11 格**；四筆為 44 格、八筆為 88 格，新增四筆的此項需求為 **44 格**。

這是**依指定建立流程推導的條件式預算**。保存資料不含 writable templates，尚未證明執行期呼叫順序、其他程式對模板的寫入、或載入後內容與這些 emission blocks 完全相同。重播也沒有把原 initializer 當作 native code 執行。不能把這個結果稱為 live occupancy 測量或完整遊戲資源需求。

先前「新增最多 240 格、八筆最多 480 格」來自每個 S 的 12 個索引欄位上限；仍是合法模板的物理上界。現在可為這組具體模板採用更窄的 44 / 88 格條件式預算。**256 格共用池是否足夠仍未確定**：其他用途與切換期間的額外占用，必須在上述條件下合計不超過剩餘 168 格。

## 1. 五個子物件如何對應四種模板

沿用[既有 consumer 證據](indexed_float_consumers_findings.zh-TW.md)中已證明的 `D` 身分與迴圈；record 位址是 `D+0x80E18+i*0x298`。`142DA78` 設定 `R14=D+0x810A5`，亦即 record 起點加 `0x28D`；迴圈尾每次增加 `0x298`。

| Record 內 S 偏移 | 模板 ID | 配置 caller | 節點數 | 各節點事件數 |
|---|---|---|---:|---|
| `+0x28` | `0x17` | `142DE22 → 142F6E0 → 140C2E0` | 5 | 4、4、4、3、3 |
| `+0xA0` | `0x18` | `142DE3B → 142F6E0 → 140C2E0` | 1 | 3 |
| `+0x118` | `0x1B` | `142DACA → 140C2E0` | 1 | 4 |
| `+0x1A0` | `0x19` | `142DE6F → 140C2E0` | 3 | 1、1、1 |
| `+0x218` | `0x1B` | `142DF09 → 140C2E0` | 1 | 4 |

模板 `17` 的 type 序列是 `[2,2,1,2,2]`；`18` 是 `[2]`；`19` 是 `[2,1,2]`；`1B` 是 `[2]`。一筆記錄合計 9 個 type 2、2 個 type 1 nodes，以及 32 個模板事件。事件位於 node 的既有儲存，**不能把 32 個事件再當作 32 個 pool nodes 加上去**。外部圖形／引擎資源仍可能另有配置，本預算只計 node slots。

這些 caller 所在迴圈有 active 條件；11 格是五個 S 全部採用指定模板並成功配置時的需求，不是每個時刻一定已有 11 格。

## 2. 實際建立操作與完整 leaf

完整 initializer unwind root 是 `[1258050,12616B6)`，共 6,440 條指令。四個直線 emission blocks 為：

| Template | Block，右端不含 | Node append calls |
|---|---|---|
| `17` | `[125EA82,125EBA9)` | `125EA93、125EACC、125EB08、125EB44、125EB80` |
| `18` | `[125EC6E,125ECA8)` | `125EC7F` |
| `19` | `[125EE51,125EEA3)` | `125EE62、125EE7A、125EE92` |
| `1B` | `[125F404,125F44A)` | `125F415` |

每段先以 immediate ECX 呼叫 selector，接著只有以 RBP 為基底的來源 LEA 與已核對的 leaf calls；段內沒有條件跳躍、未知 helper 或中途從外面跳入的 normal CFG edge。這只證明選定區塊的順序，不等同證明全 initializer 的每個外部 call 都無副作用。

五個完整 leaf 共 192 條指令，入口均由 initializer 中實際直接 call 證明，所有 branch targets 與 returns 都在所列範圍內：

| Leaf，右端不含 | 寫入意義 |
|---|---|
| `[1257720,125774B)` | 保存 current template ID 至 global `346D248`；選取 `3492F20+ID*A0E8`，將其 `+A0E0` node count 設為 0，另寫 `+A0E4` 的 float。 |
| `[1257830,12578D4)` | 把 node count 增加 1，選擇舊 count 對應的 `D68` element，寫 type 1 與 payload。 |
| `[1257C90,1257D44)` | 相同的 node count 增加操作，寫 type 2 與 payload。 |
| `[1257E00,1257EE9)` | 選擇最後一個 node，增加該 element `+D64` 的 event count；複製 `FC` bytes 至 `+38C+oldEventCount*FC`。不增加 template node count。 |
| `[1257EF0,125803D)` | 有事件時向最後一個 event 追加 `78` bytes secondary payload，增加 event `+E4`；沒有事件時使用 element `+298` 區及 `+388` 計數。不增加 template node/event count。 |

先前 exploratory `1257EF0` 前綴未含完整無事件分支；本次已收至兩個 return（`1257FB5`、`125803C`）。模板 17 在 `125EB68` 的呼叫走「已有事件」條件，對第四個 node 的第二個 event 追加一次 secondary payload。重播另涵蓋無事件分支。

模板 element 的事件計數與 secondary count 初值需要有效初始化。initializer 開頭存在對模板區 `0x2DE228 = 73*0xA0E8` 的 bulk-clear 呼叫；**本次未證明整個函式之後的所有寫入與執行期順序**，因此 Python 模型將 fresh zeroed elements 與 event input 的 `+E4=0` 明列為前提。沒有把合成 payload 說成實際遊戲 stack 內容。

## 3. 八筆方案的容量條件

在模板等同性、有效初始化與上述五個 S 全部配置的前提下：

| 項目 | Nodes |
|---|---:|
| 每筆玩家記錄 | 11 |
| 原四筆 | 44 |
| 八筆 | 88 |
| 新增四筆 | 44 |
| 原池總容量 | 256 |
| 八筆配置後，其餘用途與額外暫存占用的合計上限 | 168 |

以 `other_peak` 表示其他用途的同時占用，`transient` 表示搬移／切換時另持有的 nodes，必要容量條件為：

`88 + other_peak + transient <= capacity`

若保留容量 256，便需證明 `other_peak + transient <= 168`。只看當下一次 free count 有 44 格，不能證明後續峰值也足夠。舊四筆的 active S 亦不能複製為新的 active S；唯一所有權與 cleanup 要求仍依[子物件生命週期](indexed_float_subobjects_findings.zh-TW.md)。

44 個 nodes 對應內部 node bytes `44*0x208 = 22,880`，occupancy bytes 為 44。這只是容量帳目；**不是可直接追加 22,924 bytes 的配置方案**。原 node backing 的末端就是 occupancy 區，擴池仍需另配正確 backing、維持所有 aliases，並處理池滿的 partial allocation／同 ID 不重試。

## 4. 重播與核對

- [重播腳本](indexed_float_template_budget_replay.py)
- [正式證據](indexed_float_template_budget_evidence.json)
- [同來源重跑](indexed_float_template_budget_recheck.json)
- [主代理額外原 bytes／結構核對](indexed_float_template_budget_review_checks.json)

正式 JSON SHA-256：`575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc`。

腳本核對固定 capture 的 report/data SHA，以及前置 consumer / subobject 證據。Python instruction model 僅解釋這五個 leaf 所用的整數地址運算、計數、byte copies 與 JE/JNE；未知指令／未知 register／區外記憶體會失敗，不載入或執行遊戲程式。

33 組合成案例、5,051 次指令步驟通過：四個 emission blocks 各用零／`A5` payload 重播；兩個 node appender 分別覆蓋全部 12 個合法位置；另測 secondary payload 的無事件分支。兩處 conditional branches 的真假方向都有覆蓋。這些案例用來檢查模型、拷貝界限與計數推導，不能代替真實遊戲測試。

主代理以另一段核對程式重讀 capture，檢查 6,788 條 evidence rows、6,654 個不同指令位置，重新驗證完整 initializer fragment 與四段 call counts；重跑 JSON 逐 byte 相同。其他代理因帳號用量限制停止，本次沒有宣稱已完成獨立代理語義審查。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_template_budget_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_template_budget_new_recheck.json
```

輸出路徑必須尚未存在。重播只讀保存資料、建立本機研究輸出。

## 5. 上層初始化探索與下一步

本次另保存 caller `724260` 全部 358 條指令，確認已知 `724542 → 142B990` 的 D 來源仍為 manager 加 `0x4CD1F0+k*0x55A698`。對 D、U、manager、最外層 owner 的 pool 欄位組合做有限 disp32 掃描，沒有找到可直接閉合 used count / cursor / occupancy 初始化的新引用；計算位址、無 unwind leaf、整塊清零仍可能不在這種掃描內。

探索結果分別在 `indexed_float_pool_init_caller_discovery.json`、`indexed_float_pool_enclosing_offsets_discovery.json`、`indexed_float_pool_owner_layout_discovery.json`、`indexed_float_pool_owner_roots_discovery.json`。其中 **`72F780`、`730230` 是新找到的 reader 候選**：以入口 RCX 加 `4CD1F0`，再按外部 index 乘 `298` 讀 `+80E24` float pair，轉交 `1432F10`。目前尚未閉合它們 caller 的 RCX 身分，不列入已證同一 D 的 consumer 清單；後續應先核 caller／註冊來源，不能漏掉後直接宣布改接完成。

對這兩個入口的有限引用掃描已保存於 `indexed_float_extra_reader_xrefs_discovery.json`：未找到已識別的直接 E8/E9 分支、RIP MOV/LEA 引用或 absolute pointers；只有 unwind table 的入口 RVA。掃描不含 writable data，亦不解算任意位址運算，**不能據此說它們不會執行**。後續需要不同來源的 caller／註冊證據，不應重複同一掃描當作進展。

仍待完成：共用池初始化與其餘用途峰值、模板執行期等同性、所有 record aliases、房主／客戶端／roster／玩家實體與相關固定容量的共同修改，以及第 5–8 人的實際加入和玩法驗證。第四次唯讀擷取仍待先前問題的授權；本次沒有查詢或讀取活程序。**八人 Mod 尚未完成。**
