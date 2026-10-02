# 6054F0 狀態更新：測試 oracle 接續審查

2026-09-28 接續時重新讀取測試、builder、固定原 body 的完整解碼及保存報告，補上暫停時尚未落檔的審查。本文件記錄本次實際核對，不代稱先前代理的口頭審查。未修改候選或測試來源；在既有 Python 3.12.10、Unicorn 2.1.4、Capstone 5.0.7 環境只重跑本套五個方法，42 筆頂層執行紀錄與凍結報告的 `emulator_runs` 完全相同。其他舊套件未重跑，凍結報告未覆寫。

## 結論及指紋

有限範圍內未發現阻止離線候選交付的 oracle 缺陷。測試預期欄位和控制條件與原指令吻合，沒有以 builder 的輸出值反推記憶體預期結果。合成環境中的有效路徑及拒絕測試足以支持本次局部改接；不構成任意輸入安全、引擎整合或多人成功的證據。

| 檔案 | SHA-256 |
|---|---|
| `Native/roster_arrival.py` | `2744e367accb26d022807984b8a573d95cc6e9ec15c011c5b403ee187e030771` |
| `tests/test_native_roster_arrival.py` | `b865db68403103fc23509de9c36fda9db06c50095740ac7244006d8f3c8fd90f` |
| [凍結報告](native_roster_arrival_tests.json) | `3c9d4921951bc6ae2777c0b02f682b36df44853d89c6d58c79fcd2d3e94530ad` |
| [原指令 evidence](../../five_player_feasibility_20260927/roster_arrival_native_evidence.json) | `c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64` |

## 預期值與指令的對應

- 原 `605599` 的 caller 首 byte 控制 primary/property/publish/dirty 副作用；`6055AD/6055C3` 的 eligibility/entity bit 控制 bit11 設定。測試將這些條件與 P 分開，沒有假設 ordinal、network index、prefix 分類相等。
- Primary 的 1、5、8 分別來自 active 為 null/相等、D 範圍全部合格、第一個其他不合格記錄。測試包含第七格 blocker、D=0、pending target `n>=D` 及原四格對照；原 D 迴圈逐格 pointer 讀取另依 RIP 檢查。
- Aux 的 `+8` DWORD 7FFF、`+14` 單 byte 反轉 property bit0、`+20` 非預設 missing sentinel，以及 `+0` 關聯指標均獨立建構預期 bytes。`6056F0→605707` 的 flags 決定先寫 state3，mode4 匹配紀錄可再覆寫 state1；測試同時核最終 bytes 與兩次 store 的順序。
- `605760` 讀完整 network DWORD。0..3 讀固定 palette 的後三個 float，4..7 及 FFFFFFFF 使用原 1.0×255 fallback；實際 SSE 結果與 palette 讀取範圍均檢查。這不證明額外玩家具備獨立顏色。
- UI 呼叫的參數在 callee-entry stack 偏移多 8 bytes，測試的 +28/+30/+38/+40 正確對應 caller +20/+28/+30/+38。兩次 UI、count helper、player_count event 均核當時 D；沒有加入離隊預測公式或 T/D/P 遞增。
- 所有非 stack 映射頁與獨立預期變更比對，並逐筆限制原生 store 的位址及寬度。其他記錄、map、counts、舊 inline 陣列及 canary 保持。Stack 另核 RSP、nonvolatile GPR/XMM 與 cookie 參數，不聲稱逐 byte 核整個 stack。

## 覆蓋與計數

五個 unittest 方法共 42 次頂層模擬：原版完整返回 4、候選完整返回 21、候選拒絕 17。候選拒絕包含 15 種 fixture 與 2 個 rel32 邊界。巢狀原 FD9AF0 共 25 次，不加到 42；重跑也不再加到套件案例總數。

19 個改接位點由測試內獨立地址集合固定。17 個有效域可達位點有條件、地址與存取寬度檢查；兩個 LEA 另核執行條件及後續遍歷。6056C8/6056D6 的 invalid-ordinal 路徑被入口 guard 排除，只保留靜態覆蓋。動態 RIP 分組使用 builder 的 address map，故不能以此單獨證明 relocation 正確；另由[已保存的 source 審查](native_roster_arrival_review.zh-TW.md)核原指令、實際 emitted bytes 與全部 CFG/外部 relocation。

四次原四格基準與候選配對比較四組資料及 RGB，其他案例對照獨立預期變更。第二個 ASLR 基址、拒絕原因碼、entry 參數恢復、null caller、map miss/full miss、ordinal 越界、pointer binding 與已知區域碰撞均有有限檢查。沒有窮舉全部輸入、任意 map 破壞或全部 flags 組合。

## 真實指令與替身的界限

FD9AF0 執行保存的 174-byte 原指令，但只提供有效命中的 context map，返回 1234 或 7FFF；未測其零容量、full miss、sentinel 入口等路徑。兩個關聯介面、palette callback、94C9C0、60C2A0、player_count event 與 cookie helper 均為明示替身。它們檢參數、stack 對齊及 shadow space，覆寫 volatile GPR/XMM，保留 nonvolatile 與共享狀態；未執行真實資源、回呼重入、排程、失敗復原或 cookie 安全實作。

共同 bundle 核 16 個 roster 函式、既有 player_count 計畫、62 個已知區域與固定 sample 相同；這些組合檢查不代表其他函式套件本輪重新執行。仍缺 sidecar 配置／發布／清理、完整 caller/reader 集合、同步、hook、reject handler、Windows unwind、遊戲執行及五至八帳號任務驗收。
