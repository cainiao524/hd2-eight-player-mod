# Receiver vector adapter（離線候選）

固定 build `25480438` 的 `0xBC2D10` callback-vector leaf、selector `168`、table entry `0x214C2E0 + 168*8 → 0xBABA80` 及五個 descriptor 欄位偏移 `+8/+18/+28/+38/+48` 已由保存的 code/data evidence 固定。本候選只把這個 ABI 形狀做成 fail-closed C++ decoder：只接受 selector 168，缺欄位或未知 selector 直接拒絕，五個值保持 opaque。

它刻意不把五個欄位猜成 peer、resource 或 network index，也不假設 `0x4804FCF4` 已能解析到 selector 168。建置會輸出 `ep_receiver_adapter_synthetic_passed`，但沒有 callback、hash registry、hook、注入、遊戲程序存取或多人功能。

```powershell
cmd /c build_x64.bat
```
