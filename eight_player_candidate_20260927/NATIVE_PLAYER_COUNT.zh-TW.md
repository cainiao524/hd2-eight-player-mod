# 八人玩家數與設定範圍：離線原生候選

## 目的與目前狀態

[player_count.py](Native/player_count.py)產生兩處固定版本的機器碼修改及一個 51-byte 跳轉片段。它把 `94C9C0` 的玩家數上限由四改為八，並讓第 5–8 人沿用原先適用於四人的設定記錄。真正的玩家數保留至八；另一個 tech level 參數及權重索引維持原行為。

這是候選元件的離線修改計畫。程式只讀提供的證據、檢查 bytes 並輸出 JSON，沒有配置可執行記憶體、安裝修改、查詢或寫入遊戲程序。`installable=false`、`game_execution=false`、`multiplayer_verified=false`。它沒有完成名冊離隊、加入、角色建立、同步或八人任務驗收。

## 固定版本與來源

目標為 Steam build `25480438`、Windows x64。EXE SHA-256 為 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`，game.dll 為 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。這些是固定研究 profile，不能視為已驗證目前載入的程序版本。

| 固定 body | bytes | SHA-256 |
| --- | ---: | --- |
| `94C9C0..94D308`，含原跳轉表 | 2376 | `7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2` |
| `94BE10..94C44A`，含必要 cold fragment | 1594 | `0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e` |

來源是[玩家數完整證據](../five_player_feasibility_20260927/roster_player_count_native_evidence.json)及[上一輪 callee 證據](../five_player_feasibility_20260927/roster_departure_callee_evidence.json)。兩份 JSON 的固定指紋均由 loader 驗證，再驗完整 body 的長度與指紋，最後另驗修改位點的原 bytes。資料流與完整 CFG 見[研究结果](../five_player_feasibility_20260927/roster_player_count_native_findings.zh-TW.md)及[獨立前提](../five_player_feasibility_20260927/roster_player_count_native_prerequisites.zh-TW.md)。

## 新候選規則

1. `94C9C0` 對玩家數作 unsigned clamp `[1,8]`。原輸入 0 仍變成 1，原輸入 1–4 保持，5–8 保留為本身，較大值限制為 8。
2. 每筆設定保留原最低人數。只有「最高人數等於 4，且最低人數不大於 4」時，才將比較使用的最高人數視為 8。
3. 其他最高人數保持原意。`min>4,max=4` 的原空區間不因延伸變成有效區間。
4. 原 override／tag 分支保持；它本來即可繞過通常的範圍資格判斷。
5. 不修改來源記錄、tech level、權重表、配置大小或資源 hash。

對全部滿足 `1≤min≤max≤4` 的設定，count 5–8 選到的記錄與原 count4 相同。因此在其餘輸入、記錄、外部 helper 返回值一致且容量足夠時，可用原 count4 的完整函式輸出核對候選 count5–8。這是明示的新配置延伸規則；遊戲平衡與實際資產是否符合該範圍仍未驗證。

此等價不能推廣至任意記錄。例如 `min=1,max=6` 保留原上界六，所以 count8 仍被排除。元件沒有假設或證明所有執行期記錄都屬四人設定，也沒有藉此保證每種玩法都有八人適用的記錄。

## 精確修改與 ABI

| 原位點 | 原 bytes | 修改 |
| --- | --- | --- |
| `94CA30` | `B8 04 00 00 00` | `B8 08 00 00 00`，只改玩家數上界 |
| `94C07B..94C081` | `41 3B 47 08 77 04` | `E9 rel32` 加 NOP，跳到 51-byte 片段 |

片段輸入是原 `94C07B` 的暫存器／stack 狀態：EAX 是玩家數，R15 指向 record+F0，原下界比較已執行。片段依上述規則比較上界，接受回 `94C081`、拒絕回 `94C085`。原流程之後設定 AL，再於 `94C087 COMISS` 覆寫旗標。

新片段不借用 scratch GPR、不存取 stack、不呼叫 helper、不寫資料，也不能當獨立函式 CALL。完整 CFG 已證明被覆蓋六 bytes 的中間位置沒有其他分支入口。

原 `94C9C0` 與 `94BE10` 其餘 bytes 保持原位，所以不移動原 jump tables、RIP 位移或 calls。Builder 核所有新跳轉的 rel32 範圍，要求 game base 4 KiB 對齊、片段 16-byte 對齊，且片段不與固定 `SizeOfImage=74727424` 的整個 game.dll 範圍重疊。這只檢查已知區域，並不代表地址已配置或與其他候選元件不衝突。

## 重現建置

在 workspace 根目錄執行；輸出路徑須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B `
  eight_player_candidate_20260927/Native/player_count.py `
  --evidence five_player_feasibility_20260927/roster_player_count_native_evidence.json `
  --context-evidence five_player_feasibility_20260927/roster_departure_callee_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_player_count_addresses_synthetic.json `
  --output NEW-player-count-candidate.json
```

[地址範例](verification/native_player_count_addresses_synthetic.json)是合成地址；[對應產物](verification/native_player_count_synthetic.json)保存兩處 expected/replacement bytes、51-byte 片段、所有分支目標、固定來源與明示限制。Python API：

```python
sources = load_sources(count_evidence, context_evidence)
result = build(sources['context'], sources['filter'],
               game_base=game_base, trampoline_address=trampoline_address)
```

## 指令驗證

[測試原始碼](tests/test_native_player_count.py)與[結果](verification/native_player_count_tests.json)共 7 組、188 次 x64 執行／觀察，分成 162 次完整 filter（原版 65、候選 97）及 26 次 context 前綴觀察。前綴在 `94CA3A` 停止，只核兩個參數的 clamp；未執行完整 context 或其通知。

- 原四人合法範圍的 10 種 min/max 組合，逐一比較 count1–4 的原／候選完整輸出。
- 同一有效設定域內，比較新 count5–8 與原 count4 的選集、完整輸出及暫存索引。
- 核其他上限、`min>max` 空區間、原 override 的接受路徑及兩種加權分支。
- 核另一個 tech level 的 1、3、10 三個值；權重位址只依該值變化，不依玩家數變化。
- 核 Win64 非 volatile GPR／XMM、RSP、片段前後全部 GPR、全部非 stack 頁的預期差異、暫存配置及邊界。
- 核第二個 image base、正負 rel32 可達邊界、來源指紋、地址重疊與對齊拒絕。

實際執行原 `94BE10` 加候選片段及原 `177E3C0` tag predicate。`94A0A0`、`949E10`、`173B8D0`、`2088770` 使用明示的資格／倍率、配置及 security cookie 契約替身；替身會破壞 volatile registers，且配置成功範圍限兩個合成 source 的 8-byte 暫存表。測試沒有執行真實資源或配置失敗。

重跑命令：

```powershell
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927/tests/test_native_player_count.py
```

測試會更新對應報告。[Source 審查](verification/native_player_count_review.zh-TW.md)核固定 body、切點、機器碼與地址範圍；[測試審查](verification/native_player_count_test_review.zh-TW.md)記錄 oracle 與替身邊界。

## 整合仍需完成的工作

- 將兩處修改與片段當作同一功能共同安裝／撤回，核對實際載入版本、可執行空間與所有其他候選區域。
- 完成同步修改、指令快取處理及片段所在位址的 Windows unwind；原非 leaf frame 不能因新片段沒有 push 就省略 unwind 設計。
- 核實實際設定記錄、資源有效性、被選中記錄數與 output buffer 容量；原 filter 沒有顯式 output capacity 參數。
- 接合離隊通知的正確 count 與生命週期。前輪 pending D=0 的 `FFFFFFFF` 下溢仍會被 clamp 為 8，來源錯誤沒有因此修正。
- 完成平台加入、原生角色、名冊／元件八份儲存、所有客戶端同步及五至八人的任務全流程測試。

這些缺口阻止本元件成為可安裝八人 Mod；原四人設定的離線輸出對照不能替代八帳號實測。
