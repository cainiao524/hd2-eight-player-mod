# 八格名冊插入候選與七函式共同建置

## 狀態與成品需求

`0.7.0-offline` 新增 [roster_insert.py](Native/roster_insert.py)，將四個固定插入函式的 pointer、primary、auxiliary 寫入導向既有八格儲存，並與 producer、receiver、完整 mover 共同建置。這推進玩家 ID／記錄不因第五至八筆而覆蓋相鄰資料的需求。

**目前交付是原生機器碼產生器與离線驗證，沒有可安裝的八人 Mod。** 真正加入事件的 caller 契約、完整生命週期、平台加入、角色建立和多人任務均未完成。以下「八筆」指合成名冊資料，沒有八個帳號參與測試。

目標為 Windows x64 Steam build `25480438` 保存 profile；版本及 EXE／game.dll 指紋見 [manifest](candidate-manifest.json)。指紋是候選的來源檢查，不代表已驗證現行遊戲相容。

## 四個原生入口

| 候選名稱 | 原入口 | 原 ABI | 行為 | 候選 bytes |
|---|---|---|---|---:|
| `append_legacy` | `60CBA0` | RDX=entity | 在 tracked 尾端追加 | 502 |
| `append_registered` | `540850` | RCX=entity | 同上，另一個 ABI | 505 |
| `dense_legacy` | `60CA80` | RDX=entity、R8=flags pointer | 插入 dense／prefix | 597 |
| `dense_registered` | `540920` | RCX=entity、RDX=flags pointer | 同上，另一個 ABI | 596 |

四者均由 global `3326468` 取得原名冊 S。令 DWORD `T=S+80h`、`D=S+84h`、`P=S+88h`。候選使用與 [mover bundle](NATIVE_ROSTER_BUNDLE.zh-TW.md) 相同的 `680h` 儲存 B，起點依序為 pointer `0`、primary `40h`、auxiliary `3C0h`、property `580h`。

每個原 body 有 14 個直接陣列 stores；property 由後續 producer／receiver 初始化，dense 的可選 mover 則搬四組完整記錄。本候選不把四種入口串成同一次加入：append 與 dense 都各自增加 T，重複呼叫同一 entity 會破壞計數。

## 保留的初始化與副作用順序

**Append** 選 ordinal=T，清 primary，將 auxiliary 清零並設 relative `+14h` byte=1，再寫 pointer。實際 `172F790` map helper 寫入 ID→ordinal 後，原 caller 才增加 T；D／P 不變。因此新記錄仍在 `[D,T)` 待整理區。

**Dense** 在 flags[0]=0 時選 ordinal=D，保留 primary；flags 非零時選 ordinal=P，必要時先呼叫八格 mover 將 P 記錄搬到 D，再增加 P、清新目的 primary。兩分支都初始化 auxiliary、增加 D／T、更新 high-water、寫 pointer，最後 tail-jump 到同一 map helper。Property 的既有 bytes 在這個階段保留。

原四函式沒有本地 R11 活值，因此候選在每個 array store 前加入 `MOV R11,B−E8h`，將該 operand 的 RBX 改成 R11，依 SIB 使用 REX.B 或 REX.X。Primary 位移加 `20h`，auxiliary 加 `1E0h`，pointer 不加；RBX 始終保留 S 給 counts／map。內部分支重新定位並升成 near branch，外部 global、mover call 及 map call／tail-jump 全部重算。詳見[固定來源](../five_player_feasibility_20260927/roster_insert_native_findings.zh-TW.md)。

## 入口檢查與尚未證明的前提

新 guard 在原 prologue 前檢查 global 綁定、**直接比較 T<8**、P≤D≤T。這避免原 `(uint32)(T+1)<=4` 的回繞問題。Dense 另要求 **D==T**：原 body 在 D<T 時會覆蓋待整理記錄，尚缺能證明安全的 caller 空洞／轉換契約，因此目前先拒絕這個狀態。

| R10D | 拒絕原因 |
|---:|---|
| 1 | Global 中的 S 與綁定不符 |
| 2 | T 不小於 8，包括 FFFFFFFF |
| 3 | P／D／T 順序不成立 |
| 4 | Dense 插入仍有待整理尾端 D<T |

拒絕時 entry RSP 未變，沒有 prologue／陣列／map 寫入；RCX、RDX、R8、R9 與非揮發 GPR／XMM 保留，RAX、R10、R11、flags 可改變。整合者仍須提供會終止上游操作的拒絕 handler，不能假裝原函式正常成功。

**D==T 是候選新增限制，尚未證明真實 caller 皆能滿足。** 下一步必須接上壓實／待整理記錄流程及實際呼叫契約，才能宣告完整名冊生命週期可用。

Guard 也沒有證明 map 有效。Map 必須具備有效 backing、新的非 sentinel ID 與可用 bucket；原 helper 接受重複 ID，滿表／零容量時可能在其他資料已改動後寫 `[4]`。沒有完整錯誤恢復。Global 和 counts 會在 guard 後由原 body 再次讀取，因此必須有涵蓋整段操作的同步保護；兩次讀到相同值不能取代它。

完整前提見[獨立審查](../five_player_feasibility_20260927/roster_insert_native_prerequisites.zh-TW.md)。

## 已通過的離線驗證

[測試報告](verification/native_roster_insert_tests.json)記錄 **9 個方法、515 次 x64 模擬執行、0 failures／0 errors**：

- 兩種 append ABI 的所有有效 P≤D≤T<8 分段，以及原四格對照。
- 兩種 dense ABI 的全部 prefix 選擇、flags 真／假與可選搬移，另含非零 flags=255。
- 完整非 stack 記憶體頁比對，確認原初始化／保留欄位、map 與 count 順序；GPR／XMM／stack 恢復。
- 新 guard 拒絕、未映射的錯誤 S、count 回繞值、rel32 邊界及七函式區域交疊。
- 每種 append 在**同一份持續存在的合成記憶體**連續加入八筆不同 entity，第九筆被拒絕，原八筆資料與 map 維持不變。
- 實際執行 append → producer → receiver：插入建立 entity 17→ordinal 7，producer 透過該 map 填入 property，receiver 再按同一 ID 更新槽 7；network index=4。Producer 同時沿用既有固定 field／descriptor oracle。

Map helper、mover、producer 的 index leaf 及 receiver 均執行保存／產生的 x64 指令。只有 allocator 使用成功契約，incoming bytes 人工提供；未执行真實 serializer、網路、遊戲 callback 或帳號加入。獨立審查範圍見[候選審查紀錄](verification/native_roster_insert_review.zh-TW.md)。

## 重現與共同建置

在工作區根目錄，已有 [native test 依賴](requirements-native-tests.txt) 時可執行：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_insert.py
```

以下只產生 JSON。所有地址來自[合成設定](verification/native_roster_insert_addresses_synthetic.json)，沒有代表實際配置；輸出檔名須尚不存在。已保存的[七函式範例](verification/native_roster_insert_bundle_synthetic.json)可由同輸入逐 byte 重建。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/Native/roster_insert.py `
  --evidence five_player_feasibility_20260927/roster_insert_native_evidence.json `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_roster_insert_addresses_synthetic.json `
  --output NEW-roster-insert-bundle.json
```

共同建置器保留既有三函式 bundle，加入四個插入 code／reject／原碼範圍及 map helper 範圍，檢查有限已知區域交疊。這沒有配置記憶體、註冊 Windows unwind、安裝 hook 或提供錯誤恢复。

後續[原四格執行調查](../five_player_feasibility_20260927/roster_compact_counterexample.zh-TW.md)確認 `60CC70` 的兩次 copy 在 `P<D<T` 且 tracked 記錄互異時，會覆寫原 D 並留下錯誤 map。因此不能直接重定位後宣稱保留 pending 記錄；下一步先釐清 append dispatch／pending 所有權與實際 caller 前提。本插入候選的 `D==T` 限制仍未解除，不能把完整生命週期宣告可用。其後仍需分類、移除、其他讀者、完整建立／發布／清理與原型及多人驗證。
