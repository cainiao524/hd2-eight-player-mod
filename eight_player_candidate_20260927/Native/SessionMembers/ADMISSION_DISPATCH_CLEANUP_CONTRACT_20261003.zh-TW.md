# Admission／dispatcher／cleanup 靜態交叉契約（2026-10-03）

本契約只重播已保存的固定版本 `25480438` 反組譯資料，不啟動或存取遊戲程序，不呼叫函式、不寫入記憶體，也不安裝 hook。

## 已核對的連接

- Host admission 在 `0x108DDC7` 與 `0x108DE09` 仍是介面表 `+0x08`／`+0x50` 的間接呼叫，輸入為 `RCX=[network_context+0xB390]` 與 `RDX=[r12]`。
- 後續 host-to-client dispatcher 在 `0x108C8CB`、`0x108C8DE` 發送兩個事件 hash，接著設定 `r12d=4`，以 `0x38` bytes stride 迭代四筆。`RDI=session+0x40`，record id 來自 `[RDI-0x20]`，`[RDI]` 是 record `+0x20` 的 state 欄位；`cmp eax,5; jb` 跳過 state <5，`cmp eax,7; setae al` 產生 state >=7 的參數旗標。這不是 network index 5～7 的 gate，也沒有在此排除 state >=8。
- dispatcher 會呼叫 `0xBE4910`（confirmed-peer sender）及 `0xB90B20`（client confirmed-peer insert）。迴圈結束後呼叫 `0x135EA10`，再送出 `0x9BF86D8C`。
- `join_handler` 的另一個狀態探測是 `[object+0x50] -> [returned+0x28] -> call`，以 `EAX` 的小集合做狀態分支；這個形狀不能與 host admission 的 `[r8+0x50]` 直接視為同一個 target。
- `join_handler` 在 `0x108BFD7` 呼叫 `0x13EFF30` 後測試 `AL` 並分支，保存為 reject／cleanup 候選，尚未解析語義。

## 解讀限制

四次 dispatcher 迭代與 state >=5／>=7 的條件是實際反組譯形狀，但不足以證明 peer admission、第五至第八個玩家建立、客戶端 replication、離隊清理或 host migration 已成功。這次修正移除了先前把 state 欄位誤稱為 index gate 的標籤。兩個 host 間接 target 的實際位址、回傳 ABI 及 cleanup ABI 仍未解析。

收據由 `admission_dispatch_cleanup_contract_20261003.py` 產生，固定 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
