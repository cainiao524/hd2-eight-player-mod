# Host Join Mid-function Stub 候選（固定 Build 25480438）

這個目錄保存兩個「可檢查、可回滾、但尚未安裝」的 x64 machine-code stub 模板，用於把 host join 裡的兩個四格中段改接到八槽 sidecar：

- `game.dll + 0x108C18F`：capacity gate 的 38-byte 指令範圍，從 `0x108C18F` 到 `0x108C1B4`，跳回原本的 `sub ecx,eax`（`0x108C1BA`）。stub 保存 `r9/r12/r13/r14/r15/rbp`，呼叫 sidecar occupancy helper，驗證回傳值在 `0..8`，再讓原本的比較與分支保持有效。
- `game.dll + 0x108C3D8`：allocator loop 的 15-byte 指令範圍，跳回原本的 outer-loop continuation `0x108C3F7`。stub 保存 `r9/rdx`，呼叫 sidecar index helper，允許 `0..7` 或原生 `-1` sentinel，最後寫回原本使用的 `r8d`。

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

驗證器只讀取倉庫內保存的 `join_handler_disasm.json`，並在 synthetic byte buffer 中套用與還原 patch。它不開啟遊戲程序、不配置遊戲記憶體、不寫入 `game.dll`，也不安裝 function table。

## 生產狀態

這是 machine-code 與 unwind layout 候選，不是可安裝的八人 Mod。helper 位址目前是明確的 template sentinel，尚未綁定實際 host/client sidecar owner。以下契約仍未閉合，因此沒有安裝器入口：

- host/client sidecar 的生命週期、重入與 host migration。
- confirmed-peer hash 到 receiver 的實際 dispatcher 綁定。
- player creation、resource handle 與 cleanup 的 4→8 合約。
- 目標程序的 thread quiescence、`RtlAddFunctionTable` 註冊和卸載流程。
- 第五至第八帳號的同任務實機測試。

`machine_code_emitted=true` 只代表 bytes 與 unwind layout 已由靜態 verifier 產生；`executable=false`、`install_game_rva=false`、`multiplayer_verified=false` 才是本候選的有效狀態。
