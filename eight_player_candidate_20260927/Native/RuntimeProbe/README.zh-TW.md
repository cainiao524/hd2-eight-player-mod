# Host Join Runtime Probe 候選（build 25480438）

這個候選只保存一份**由外部已審核觀測器複製後傳入的入口 frame**。它不掃描、注入、呼叫或修改 Helldivers 2，也不寫入遊戲目錄；`ep_probe_record` 不會解參數中的指標，也不會讀取 `rsp`。

## ABI 證據

固定 build `25480438` 的 `game.dll + 0x108BC70` 是目前確認有正常函式序言的 host-join root。入口在 Windows x64 呼叫慣例下收到：

- `rcx`：host object，函式稍後保存至 `[rbp-0x59]`
- `rdx`：context/status pointer，保存至 `[rbp-0x69]`，並移入 `r12`
- `r8`：request list pointer，保存至 `[rbp-0x71]`，並移入 `rsi`
- `r9`：request container/count pointer，保存至 `[rbp-0x51]`；可見程式讀取 `[r9]` 作為 request count
- 入口 `rsp`：呼叫者 return address 位於 `[rsp]`，後續 stack home / argument 區只以複製資料形式記錄

`EP_PROBE_ENTRY_FRAME` 保存上述寄存器、`rsp`、`rbp`、`r12-r15`、flags、return address 及最多 16 個已由觀測器安全複製的 stack words。超過 16 個會截斷，任何指標不會被 dereference。

## 使用界線

`ep_probe_init` 只接受 build `25480438` 和 RVA `0x108BC70`。`ep_probe_validate_site` 僅在呼叫者提供已載入模組與預期 bytes 時做 read-only 比對；本候選沒有 game RVA installer，也沒有 detour 或執行緒暫停功能。固定 18-byte prologue SHA-256 為 `8deecd0b4075eee3e436db6d5787ba68feb5ade0b9401ce1eee9814995309624`。

記錄器使用 32 筆固定容量、可停止的記憶體緩衝區。`ep_probe_stop` 停止記錄，`ep_probe_start` 清除並重新開始，滿載或 profile 不符會 fail-closed。這只產生 ABI 證據；它沒有提供第五至第八名玩家的 admission、roster、entity 或多人驗收能力。

## 合成驗證

`build_x64.bat` 建立 DLL 與測試程式。測試只配置 synthetic memory，驗證 build/RVA gate、入口寄存器映射、stack 上限、固定容量、停止後拒絕，以及 site bytes 比對；輸出 `ep_runtime_probe_synthetic_passed`。
