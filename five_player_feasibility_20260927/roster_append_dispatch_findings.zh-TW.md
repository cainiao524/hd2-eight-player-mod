# `540850` 第一張 callback 表：有界讀者與壓實順序核對

此輪只讀固定 `existing-code-evidence-25480438` 擷取，並重用已存的 callback 登錄、fieldscan、dispatch、壓實證據。沒有操作 live 程序、產生 emitter、修改候選或重新做全程式 xref。`roster_append_dispatch_replay.py` 固定來源 SHA 與下列原始指令／片段；正式 evidence、recheck 及獨立以 Python 3.12 重跑的 review recheck 逐位元一致，SHA-256 均為 `b5b09a88cbfb09b2244cec5280c704abbd218b5f4985886f3721ef19fd3eaa42`。

## 已證註冊，尚未證第一張表呼叫

`55BFC2 488d058748feff` 產生 `540850` 的地址；`55BFC9 48898168bef000` 將其寫入 `owner+F0BE68`。算式 `F0B6F0+239×8=F0BE68`，故 **component index 239 在第一張 `F0B6F0` 表被註冊為 `540850`**。這是固定 initializer 的寫入，不是執行期 table value 或回呼命中紀錄。

先前 `spawn_callback_registration_first_phase_fields.json` 對 `F0B6F0` 與原 context 視角的 `F0B730` 均記錄 `references=[]`，各有一個 unwind 外 raw match；目前沒有通過指令邊界驗證的第一張表讀者。另一次限定 `F0B6D0..F0B730` 位移核對只找到前方 constructor／atomic 欄位與 initializer 寫入，沒有建立 table dispatch。這些負面結果受精確編碼位移、unwind 覆蓋及固定 capture 限制；**不能推論第一張表從未被讀取**。經計算的地址、無 unwind leaf 讀者或未擷取程式仍可能存在。

## 已知第二張表的建立路徑

同一 initializer 於 `55BFD0/55BFD7` 將 `540920` 寫入 `owner+F0C888`，即第二張表 `F0C110+239×8`。已證的 `FDC140..FDC309` 在 `FDC250` 傳 `RCX=context+40=owner`，`FDC254` 傳 creation params，`FDC257` 傳新 entity record，`FDC25A` 呼叫 `581320`。該已知 dispatch root 的六段 unwind fragment 覆蓋 `581320..58177E`；`58140A` 從 resource metadata 取 16-bit component index，`58140E` 讀 `owner+F0C110+index×8`，`581416/419` 在 callback 為零時跳過，`58141B/41E/421` 以 `RCX=entity record`、`RDX=creation params` 執行間接 call。若當前 resource 清單包含 239，且 table 保留初始化結果，這條路徑會選到 `540920`。既有參考 player 資源清單包含 239；此檔案結果不等於 live resource 或 callback 值已驗證。

在這條建立路徑，`FDC140` 先生成 record 與 creation flag，然後 call `581320`；後續 `FDC275` 在 handle 非 `7FFFh` 時插 handle map，`FDC29B` 的 apply 還要求 params[0] 為零，最後 `FDC2B1` 呼叫 `581780`。這是**第二張表**的相對順序，不能套到尚未找到 reader 的 `F0B6F0→540850`。

## `60CC70` 的已知更新鏈與生命週期邊界

完整 `FDC780..FDC81F` 為 159 bytes，SHA-256 `61bda56a4260158aeff7b3bc5ab3dbb6fb8ad639187ec11d964773eec2f63400`。它可先視 `[context+8]` 呼叫另一 helper，但 `FDC7A3` 一定形成 `RCX=context+40`，`FDC7A7` 無條件呼叫 `576CF0`；後者把 owner 保存到 RBX，`57E00F` 形成 `S=owner+EA0818`，`57E01C` 直接 call `60CC70`。因此壓實有明確的 owner 更新路徑。`108AE23..108AE36` 的有限 caller 在 global `346BF98` 非零時呼叫 `FDC780`；另一保存 caller 片段在 `AB5137/513E` 以 `R14+E49F0` 呼叫它，並於 `AB5143/5151` 隨後讀 roster global `3326468` 的 dense `+84h`。後置讀取不是對壓實前 `P/D/T` 的 guard。

上述建立路徑與更新鏈使用同一個 owner/context 型別，roster 指標也有既有 global 發布鏈。但這些有限 caller **沒有**給出 `540850` 的實際間接 call，也沒有在同一條有界控制流中固定「第一張表 append → 第二張表建立 → `FDC780` 壓實」的完整順序。保存的 `AB5054..AB62D6` caller fragment 有多個 `FDC780` 呼叫，未見直接 `FDC140/581320/540850/540920` 呼叫；這只約束該 fragment 的直接邊，未檢查不透明 callee 或別處回呼。故不能用這些片段證明 `P<D` 在 compact 時可達或不可達，也不能拿舊四槽反例冒充 runtime 觀察。

## 決定與重開條件

目前可固定：`540850` 被登錄於 component 239 的第一張表、`540920` 在已知建立路徑由第二張表條件分派、`60CC70` 在 `FDC780→576CF0` 更新鏈被直接呼叫。**缺口是第一張表真正的讀取／間接呼叫位置及其上層 caller 對同一 roster 的 P/D/T 時序契約。**在找到具體 computed-table 來源或取得新的保存資料前，不再重開泛式全程式掃描，也不據此製作聲稱保留所有 tracked unique entity 的八槽壓實 emitter。原 `60CC70` 在 `P<D` 的靜態反例仍成立，是否可在遊戲生命週期發生仍未證。

重跑方法：用同一固定 capture 目錄作 `--evidence`，以尚不存在的路徑分別輸出 `roster_append_dispatch_evidence.json` 及 `_recheck.json`。JSON 保存原始 bytes、有限 slice、完整 `FDC780` body、既有第一張 fieldscan 結果及來源 SHA；不把 `references=[]` 擴大為全 code 無 reader 的證明。
