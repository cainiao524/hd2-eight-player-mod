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

## `0x10936E0` leaf reader 候選

已保存 `platform_member_leaf_reader_disasm_20261002.json` 的完整 118-byte body，以及對 `0x10936E0` 的 template-only 14-byte detour 候選。候選先讀八槽 sidecar 的 signed result，對非負結果轉成原 leaf 的布林值；sidecar 缺失、負結果或 callback 未解析時回到既有 owner/mode predicate。`platform_member_leaf_reader_patch_verification_20261002.json` 的靜態收據為 2/2，stub 為 89 bytes。

這個 leaf 候選仍不可安裝：resolver、mode callback、sidecar `+0x44` 的真實生命週期與 `0x10937A0` 的所有 count-driven reader/writer 尚未接到遊戲內 dispatcher。它只補齊相鄰四槽讀取的 ABI 證據，不代表遊戲程序已修改或多人已成功。

## `0x10937A0` state update exact evidence

`platform_member_state_update_disasm_20261002.json` 以同一份只讀 capture 完整解碼 `0x10937A0..0x10945D8`（3640 bytes、819 條指令、body SHA `929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69`）。它記錄三個外部 caller 的 `RCX` 子物件來源、四個相鄰 consumer call、71 個 owner 欄位 site 和 14 個立即數 `4` site，並保存 stack cookie、unwind 需要的非揮發暫存器和 callback 分支。

`PLATFORM_MEMBER_STATE_UPDATE_20261002.zh-TW.md` 說明為何不能把這個 3640-byte state machine 當作 leaf 直接 detour。它目前只有 exact captured evidence；`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。驗證腳本和 2/2 測試只證明擷取內容與 ABI inventory 一致，不代表已修改遊戲或完成多人聯機。

## 尚未可安裝

這是原生資料流候選，不是可用 Mod。resolver／consumer 的遊戲內身份與完整 ABI 尚未找到，`0x1093590` 及其他平台成員 reader/writer、client confirmed-peer、角色建立、hook／unwind、owner lifetime、服務端接受和真人多人驗收仍未閉合。此目錄沒有存取或修改遊戲程序，也不會把合成執行結果標記為多人成功。
