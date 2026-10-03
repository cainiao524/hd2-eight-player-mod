# Platform Session Members：八槽候選

這個目錄把固定 Steam build `25480438` 的平台成員列舉函式 `game.dll+0x1092E60` 做成一個可執行的離線候選。原函式將成員 ID 寫入 `owner+0x1B58`，並以 `4` 作為平台 API 的容量；該陣列後方的 `+0x1B78`、`+0x1B7C` 和 `+0x1B80` 已由既有證據確認仍在使用，所以把常數改成 `8` 會破壞控制欄位。

候選把兩條列舉路徑的目的地移到八槽 sidecar，保留原平台方法的參數順序。真正平台方法仍可回傳最多八筆，true path 另外逐 index 取出 ID。原先 `0x1093590` 會讀四槽 inline 陣列，候選改用兩個明示的外部 ABI：

- resolver：`RCX=owner`，`RAX=sidecar`；回傳零時拒絕。
- consumer：`RCX=owner`、`RDX=sidecar`、`R8D=count`，以 `EAX` 回傳 signed status。

`test_session_members.py` 使用 Unicorn 實際執行保存的原函式 bytes 與候選 machine code，涵蓋原版 0–4、候選 0–8 及 9 的安全上限，並涵蓋 captured true/alternate 兩條平台路徑。`verify_session_members.py` 將結果保存到 `session_members_verification_20261002.json`。

## 已恢復的 `0x1093590` consumer ABI

固定 build 的 `0x1093590` 已由保存的 335 bytes 還原出可審查的呼叫契約：Windows x64 下 `RCX=owner/platform state`，`EAX` 是 signed status。當 owner 沒有 platform object 時，函式回傳 mode predicate；owner 有 object 但 `owner+0x1ba6` 尚未 ready 時回傳 `-1`。掃描成員時，`owner+0x1b58+8*i` 是 ID，`owner+0x1bb0` 是 count；`r15d` 從 1 開始，只在非本機 ID 的平台查找回傳 non-null token 後增加，所以必須恰好有一個本機 ID，其他 ID 才能完成 `0x20bde78` 的零狀態檢查。

`platform_member_consumer.py` 將同一個 predicate 接到八槽 sidecar，`platform_member_consumer_abi_20261002.json` 保存入口、欄位、依賴、caller 和固定 build body SHA，測試涵蓋 8 個 ID、缺失本機 ID、重複本機 ID、lookup 失敗和第 9 槽拒絕。這解決了 consumer 的資料語義，但沒有猜測遊戲內 resolver 的身份；仍需把 sidecar resolver 綁到真實 owner lifetime，並完成可回滾 hook 和真人多人驗收。

`platform_member_consumer_verification_20261002.json` 保存這 7 項模型測試、來源雜湊與 production gate；它是 ABI review receipt，不是實機多人成功證明。

`platform_member_consumer_patch_candidate_20261002.json` 則是 consumer 的 template-only 14-byte detour／270-byte stub，`adjacent_member_abi_20261002.json` 保存 `0x1092E60`、`0x10936E0` 和 `0x10937A0` 的相鄰讀寫關係。這些資料用來阻止只替換 consumer 而留下四槽 caller；沒有任何 template callback 地址可直接安裝。

### 2026-10-03 bound candidate 與 unwind 修正

新增 `bind_candidate()`，將已核對的 body 轉成由呼叫者提供地址的可重定位 bytes。它會拒絕未解析 sentinel、非 canonical／未對齊地址、callback alias、image／stub／unwind 重疊與 `RUNTIME_FUNCTION` 相對位移溢出；它只輸出 detour、stub、unwind 和 callback contract，不分配記憶體、不改寫遊戲、不註冊 hook。

`test_consumer_bound_execution.py` 以合成 callback 實際執行產物，涵蓋原四人與 5–8 人 count、失敗回滾、移動後的 code address、callback 破壞 volatile registers，以及全部 prologue 邊界的 Windows x64 unwind 重建。測試共 4 項通過，收據見 `consumer_bound_execution_20261003.json`。

這次也修正了先前 unwind metadata 的實際錯誤：序言長度是 16 bytes，而不是 17；`UWOP_PUSH_NONVOL` 的 `OpInfo` 現在使用正確的高半位元組編碼。這只使離線 native bridge 候選可被正確審查，不能把合成 callback 當成 HD2 的真實 resolver 或八人聯機成功。

## `0x10936E0` leaf reader 候選

已保存 `platform_member_leaf_reader_disasm_20261002.json` 的完整 118-byte body，以及對 `0x10936E0` 的 template-only 14-byte detour 候選。候選先讀八槽 sidecar 的 signed result，對非負結果轉成原 leaf 的布林值；sidecar 缺失、負結果或 callback 未解析時回到既有 owner/mode predicate。`platform_member_leaf_reader_patch_verification_20261002.json` 的靜態收據為 2/2，stub 為 89 bytes。

這個 leaf 候選仍不可安裝：resolver、mode callback、sidecar `+0x44` 的真實生命週期與 `0x10937A0` 的所有 count-driven reader/writer 尚未接到遊戲內 dispatcher。它只補齊相鄰四槽讀取的 ABI 證據，不代表遊戲程序已修改或多人已成功。

## `0x10937A0` state update exact evidence

`platform_member_state_update_disasm_20261002.json` 以同一份只讀 capture 完整解碼 `0x10937A0..0x10945D8`（3640 bytes、819 條指令、body SHA `929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69`）。它記錄三個外部 caller 的 `RCX` 子物件來源、四個相鄰 consumer call、71 個 owner 欄位 site 和 14 個立即數 `4` site，並保存 stack cookie、unwind 需要的非揮發暫存器和 callback 分支。

`PLATFORM_MEMBER_STATE_UPDATE_20261002.zh-TW.md` 說明為何不能把這個 3640-byte state machine 當作 leaf 直接 detour。它目前只有 exact captured evidence；`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。驗證腳本和 2/2 測試只證明擷取內容與 ABI inventory 一致，不代表已修改遊戲或完成多人聯機。

## 尚未可安裝

這是原生資料流候選，不是可用 Mod。resolver／consumer 的遊戲內身份與完整 ABI 尚未找到，`0x1093590` 及其他平台成員 reader/writer、client confirmed-peer、角色建立、hook／unwind、owner lifetime、服務端接受和真人多人驗收仍未閉合。此目錄沒有存取或修改遊戲程序，也不會把合成執行結果標記為多人成功。

## Confirmed-peer 外部鏈 exact evidence（2026-10-02）

`confirmed_peer_external_chain_20261002.json` 將 host capacity `0x108C18F`、host index allocator `0x108C3D8`、host sender `0x108C760`、client append `0xB90B20` 和 player creation gate `0x1086460` 綁定到固定 build 的只讀 capture，並列出 host cleanup、host migration、client remove/reset 四條必須同時閉合的生命週期。`CONFIRMED_PEER_EXTERNAL_CHAIN_20261002.zh-TW.md` 說明第五筆 client record 會從 `+0x150` 開始、與鄰接 live 欄位衝突，因此 sender-only 或單改 capacity 不能成為八槽 patch。

`verify_confirmed_peer_external_chain.py` 與 `test_confirmed_peer_external_chain.py` 的結果為 5 個 site、2/2 tests；所有旗標保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
## 2026-10-03 原生 consumer executor 候選

新增 `ep_consumer_executor.h/.cpp` 與 `build_consumer_executor_x64.bat`，該腳本同時產生可載入 DLL `ep_consumer_executor.dll` 與合成測試執行檔；把固定 build `25480438` 的 `0x1093590` consumer 候選收束成可回滾的 Windows x64 原生安裝器：先驗證 14-byte 原始入口，再配置 270-byte full-replacement stub 與 24-byte unwind，註冊 `RUNTIME_FUNCTION`，最後寫入 FF25 絕對跳轉；移除時只接受自己擁有的 detour 並恢復原始 bytes。安裝器要求五個非空 callback，呼叫者必須負責 thread quiescence 與 callback／owner lifetime。

`ep_consumer_executor_test.exe` 在合成 module 上通過 4 人相容、5--8 人 count、count 9 拒絕、缺 callback 拒絕、入口 fingerprint 改變拒絕及 install/remove 原始 bytes 恢復；收據見 `consumer_executor_receipt_20261003.json`。 `ep_consumer_executor_load_test.exe` 另外通過 DLL `LoadLibrary`、五個 export 與 build/size getter 檢查。這是可審查的離線 executor，不是 HD2 callback 綁定：沒有注入或改寫遊戲程序，`production_executable=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。

