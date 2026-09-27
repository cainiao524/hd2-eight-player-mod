# 原生候選：名冊屬性產生端與接收端共用八格儲存

## 目前可交付的行為

候選 `0.5.0-offline` 加入 [roster_producer.py](Native/roster_producer.py)，產生 662-byte x64 程式；[roster_property_pair.py](Native/roster_property_pair.py) 同時建置它與既有 375-byte receiver，強制使用相同的 roster 物件 S 與 property 儲存 B。B 的容量是 `8×20h=100h` bytes，每格是一名 entity 的八個 DWORD。

產生端保留原本的 entity→ordinal 查表、32-byte buffer 配置、八個 property descriptors、初始值、network index 查詢及正常返回。接收端保留 payload 讀取順序與 cursor 推進。兩者改接同一 B，因此完成了一組可共同測試的原生資料讀寫候選。

**這仍不是可安裝的八人 Mod。** Pair builder 只輸出 bytes 與契約，沒有配置或初始化遊戲儲存、安裝 hook、實作拒絕處理或登錄 Windows unwind。插入、搬移、分類、移除及其他讀者必須共同完成改接，才能啟用。完整目標仍需八帳號同任務與生命週期驗收。

## 來源與地址改接

固定目標為 Windows x64 build `25480438`；EXE／game.dll 指紋見 [manifest](candidate-manifest.json)。這是保存來源的版本，不是多人相容性聲明。

產生端完整原函式 `[60C640,60C882)` 共 578 bytes／130 條指令。`60C77D` 僅是函式內 network index 欄位的寫入點。保存 evidence SHA-256 為 `f73ec903d06f2304f4f944c25e011a7ef86d78737cb1b197101a1c96daaabacb`，原 body SHA-256 為 `8b9a20e5207ae395e99e45f153cba1994ff50c10cb258101fd16a74285824c34`；詳見[完整切點及 ABI 證據](../five_player_feasibility_20260927/roster_property_producer_native_findings.zh-TW.md)。

- 產生端從 global `game_base+3326468` 取得 S，入口 RCX 不是選取 S 的來源。接收端則從入口 RCX 取得 S。
- 產生端在 `60C6C9` 的五 bytes 切點，於 allocator 呼叫及所有 output／property 寫入前檢查 ordinal `<8` 與 S 綁定。成功時偏置 RBP，使八個 property stores 指向 B；第七欄的衍生地址也包含在內。
- 兩個 RIP 讀取與兩個外部 call 均重新計算 rel32；原內部指令位置與跳轉保留。搬移後仍呼叫原 allocator `173B8D0` 與 index helper `134F190`。
- 全部地址必須明確提供，遵守各 emitter 的對齊、low canonical 及相對距離檢查。來源 bytes 或證據指紋不符即拒絕產生。

## 共同建置與拒絕入口

Pair builder 只有一組 `game_base`、`roster_address`、`property_address` 參數，不能為兩端分別傳入不同 S 或 B。它檢查兩份候選程式、兩個拒絕入口、原函式、S/B、已知 globals 與 helper 範圍是否交疊。

這是**有限已知範圍**核對，並非完整程序的配置圖：allocator 只保護已知入口一 byte，reject handler 也只保護入口一 byte；它們的整個長度、有效權限、當前配置、物件世代及同步仍須整合層驗證。

兩端必須提供不同的拒絕入口，因為同樣的 reason ID 對應不同的內部 frame：

| 拒絕時狀態 | Producer | Receiver |
|---|---|---|
| R10D | 1：ordinal 超界；2：global roster 不符 | 1：ordinal 超界；2：輸入 roster 不符 |
| RSP | 入口 RSP−38h | 入口 RSP−8 |
| 原 ordinal | RBX 中的 uint32 值 | R8 為 uint32 ordinal×32 |
| 原 S | RBP | R11 |
| RAX | reason 1 為 entity ID；reason 2 為預期 S | reason 1 為 ordinal；reason 2 為預期 S |
| 已有副作用 | prologue stack 保存與 entity/global/map 讀取 | prologue stack 保存與 map/cursor 讀取 |
| 尚未發生 | allocator 呼叫、buffer／descriptor／count／property 寫入 | payload 欄位讀取、property／cursor 寫入 |

兩個入口都必須正確恢復各自 frame 並終止上層完整操作。不能直接 `ret` 或略過資料後假裝成功。Guard 都在查表之後，無效輸入指標可能在到達 guard 前出錯。有效 map、足夠輸出容量、來源／目的不別名、allocator 成功與資源生命週期仍是必要前提。

## 驗證與實際涵蓋範圍

[Producer 測試](tests/test_native_roster_producer.py) 由主代理獨立於 emitter 作者實作，10 組測試／54 次隔離 x64 執行通過：

- 兩組 ASLR 地址、全部八個 ordinal、與 ordinal 不同的 network index，逐一對照原指令與候選。
- 實際執行保存的 `134F190` leaf，測到命中、查無本機 peer、空表及完整 32-bit 返回值。所用 peer 資料為合成配置，沒有證明原 client 支援八人。
- Allocator 採明確契約 hook：檢查物件、size 32、alignment 4 及 stack 對齊，破壞 Win64 volatile GPR／XMM，回傳已映射的合成 buffer。沒有執行真實 allocator、配置失敗、回收或資源所有權。
- 比對全部已映射非 stack pages，只允許預期 record、buffer、descriptors、count 的變更；另核對逐筆寫入順序、非揮發暫存器與 RSP。
- 查表碰撞／回繞、sentinel／miss、ordinal 超界、global roster 不符及 rel32 可達邊界。
- 從 producer 的八個 descriptor pointers 按原順序取得資料，再交給實際 receiver 指令；測同 S 與另一個 S/B、ordinal 7→2、network index 4 不變。**這是資料格式橋，未執行遊戲 serializer、網路傳輸或遠端客戶端。**

[Pair 建置測試](tests/test_native_roster_pair.py) 另有 4 組，核對共用綁定、與個別 emitter 的 byte artifact 相同、跨程式／reject／原碼／global 碰撞，以及來源拒絕。這四組只執行 Python bytes 建置，不另計 x64 執行次數。

完整結果見 [producer 報告](verification/native_roster_producer_tests.json)、[pair 報告](verification/native_roster_pair_tests.json)與[審查紀錄](verification/native_roster_producer_review.zh-TW.md)。既有 receiver 的 11 組／52 次執行來源未變；全套候選現有 79 組測試，106 次 x64 執行屬於兩個原生套件內的案例，不再加到組數。

## 產生離線範例

所有下列地址都是合成例子，不能直接用於遊戲。從工作區根目錄執行，output 必須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/Native/roster_property_pair.py --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json --game-base 0x7FF800000000 --roster-address 0x20000000 --property-address 0x30000000 --producer-code-address 0x7FF805000000 --receiver-code-address 0x7FF805001000 --producer-reject-address 0x7FF805010000 --receiver-reject-address 0x7FF805011000 --output eight_player_candidate_20260927/verification/native_roster_pair_synthetic.json
```

已保存[合成範例](verification/native_roster_pair_synthetic.json)。現有 `.native-test-deps` 與[固定依賴](requirements-native-tests.txt)足以重現新測試：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_producer.py
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_pair.py
```

## 下一個原生實作關口

[有限 consumer 清單](../five_player_feasibility_20260927/roster_property_consumers_native_findings.zh-TW.md)已將已證來源整理成具體改接位置。下一個最小完整局部為 `60C410` 搬移函式；它在 property copy 前已修改其他三組平行陣列，之後修正 entity map。因此 guard 必須在首次變更前，不能只在 property copy 處拒絕，也不能永久偏置仍供其他陣列／map 使用的 RBX。

完整八格 roster 還需其他平行陣列、插入 guard、分類交換、移除、讀者與儲存生命週期共同完成。此 pair 已使兩段候選採用一致的資料來源與目的地，沒有解除平台加入、第五人角色建立及多人實測的缺口。
