# `605950` 原生候選測試的獨立 oracle 審查

## 審查範圍與固定版本

唯讀審查 [`test_native_roster_departure.py`](../tests/test_native_roster_departure.py) 和 [`native_roster_departure_tests.json`](native_roster_departure_tests.json) 的 fixture、預期值、實際執行入口、斷言與報告口徑，並對照固定 [`roster_departure_native_evidence.json`](../../five_player_feasibility_20260927/roster_departure_native_evidence.json) 中 `605950` 的分支及 [`roster_departure.py`](../Native/roster_departure.py) 的候選契約。未重跑舊套件、重新擷取、執行遊戲或修改候選 source。

| 檔案 | SHA-256 |
| --- | --- |
| `tests/test_native_roster_departure.py` | `f0d5a90b52a613799c33a987859717bf2c381cf20f27dd53b1a73d68345b25f0` |
| `verification/native_roster_departure_tests.json` | `ee4c092341b2d6dccf59ec9df29e878d5ed39697dbfcc29cf5b629a28892e3ff` |
| `Native/roster_departure.py` | `a0d9a350254955a840a6039795eb42b89ea8f48e86c3ce00b921e3b1c6f165ba` |

報告記錄 7 個 method、43 次頂層 x64 Unicorn 執行，0 failure/error；其中 7 次原四格 departure 基準、16 次候選完整 departure 返回、17 次候選 preflight 拒絕、1 次候選 remove 串接、2 次候選 getter 串接。真正從 departure 內呼叫的候選 getter 為 16 次；另兩次 getter 是獨立頂層執行，報告已分開計數。這是測試報告的結果，不是多人或遊戲執行數。

## 原控制流與 oracle 的對照

| 原控制流／副作用 | 審查到的實際驗證 | 邊界 |
| --- | --- | --- |
| `605B96→605BC9` 可先發 `disconnected` | prefix 指標 bit 0 與 global 開關的案例驗固定字串、R8B=1、R9D=0，以及它早於 network／primary 事件 | `13462C0` 是受控 callback，未發真通知 |
| `6059EE` network reader；`605A0D→605A2E/A42/A56` 三個 primary helper | 原版執行完整 `606820`，候選執行真正 getter；三個 primary helper 執行保存機器碼並驗 resource、原 S、ID、順序，以及 24-byte owner/ID 清單的即時尾筆替換或延遲 owner 清零 | 僅非空清單；allocator／清空後釋放路徑未覆蓋 |
| `605A5B→605A68` 關聯 ID 與 `FD9C80`；mode 4 長支線 | `FD9C80` 的 `7FFFh` 直接 null 與有效命中皆跑保存碼；完整長支線另跑保存 `FD9D40`。controller、query true/false、controller false、associated flag false、mode 3 路徑分列。間接 vtable 與 record/link/output 呼叫核參數、順序、shadow space | controller、record 操作、輸出建立等為明示成功／失敗替身；不能據此推定真資源可用 |
| `605DC6/605E17` 關聯與 manager loop | fixture 有同一關聯、null、bit 0 關、類型不符及一個合格項；驗兩個 queue ID 的條件及次序 | `FDC310` 為替身，沒有實際 queue/event 或重入效果 |
| `605E65..605EDE` tag 3E、mode 4 才呼叫 UI；`605EFA` count；`605F28` tail | 三筆 registry 包含兩筆 tag 3E；有無 UI 與 mode 3 分支均測。兩個 UI 的 stack count、`60C2A0` EDX 均獨立按 fixture 算 `D−(ordinal<D)`；tail 驗原未減的 pre-remove D。原四格基準則按原 `D−1` 配對 | `94C9C0`、`60C2A0` 和 tail 是受控通知替身；本測試沒有執行完整 count consumer／驗資產 |

`success()` 除事件順序外，還按六個改接位置檢查實際讀取地址與寬度、候選不讀原 inline 陣列、所有非 stack 頁面僅出現預期的真 primary 清單修改，並檢查非揮發 GPR/XMM 與返回 RSP。替身在檢查 Win64 入口對齊與參數後覆寫 32-byte shadow space、污染易失 GPR/XMM，故不會因保留呼叫前易失值而假通過。預期值由 fixture 的 T/D/P/ordinal、旗標與固定 ID 建立，不由候選輸出回填。

15 個不同失敗狀態及 2 個 rel32 邊界執行到 reject；斷言 reason、原入口參數與 nonvolatile 狀態、無外部事件、無非 stack 寫入。單一合成串接先跑 pending departure，再跑候選 remove、保存 map-delete 與候選 mover，核四組完整紀錄、map 雙射／可 probe、D 不減；最後用真正候選 getter 證移至 slot 4 的 ID／network index 可讀、已刪 ID 返回 missing。外層 `FDC820` 沒有在串接中執行。

## 結論與適用界限

對這份**有限、固定版本**測試，未發現會令候選局部改接、計數預測或原 helper 順序錯誤仍被 oracle 判通過的具體缺陷。初版 nested getter metadata 曾將兩次頂層 getter 納入巢狀數，最終版已分開為 16 次巢狀 getter；43 次頂層總數未變。

此結論依賴 fixture 提供的 S/B、map、partition、entity 與 callback 期間狀態不變。測試沒有證明真實回呼不改 S、ordinal 或 counts，也沒有驗證 primary 清單清空後釋放、任意關聯資料、真 manager queue、通知資產、完整 `94C9C0` 或 `60C2A0` 的行為。`D_post` 是新增候選通知政策；`D_post=0` 時 v0.11 的 UI consumer 仍把 0 夾成 1。候選尚未安裝，也沒有真實遊戲或八人任務驗證。
