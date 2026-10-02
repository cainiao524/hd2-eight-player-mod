# Confirmed-peer receiver binding 邊界（固定版 25480438）

本輪新增離線 verifier：`verify_receiver_binding_boundary_20261002.py`，以及其輸出 `receiver_binding_boundary_verification_20261002.json`。Verifier 只讀既有固定 capture 與保存的 disassembly，不執行遊戲函式、不寫入程序、不安裝或注入 Mod。

## 已機器核對的程式碼關係

- `0xBE4910` 內嵌事件 hash `0x4804FCF4`。
- `0xBABA80` 逐項解碼 descriptor 的 `+8/+0x18/+0x28/+0x38/+0x48` 欄位，呼叫 `0xB90B20`。
- `0xB90B20` 將第五個呼叫參數的 DWORD 寫入 confirmed-peer record `+0x14`；保存的 body 在該 store 前沒有 index mask 或 `<4` clamp。
- host 路徑 `0x108C960` 直接呼叫同一個 `0xB90B20`。
- 靜態 592-entry code-pointer run 的 entry 168 指向 `0xBABA80`。
- 固定 capture 的 hash 掃描只找到 sender immediate；沒有找到 hash 與 receiver pointer 的同表映射。

Verifier 輸出 `static_boundary=passed`，並且固定報告／資料 capture identity、receiver body、sender hash、direct call edges 和 build identity 全部通過。

## 仍然拒絕產生 production patch 的原因

Verifier 的 production gate 固定為 `blocked_receiver_registry_unresolved`：

1. 沒有保存 receiver-side hash→callback 的 writable registry 或可執行 lookup。
2. `0xBDE430` 只能證明 send-side generic dispatcher；不能把它當成 receive dispatcher ABI。
3. client confirmed-peer 的四筆 inline storage 在第五筆起點撞上 `+0x150`，relocation aliases、cleanup、unwind 和 owner lifetime 尚未閉合。
4. 因此輸出明確保持 `installable=false`、`runtime_invoked=false`、`game_memory_written=false`、`multiplayer_verified=false`。

只有在上述 registry、receive ABI、owner storage/cleanup 全部有固定版本可重播證據後，才允許把此邊界升級為可回滾的 production hook 候選。
