# 官方 Stingray Plugin ABI 邊界

`get_plugin_api(unsigned)` 是固定 build 的官方 plugin 載入 ABI 候選。此目錄提供一個最小、版本化且 fail-closed 的探針：

- 只接受 `api_id == 0`（`PLUGIN_API_ID`），未知 API ID 回傳 null。
- `loaded` 只查詢 `C_API_ID == 31` 並保存返回指標；依公開 `ScriptApi` 順序讀取 `Network` slot `+0x38`、`GameSession` slot `+0x40` 的 table 指標並保存，但不解參照其中的 function pointer、不呼叫函式、不寫入遊戲記憶體、不建立 peer、不建立 player entity。
- `unloaded` 清除保存的指標，避免跨生命週期使用 stale API。
- `build_x64.bat` 會產生 DLL 並執行本機 stub harness；這個 harness 不載入遊戲、不存取程序。

公開 ABI 來源：[Autodesk Stingray plugin API samples](https://github.com/AutodeskGames/stingray-plugin-api-samples) 與 [Stingray engine plugin 說明](https://help.autodesk.com/cloudhelp/ENU/Stingray-SDK-Help/sdk_help/extend_engine.html)。

這是官方插件入口的 ABI 骨架，不是八人功能本身。要接八人 sidecar，還需要同一 build 的 `ScriptApi`／`GameSessionCApi` 版本核對、合法 plugin 載入證據、第五至第八個 peer admission 與 player creation callback，以及所有 client cleanup/migration 路徑。任何一項缺失都保持 disabled。
