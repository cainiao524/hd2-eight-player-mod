# `94BE10` 玩家數 consumer：固定原碼與八人局部候選切點

## 固定來源與驗證

本輪僅讀 Steam build `25480438` 的保存 capture，未操作遊戲程序、新擷取、安裝或修改現有候選。保存 capture 的 report/data SHA-256 分別為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`／`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`；capture identity 為 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

[replay](roster_player_count_native_replay.py) 從固定 unwind chain 讀 `94BE10..94C44A` 四個連續 fragments，共 1594 bytes、359 條指令，body SHA-256 `0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e`。`94C43E..94C44A` 雖位於 `94C43D ret` 之後，仍由 `94C1AB` 及 `94C234` 分支可達，是程式碼而不是 table。完整 CFG 有 53 個本地分支、5 個 RIP data/address refs、6 個外部 rel32 calls，無間接控制；所有指令在 CFG 中由入口可達。直接必要的 tag predicate `177E3C0..177E45C` 另固定為 156 bytes、55 指令，SHA-256 `6f2946133c59eff112dee7cd648bef3126d78e4f9b4dde1fc07f32af4db54a38`；它不接收玩家數。

[evidence](roster_player_count_native_evidence.json) 的 `bodies['0x94be10']` 與 `bodies['0x177e3c0']` 含完整 bytes、逐指令 RVA／bytes／SHA／encoding、fragments、CFG、relocations。`caller_count_producer` 限定使用已固定 `94C9C0` body，釘住 `[1,4]` clamp 和全部 15 個 `[caller RSP+38h]←EBP`／`call 94BE10` 配對。重跑至另一輸出得到逐 byte 相同的 [recheck](roster_player_count_native_recheck.json)。可在 workspace 根目錄以以下指令重現，`NEW.json` 須尚不存在：

```powershell
$cap = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
$env:PYTHONPATH = 'eight_player_candidate_20260927/.native-test-deps'
py -3.12 -B five_player_feasibility_20260927/roster_player_count_native_replay.py --evidence $cap --output NEW.json
```

## 實際 count 資料流

`94C9C0` 在 `94CA1D..94CA37` 將輸入 unsigned clamp 至 `[1,4]`，存在 EBP。它的 15 個 `94BE10` 呼叫都先將 EBP 寫到 outgoing `[RSP+38h]`。`94BE10` push RDI、R13 並 sub RSP,108h，故這個玩家數位於 **body `[RSP+158h]`**；`94C06E` 是唯一讀取。`94C075/79`、`94C07B/7F` 分別以 unsigned 含界比較每筆 record 的 `+F4h` min、`+F8h` max，經 AL 與 `94C0AD/AF` 控制正常資格。R8 是來源 record base、R9D 是 record 數，遍歷步幅 `118h`。`[body RSP+168h]` 非零且 SIL 成立時，`94C09B` 會直接跳過 BL/CL/AL/DL 正常資格鏈；caller 確有一個布林 override 實例。

`[body RSP+150h]`／R12D 是另一個 `tech_level` 參數，後段 `94C1E9`、`94C26F`、`94C2E3` 的 `tech_level−1` float 表索引與玩家數無關。玩家數沒有進入 `94BE10` 的地址計算、容量、倍率或對外 callee 參數；選中 record 後會重新覆寫 EAX。完整局部語義及外部副作用邊界見[獨立前提](roster_player_count_native_prerequisites.zh-TW.md)。

## 可實作的局部八人政策

明示新政策為：`94C9C0` 的 upper clamp 由 4 改 8；對 `94BE10` 每筆 record，僅在 **max 恰為 4 且 min≤4** 時把比較上界視為 8，其餘 min/max 和 tech level 保留。增加 min 條件使原本 min5/max4 的空範圍仍為空。這令有效四人 record 對 5..8 延伸原選集，而上游 `num_players` 可傳實際 5..8。它是候選政策，不是已證遊戲資產的原意。後續已建立離線[原生 patchplan source](../eight_player_candidate_20260927/Native/player_count.py) 與[整合說明](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)；本份 replay／evidence 仍只負責固定原指令。

可審閱的 native 改接位置：

| 位點 | 原 bytes／動作 | 候選動作 |
| --- | --- | --- |
| `94CA30` | `B8 04 00 00 00`，`mov EAX,4` | 同長度把 imm32 改 8；保留前面的 raw0→1 下界 clamp |
| `94C07B..94C081` | `41 3B 47 08 77 04`，`cmp EAX,[R15+8]`／`ja 94C085` | 完整 6 bytes 以 `E9 rel32`＋NOP 跳近端 trampoline；若 `[R15+8]==4` 且 `[R15+4]<=4`，以 8 作上界，否則重播原上界比較；分別回 `94C081` 接受或 `94C085` 拒絕 |

原 `94C075/79` 下界比較不變。完整 CFG 顯示切點內 `94C07F` 僅由 `94C07B` fallthrough 到達，沒有其他 branch target；原 `94C07B` 僅由 `94C079` fallthrough 到達。trampoline 的兩條比較路徑只用 EAX／flags 與原 record 欄位，無須借用 live GPR；所有路徑在回原 `94C081/85` 前完成分派。後續 source 採**原位** 5／6 byte patch 與 51-byte 近端 trampoline，沒有 clone 全函式，因此不搬移原 body 的 5 個 RIP references 或 6 個外部 calls；安裝時仍須驗當前映像 bytes、rel32 可達、同步寫入、unwind 與 record 生命週期。source 目前僅生成離線計畫，未安裝或單獨啟用。

若所有有效來源 record 均滿足 `1 <= min <= max <= 4`，對 5..8 的新資格結果等同原 count=4：只有原 max=4 的 record 原先能接受 4，且新上界 8 令它接受 5..8；其餘 max<4 的 record 仍拒絕。count 1..4 結果保持，override 同樣繞過比較。在其他輸入、source bytes、tags、flags 與外部 callee 結果穩定時，可用完整原函式 count4 的執行作候選 count5..8 的選集／輸出 oracle。

**尚未取得真實 R8/R9 來源 records 的 min/max 值與生命週期，不能把上述有效域當成 runtime 事實。** min5/max4 等空範圍因新 `min≤4` 條件而保持原拒絕；其他未驗 profile 如 min1/max6 對 count8 不保證與原 count4 等價。輸出容量、`94C9C0` 已發出的其他通知、departure pending/D=0 count 語義、callback 重入與八帳號任務流程亦不由此局部切點閉合。尤其原 raw count0 會先 clamp 至1，不能用新 `1..8` guard 排除；pending D=0 下溢為 `FFFFFFFFh` 的來源仍須另定契約。
