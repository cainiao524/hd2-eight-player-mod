# 八格名冊離隊前處理：離線原生候選

## 目的與界限

[roster_departure.py](Native/roster_departure.py)將完整 `605950` 離隊前處理接到既有八格名冊儲存 B。六處 pointer／primary／property 讀取使用相同 B；原 `6059EE` 這一處額外 network reader 改呼既有八格 getter。保留原資源清理、關聯物件處理、manager 迴圈、通知與間接尾跳，並修正候選有效狀態下 pending 成員離開時的兩個預測計數。

**這是受執行契約限制的離線原生候選，尚不可安裝。** 從入口檢查至所有回呼及後續真正名冊移除之間，整合層必須保證 S、B、target 身分、map／ordinal 及 P/D/T 的有效生命週期與狀態穩定。目前沒有提供或證明該同步機制；入口 guard 不能阻止另一執行緒或回呼修改名冊，也不能撤銷先前清理副作用。

共同產物包含 **十三個 roster 函式**，另帶上一版兩處玩家數原位修改與 51-byte 跳板；不把跳板當成第十四個 roster 函式。原十二函式 bundle 與 player-count 元件內容保持，可重現檢查其嵌入產物。

## 固定版本與必要證據

目標 profile 為 Windows x64、Steam build `25480438`；EXE SHA-256 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`，game.dll `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。這些是保存證據的版本，未核目前執行程序。

原 `605950..605F2F` 為 1503 bytes、346 條指令、13 個 unwind fragments，完整 body SHA-256：`4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681`。Builder 先驗[完整來源 evidence](../five_player_feasibility_20260927/roster_departure_native_evidence.json)指紋，再驗 body；指令長度與重定位表固定於 source，執行建置不需要反組譯器。

[必要副作用及 caller 證據](../five_player_feasibility_20260927/roster_departure_native_prerequisites.zh-TW.md)與[候選契約審查](../five_player_feasibility_20260927/roster_departure_candidate_contract.zh-TW.md)區分已證原指令、候選新規則及未知執行期前提。

## 入口檢查與失敗契約

輸入 RDX 是目標 entity；RCX 不是 S。新入口在原 prologue 及第一次可能的 `disconnected` 回呼之前，乾式核對：

1. 全域名冊等於指定 S，target 非 null。
2. `0 < T <= 8`、`P <= D <= T`，map capacity 為 8。
3. target ID 不等無效 sentinel 或 empty key，有限八 bucket 查找確實命中。
4. ordinal 小於 T，`B.pointer[ordinal]` 指標等於輸入 target。
5. dense target 的 prefix flag 與 P 分段一致；pending target 仍受支援。

失敗還原原 entry RSP、四個參數暫存器及所有使用過的 nonvolatile，R10D 放入 1–10 原因碼後跳至整合者提供的 reject address。此路沒有外部呼叫或非 stack 寫入；七次 scratch push 會寫入 entry 下方 56 bytes。原因碼與可改變的暫存器列於產物 `reject_reasons`／`reject_state`。

這不遍歷並證明全 map bijection，也不驗證 OS 層面指標可讀性、外部物件所有權或排他。有效 map/backing、B、target 與同步必須由整合層提供。Reject continuation 尚未實作，不能假設 caller 會自動中止後續派發或恢復已完成的工作。

## 陣列與原資源行為

| 原位點 | 候選讀取 |
| --- | --- |
| `605A0D`、`605B96` | `B + ordinal*8` pointer |
| `605A26`、`605A3A`、`605A4E` | `B + 40h + ordinal*70h` 首 DWORD |
| `605A5B` | `B + 580h + ordinal*20h` 關聯 entity ID |
| `6059EE` | 同 S／B 的既有八格 getter，返回完整 network-index DWORD |

六處以 R11 短暫裝入對應 B bias，R13 始終保持原 S。三個 primary helpers 的 RDX owner 仍為原 S、R8D 仍為 target ID，三次原 DWORD 重讀也保留。其完整原指令沒有透過 S 再讀 inline roster 陣列，但會移除外部 registration、補洞或清 pointer，必要時釋放 backing；不可省略這些清理呼叫。

只有這一處 getter callsite 改接，沒有全域替換 `606820`。原 `FD9C80` 關聯查找、mode4 資源支線、間接 handle 回呼、`FD9D40`／出參、manager 迴圈與尾跳均保留。其他外部函式保持原目的位址。

## 新計數政策與 frame

入口在已驗證 ordinal、D 的同一狀態下計算：

```text
remainingDense = D - (ordinal < D ? 1 : 0)
```

兩個原 `D−1` 通知都讀這個保存值：dense 離隊扣一、pending 離隊保留 D，pending D=0 仍為 0。這與後續名冊移除的 dense-count 算術一致，是明示新增的通知政策；尚未證明遊戲原通知的業務契約或 pending 的真實 caller 可達性。

原尾部 `player_count` 繼續讀當時 `[held S+84h]`，不改成 remainingDense。只有在整段 D 不變的前提下，該尾部值才等於入口 D。上一版 `94C9C0` 仍把 0 夾成 1；`60C2A0` 對 5–8 只有已知數值通知，沒有新增未證實的命名資源。

為跨回呼保存資料，frame `80h→90h`；新 local `+60h=remainingDense`、`+64h=entry ordinal`。原 12 處 RSP-relative save／local operands 的 offset 加 `10h`，sub/add 也一起改動，共 14 處 frame 修改。原 `+20h..50h` outgoing 參數及依 entry RAX 保存的位置保持；R15 的 `70h→80h` 和 R14 的 `78h→88h` 升級為 disp32。新 XMM6 slot `+70h` 仍為 16-byte 對齊。

完整重定位保留 62 個局部分支、45 個外部 RIP／直接呼叫，以及原兩個間接控制點。候選為 2262 bytes。新的 frame 與程式位址仍需正確 Windows unwind；可解碼並不代表已註冊 unwind。

## 建置與共同區域核對

[地址範例](verification/native_roster_departure_addresses_synthetic.json)是合成地址；[共同產物](verification/native_roster_departure_bundle_synthetic.json)保存十三函式、玩家數 patch 計畫、來源指紋、拒絕原因與 53 個已知區域。

在 workspace 根目錄執行，輸出須不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927/Native/roster_departure.py `
  --evidence five_player_feasibility_20260927/roster_departure_native_evidence.json `
  --getter-evidence five_player_feasibility_20260927/roster_getter_native_evidence.json `
  --classify-evidence five_player_feasibility_20260927/roster_classify_native_evidence.json `
  --remove-evidence five_player_feasibility_20260927/roster_remove_native_evidence.json `
  --insert-evidence five_player_feasibility_20260927/roster_insert_native_evidence.json `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --player-count-evidence five_player_feasibility_20260927/roster_player_count_native_evidence.json `
  --context-evidence five_player_feasibility_20260927/roster_departure_callee_evidence.json `
  --addresses eight_player_candidate_20260927/verification/native_roster_departure_addresses_synthetic.json `
  --output NEW-departure-bundle.json
```

Builder 拒絕來源指紋不同、地址／對齊不符、已知區域交疊或 rel32 不可達。新增 departure code／reject／getter／S／B 不得與固定整個遊戲映像交疊；共同建置另外核 count 跳板和原函式區域。它不配置地址，不處理所有未列入的 runtime 資源，也不應將產物當安裝器。

## 驗證狀態

[測試原始碼](tests/test_native_roster_departure.py)及[報告](verification/native_roster_departure_tests.json)含 7 組／43 次 top-level 指令執行：7 次原版完整 departure、16 次候選完整 departure、17 次候選入口拒絕，以及 1 次候選 remove 和 2 次 getter 串接。內層 helper 進入次數另外記錄，不重複加入總數。

- 原四格配對包含關聯物件 null、mode 分支、controller 拒絕、完整關聯處理、三個 primary 清理及 deferred 清理。
- 八格代表案例包含 ordinal 4–7 pending、pending D=0、ordinal7 prefix、另一個 image base 及 ordinal7 完整關聯分支。
- 實際執行保存的三個 primary helper，檢查各自三筆 registration 中只刪同 S／target ID，核補洞或延後清 pointer；實際執行 `FD9C80` 和 `FD9D40` 的已證有效路徑。
- 其他資源、關聯、queue、通知採逐個明示的 ABI／順序／出參契約替身。特別保留 `FD9D40` 的 ECX，及建立出參後的新 ID 方向，核全部 stack arguments、非 stack 頁的預期修改、nonvolatile GPR／XMM 與尾跳 RSP。
- 拒絕案例在首次外部呼叫與非 stack 寫入前停止；串接案例再執行真實 map-delete 與候選 mover，將第7格四组記錄搬到第4格，getter 仍讀回同一高位 network DWORD，被刪除 ID 返回 missing。
- 共同建置核十三函式與 count patch 計畫的身分、getter 目標及區域交疊。此處沒有重跑前十二個函式或 count-filter 套件。

輔助測試來源 `FD9D40` 的 178 bytes 與一個 float literal 另有[固定 aux 證據](../five_player_feasibility_20260927/roster_departure_aux_evidence.json)及[有限重播程式](../five_player_feasibility_20260927/roster_departure_aux_replay.py)。它們來自同一份既有 capture，沒有新增程序讀取。

重跑命令：

```powershell
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927/tests/test_native_roster_departure.py
```

[靜態審查](verification/native_roster_departure_review.zh-TW.md)及[測試 oracle 審查](verification/native_roster_departure_test_review.zh-TW.md)列出各自核對範圍。測試未覆蓋 primary owner list 清空後的實際配置器／backing 釋放、任意 miss、callback 重入／失敗或 rollback；各通知接收者是替身，未端到端執行 `94C9C0`。外層 `FDC820` 也沒有由此串接測試執行。

## 整合與成品仍缺

- 實際 caller 的 entry 契約、跨 callback 至真正移除的序列化／生命週期；重入、失敗及部分清理的恢復。
- 原資源、manager 與通知在真實資料的契約；實際配置失敗、清空後 backing 釋放及完整玩家數 context。
- 其他讀者、整理、所有八格元件的配置／發布／清理與 sidecar 生命週期。
- 拒絕 handler、hook、同步改碼／撤回、指令快取、unwind、載入版本檢查與可安裝封裝。
- 平台加入、額外原生角色、所有客戶端同步及五至八帳號任務全流程。

沒有新的遊戲程序操作、載入或安裝；完整八人目標保持未完成。
