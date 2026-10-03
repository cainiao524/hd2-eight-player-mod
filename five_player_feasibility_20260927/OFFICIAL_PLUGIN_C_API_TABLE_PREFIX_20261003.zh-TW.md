# 官方插件 C API 表前綴捕獲（2026-10-03）

此證據來自固定版本 `Build 25480438` 的一次**唯讀、邊界受限**擷取。擷取程式只讀取已知 `Network` 與 `GameSession` table 指標、重讀確認相等，並對每個指標保存短前綴與反組譯；沒有呼叫任何擷取到的函式、寫入遊戲記憶體、安裝 hook 或修改程序狀態。

## 捕獲內容

- `helldivers2.exe+0x27cbe30`：`Network` table，來自公開 ScriptApi slot `0x38` 的語意標籤。
- `helldivers2.exe+0x27cbb90`：`GameSession` table，來自公開 ScriptApi slot `0x40` 的語意標籤。
- 每個 table 的指標與短前綴均標記模組歸屬、RVA、SHA-256 及重讀結果。
- table entry 的反組譯只用於描述 wrapper 形狀；它不等於已解析 HD2 的 peer、Party 或玩家建立語意。

完整機器資料：[live_c_api_table_prefixes_20261003.json](live_c_api_table_prefixes_20261003.json)

## 邊界

這份捕獲證明官方 plugin 可以在該 build 看到穩定的 C API table 前綴，並提供版本指紋候選。它不能證明第五至第八個 peer 可加入，也不能證明 wrapper 內部的固定槽位、呼叫慣例、生命週期 callback 或 Party admission 已打通。後續任何寫入或呼叫都必須先重新驗證 build、table、函式前綴和參數契約。
