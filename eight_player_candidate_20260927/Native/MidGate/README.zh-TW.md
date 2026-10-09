# Host Join Mid-function Stub 候選（固定 Build 25480438）

這個目錄保存兩個「可檢查、可回滾、但尚未安裝」的 x64 machine-code stub 模板，用於把 host join 裡的兩個固定四格中段改接到容量契約 sidecar：

- `game.dll + 0x108C18F`：capacity gate 的 38-byte 指令範圍，從 `0x108C18F` 到 `0x108C1B4`，跳回原本的 `sub ecx,eax`（`0x108C1BA`）。stub 保存 `r9/r12/r13/r14/r15/rbp`，分別呼叫 occupancy 與 limit helper；有效上限夾在 `1..16`，再讓原本的比較與分支保持有效。
- `game.dll + 0x108C3D8`：allocator loop 的 15-byte 指令範圍，跳回原本的 outer-loop continuation `0x108C3F7`。stub 保存 `r9/rdx/r12/r13`，分別呼叫 index 與 limit helper，允許 `0..effective_limit-1` 或原生 `-1` sentinel，最後寫回原本使用的 `r8d`。

2026-10-03 的 ABI 校正把 helper 的 owner/index 搬移固定為 `49 8B CF` 或 `49 8B CD`（先保存 owner，再以 `mov rcx,r15/r13` 呼叫）以及 `41 8B D6`（`mov edx,r14d`）。舊的 `4C 8B C9` 實際會解碼成 `mov r9,rcx`，不能把 native owner 傳給 helper；舊的 `44 8B D6` 實際會解碼成 `mov r10d,esi`，不能把 native index 傳給 helper。capacity 與 allocator 都由 limit helper 提供有效上限，並在 continuation 前恢復原本需要的非揮發寄存器。校正後的 stub、收據和 verifier 已重新生成並逐項一致。

Executor 的卸載流程會分別嘗試兩個 site。若其中一個 site 的 bytes 被外部改動，另一個 site 仍會先恢復；未恢復的 site 狀態保留在 `EP_MIDGATE_HOOK`，待 bytes 回復後可再次呼叫 remove。原始 bytes 已恢復但 page-protection 還原回報失敗時，stub 仍會先解除 function table 並釋放，避免留下不可重試的假 ownership。

每個 site 都保存：

1. 固定 Build `25480438` 與 `game.dll` SHA-256。
2. 完整原始指令 bytes 與 SHA-256。
3. 14-byte absolute jump + NOP patch template。
4. 產生出的 stub bytes 與 SHA-256。
5. x64 `UNWIND_INFO` bytes、prologue 長度及 `RUNTIME_FUNCTION` 相對欄位。
6. 回滾順序：停止進入、恢復原始 bytes、flush instruction cache、刪除 function table、釋放 stub。

## 驗證

```powershell
& 'C:\Program Files\Python312\python.exe' -B -m unittest -v eight_player_candidate_20260927\Native\MidGate\test_midgate_stub_candidate.py
& 'C:\Program Files\Python312\python.exe' -B eight_player_candidate_20260927\Native\MidGate\verify_midgate_stub_candidate.py --output eight_player_candidate_20260927\Native\MidGate\verification\midgate_stub_candidate_verification_20261002.json
```

工作區另有可重建的離線 executor harness：在 `Native/MidGate` 執行 `cmd /c build_x64.bat` 會編譯 `ep_midgate_executor.dll`、synthetic install/remove harness 和 export load check。它只對合成 PE image 執行，並要求 caller 自行提供 owner、helper lifetime 與 thread quiescence；沒有遊戲程序或 loader 路徑。

驗證器只讀取倉庫內保存的 `join_handler_disasm.json`，並在 synthetic byte buffer 中套用與還原 patch。它不開啟遊戲程序、不配置遊戲記憶體、不寫入 `game.dll`，也不安裝 function table。

## 生產狀態

這是 machine-code 與 unwind layout 候選，不是可安裝的八人 Mod。helper 位址目前是明確的 template sentinel，尚未綁定實際 host/client sidecar owner。以下契約仍未閉合，因此沒有安裝器入口：

- host/client sidecar 的生命週期、重入與 host migration。
- confirmed-peer hash 到 receiver 的實際 dispatcher 綁定。
- player creation、resource handle 與 cleanup 的 4→8 合約。
- 目標程序的 thread quiescence、`RtlAddFunctionTable` 註冊和卸載流程。
- 第五至第八帳號的同任務實機測試。

`machine_code_emitted=true` 只代表 bytes 與 unwind layout 已由靜態 verifier 產生；`executable=false`、`install_game_rva=false`、`multiplayer_verified=false` 才是本候選的有效狀態。
