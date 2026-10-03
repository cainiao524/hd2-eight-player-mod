# 2026-10-03 live registration state scan

原版固定 build `25480438` 的 PID `6884` 完成兩次只讀私有區掃描：128 MiB 基線，以及未截斷的約 1 GiB `MEM_PRIVATE` 範圍。掃描同時包含 receiver／insert／platform-member 指標、`0x4804FCF4`、以及七個 static registration immediate；兩次均為 0 命中。

同一程序仍在空 menu baseline（peer count `0`），文件化 roster 只有 4 槽。這是有界的負面觀察，不是「registry 不存在」的證明；沒有呼叫函式、寫入、hook、注入、安裝或第五個 peer 驗收。機器收據為 `live_registration_state_verification_20261003.json`。
