# 2026-10-03 dynamic registration caller audit

這份固定 build `25480438` 離線審計掃描 dynamic registration body `0x1094680` 的直接 `E8` caller。保存的 code capture 沒有直接相對呼叫者；該 body 會把 caller-supplied `EDX` 存到 `[RCX+8]`，因此實際 hash／selector 仍由 runtime call boundary 提供。七個已恢復的 static registration immediate 也沒有 `0x4804FCF4`。

這只把缺口收窄到 runtime registration/dispatch state 或 callback trace，沒有取得 hash→selector ownership，也沒有生成或安装 hook。收據為 `dynamic_registration_caller_audit_20261003.json`。
