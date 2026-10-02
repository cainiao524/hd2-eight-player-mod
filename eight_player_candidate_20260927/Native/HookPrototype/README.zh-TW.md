# x64 reversible hook scaffold（build 25480438）

這是 native/session 改接的可執行骨架與 synthetic 驗證器。它沒有修改 Helldivers 2，也沒有提供自動掃描或自動 patch 遊戲程序的入口。

## 已驗證的路徑

`ep_install_hook` 僅接受呼叫者已確認的指令邊界與長度。它會：

1. 保存原始 bytes。
2. 配置 trampoline，複製被偷取的指令，接一個 x64 absolute jump 回原函式。
3. 以 version-1、zero-code 的 `UNWIND_INFO` 呼叫 `RtlAddFunctionTable`；metadata 會按 DWORD 對齊，並把 code range 與 unwind data 分開。
4. 以 14-byte `FF 25 00 00 00 00 + uint64 target` 覆蓋目標並呼叫 `FlushInstructionCache`。
5. `ep_remove_hook` 在呼叫者保證所有執行緒已 quiesce 後恢復原始 bytes、刪除 function table 和釋放 trampoline。

`ep_relocate_block` 會在複製 stolen span 時調整 RIP-relative memory displacement 及 rel32 `CALL/JMP`，並明確拒絕 short branch、conditional rel32 branch、位移超出 int32 或未辨識的相對形式。這讓含有 RIP-relative 指令的 trampoline 不會靜默跳到錯誤地址；尚未支援的指令會 fail-closed。

`native_hook_test.exe` 用配置出來的 synthetic code 驗證安裝、detour、trampoline、unwind registration 和移除後恢復。測試不載入 `game.dll`，也不改寫遊戲目錄。

測試也以 synthetic module mapping 驗證 `game.dll + 0x108BC70` 的 18-byte host-join prologue，並覆蓋 RIP-relative load、rel32 call 的 relocation 以及 short/conditional branch 的拒絕。這個入口是第一個可採用標準函式 ABI 的候選；`0x108C18F` 的 capacity gate 位於函式中段，不能拿同一個 detour 介面直接接入。

## 生產 root 的安全界線

目前 admission capture 的第一個普通函式入口是 `game.dll + 0x108BC70`，18 bytes 的 prologue 已在實機 capture 中核對。`game.dll + 0x108C18F` 是同一函式中段的 capacity gate；它需要保存呼叫現場與分支語意，不能用標準 DLL detour 直接覆蓋。生產整合前必須由外層 preflight 先確認 Steam build `25480438`、已載入模組 identity 和各 4 KiB capture site bytes，再由經審核的指令表決定真正 stolen length。這個 scaffold 刻意沒有 `install_game_rva`，因此不會把未完成的 sidecar、owner lifetime、confirmed-peer dispatch 或 player-creation gate 假裝成可安裝 Mod。

不能把單一 `cmp 4` 改為 `cmp 8`。生產版本仍需要：所有 peer roots 的 trampoline、host/client sidecar owner、host migration、callback unwind、thread quiescence，以及第五人實機 join 的逐級驗證。
