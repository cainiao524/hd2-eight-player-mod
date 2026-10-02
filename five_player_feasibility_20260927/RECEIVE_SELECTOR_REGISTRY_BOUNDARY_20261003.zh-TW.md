# Receive selector registry 邊界（2026-10-03）

這次只重播固定 capture 的 native bytes，沒有開啟遊戲程序、沒有寫入、沒有 hook、沒有安裝 Mod。目的在於把 `0xBC2D10` 的 selector vector 與附近的 registration call 形狀分開記錄，避免把靜態 registration 常數誤認成 `0x4804FCF4 → 168` 的服務映射。

## 可重播結果

```text
python five_player_feasibility_20260927/recover_selector_registry_20261003.py --write --output five_player_feasibility_20260927/recover_selector_registry_20261003.json
```

結果：7 個 `[RDX+0xB0]` registration sites、selector `168 → game.dll+0xBABA80`、固定事件雜湊 `0x4804FCF4` 在 bounded capture 只命中送端 `0xBE4981`。`hash_to_selector_proven=false`、`service_registry_captured=false`、`production_hook_ready=false`。

## 已固定的 registration 形狀

`0x134D69E` 起的六個 constructor call 與 `0x14EE278` 的另一個 call，都由前面的 `mov ecx, imm32` 提供靜態 hash，再以 `call qword ptr [rdx+0xB0]` 送入服務物件。另有 `0x10946A4` 同形 call，其值由 caller 透過 `EDX` 寫入 `[RCX+8]`，不是本機 code 的立即數；這是可能接收 runtime key 的 ABI 形狀，但沒有觀察到實際 hash 或 selector。

同一 capture 的無 unwind dispatch leaf `0xBC2D10` 仍是：`R8D` selector、`R9` descriptor、owner/context 保留在 `RCX`、table `0x214C2E0` 的 entry 168 指向 `0xBABA80`。這證明 callback vector 的下游 ABI，不證明服務端如何把事件雜湊選成 168。

## 結論與下一閘門

靜態資料把 registry 缺口縮小為「服務物件／執行期 callback state」，但沒有提供可安全安裝的 hook 入口。下一步仍需同一 build 的 service-side registration/dispatch state 或 runtime callback trace，實際看到 `0x4804FCF4` 帶入 selector 168；之後還要接上 player index `4..7` 建立、跨客戶端 replication、cleanup/unwind，並以五至八個獨立帳號完成真人驗收。所有 production flags 保持 `installable=false`、`multiplayer_verified=false`。
