# Roster receiver 原生候選：審查與執行範圍

## 獨立靜態審查

`web_research` 代理以固定 receiver 的 72 條原指令、Capstone 與產生的 bytes 核對：

- 原 303-byte body 保留，只改唯一 RIP displacement 與 C932 的 6-byte 切點。
- 原八個內部跳轉的目的地與指令邊界保持一致。
- 外部 RIP 讀取仍指向 `game_base+3483C20`。
- Trampoline 先拒絕超界 ordinal，再檢查 roster binding；沒有舊四格資料的 fallback。
- 成功路徑的 RAX 暫存會被原第一個 payload load 覆寫，R11 改接目的地，R10 成功時保持原值；沒有新增 stack 操作或 calls。
- 原兩條指令重播後回 C938，八個 stores 與正常 epilogue 保留。

未發現局部機器碼缺陷。審查提醒 binding reject 時 RAX 已是 expected roster 地址，不能當通用 ordinal；此契約已加入產生器與文件，機器碼產生邏輯未因該文案補充改變。

## 獨立 x64 執行測試

另一代理 `singleton_review` 撰寫 [Unicorn 測試](../tests/test_native_roster_receiver.py)，獨立重建原 body 並與候選實際指令執行對照。**11 組測試、52 次 x64 模擬執行通過，零 failures／errors**。

涵蓋兩組高位 ASLR、全部八個 ordinal、與 ordinal 不同的 network index、非零 cursor、完整 DWORD 保留、八格 hash collision 回繞、空／滿表 miss、sentinel、超界 ordinal、可讀但不匹配的 roster、所有 nonvolatile registers 與 RSP。比對全部已映射非 stack pages，限制變更為目的 record 與 cursor；另在可接受兩端 RIP／reject rel32 邊界實際執行到 return 或 reject。

主代理逐讀產生器、生成的 trampoline 解碼及測試程式，核對報告與檔案指紋。測試沒有呼叫遊戲或將原始指令作為主機函式執行。

| 檔案 | SHA-256 |
|---|---|
| Native/roster_receiver.py | `38b163fe9a0fda32db609ee94f96ab257105221e60e28ad14c4bd14676e61a27` |
| tests/test_native_roster_receiver.py | `6c9a4165696e0c3af43894a46cb9b328ee7a67c457771b1341047399ef11e4be` |
| verification/native_roster_receiver_tests.json | `752cc87e8f464750b007978418189a9ef570f16bd5411bab4a05b27a6404d2da` |

## 不能從測試推出的結果

- 原版 ordinal 4–7 的比較使用刻意加大的合成 inline storage，沒有證明遊戲原四格區域可容納八份。
- Binding guard 在原查表之後，沒有保護任意壞 roster／map／cursor pointer 的能力。
- Reject 測試停在指定 continuation，原 RBP／R14 frame 仍需整合者處理；沒有實作或驗證 caller abort／cursor 恢復。
- 沒有驗證 Windows chained unwind、例外展開、code／sidecar 配置、存活、引擎同步、hook 安裝／移除或其他讀寫者。
- 沒有多人遊戲結果。此候選的 `installable=false`、`game_execution=false` 保留。

本局部停止條件已達成；下一步是其他 roster 存取及原生整合契約，不因更多同型合成案例而宣稱完整八人補丁完成。
