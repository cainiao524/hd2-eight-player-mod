# Mod Options Menu 公開倉庫研究（2026-10-04）

## 快照與來源

本報告只讀取公開倉庫 `CowboyBingus/ModOptionsMenu`，沒有執行遊戲、Shared Loader 或 Lua addon，也沒有把它複製成八人 Mod 的 runtime 依賴。讀取時間為 2026-10-04，`main` 與 `v1.1` 指向同一提交：

```text
46d693e421b44c4221ee6d984d26ea49997b948a
```

主要來源：

- [README.md](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/README.md)
- [src/mod_options_menu.lua](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/src/mod_options_menu.lua)
- [scripts/build.py](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/scripts/build.py)
- [tests/test_options_tab.lua](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/tests/test_options_tab.lua)
- [docs/VALIDATION.md](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/docs/VALIDATION.md)
- [CHANGELOG.md](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/CHANGELOG.md)
- [publication-files.json](https://github.com/CowboyBingus/ModOptionsMenu/blob/46d693e421b44c4221ee6d984d26ea49997b948a/publication-files.json)

## 專案定位

這個專案是 **Mod Options Menu v1.1**：在逃生選單加入 `MODS` 分頁，讓其他 addon 註冊 toggle、choice、slider。它不是 lobby、Party、peer、roster 或 entity replication 模組。README 宣稱每個 mod 最多一個分類按鈕（最多 8 個分類）和每個 mod 最多 32 個選項，套用後的值保存到 `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\ModOptionsMenu.values`。

它要求 **Bingus Shared Loader v18 或更新版本**，並以 Wwise startup replacement 載入 addon。`publication-files.json` 將 `src/mod_options_menu.lua`、`src/bingus_text.lua`、`scripts/entry.py`、測試檔和 archive 建置腳本列為發布內容。

## Loader 與 runtime 入口

### Lua addon 入口

`src/mod_options_menu.lua` 的第一行標記 addon 名稱為 `mods/cowboybingus/mod_options_menu`。它讀取 `_G.CowboyBingusModLoader`，若 loader 提供 `open_log` 就建立 `ModOptionsMenu.log`；最後將 API 放到 `_G.ModOptionsMenu`。

它保存原本的 `_G.update`，再安裝自己的 `update(dt)` 包裝器：先以 `xpcall` 執行選單步進，再呼叫原本的 update。這是可供八人 Mod 借用的 **Lua update 鉤子**，但只能在當前 client 的 Lua 執行個體內執行，沒有跨 client 的傳輸語義。

### Native UI 驗證與記憶體讀寫

初始化時使用 FFI 取得當前 `game.dll`、EXE 的模組 handle，計算兩個檔案的 SHA-256，並檢查列出的每個 native entry point 起始 bytes。只在 build 驗證成功後設定 native 函式表；失敗時記錄錯誤並讓 `ready()` 保持 false。源碼也使用 `ReadProcessMemory` 保護尚未確認有效的 UI pointer，之後對 escape menu 的 heap UI 物件做讀寫。

這些檢查對 **UI addon 自己** 是版本安全措施，不能推導出 Session/Party 或玩家 entity 的地址、ABI、容量或可複製性。它沒有讀取或修改 lobby membership、peer admission、confirmed-peer、player creation 或 network replication 結構。

### 建置與套件入口

`scripts/build.py` 要求旁邊有 Bingus Shared Loader checkout（或 `BINGUS_SHARED_LOADER` 環境變數），匯入 loader 的 `archive.py` 與 `build_addon.py`，把 Lua source 組成 archive 和 `manifest.json`，再產生 release ZIP。addon GUID 是 `95ef276a-6287-465f-ac5b-8512d2227b74`，測試 addon 有另外的 GUID。這是打包與載入契約，不是八人 native bridge 的接口。

## 可供其他 mod 使用的 API

API 物件在 `_G.ModOptionsMenu`，README 和源碼列出：

| API | 用途 | 對八人 Mod 的意義 |
|---|---|---|
| `api = 1`, `version = 2` | API 版本識別 | addon 可先檢查 `menu.api == 1`、`menu.version >= 2` |
| `register_option(id, spec)` | 註冊 toggle、choice、slider | 可加入 debug、host-only、enemy budget、診斷等本地選項 |
| `get(id)` | 讀取已套用值 | 只讀取這個 client 的值 |
| `set(id, value)` | 程式設定並保存值 | 不呼叫 `on_change`，不能取代 network admission |
| `on_change(id, fn)` | 玩家按 APPLY 後的本地 callback | 可更新本地 sidecar 設定或記錄，但不會同步其他 client |
| `ready()` | native UI 是否已通過版本檢查 | 只代表 UI integration 可用，不代表八人網路路徑可用 |

註冊值的限制是：option ID 最長 96 字元；label 64；mod name 40；choice 2 至 16 個、每個 48；description 400；每個 mod 最多 32 個選項。API v2 允許 label、mod、description 和 choices 用函數依目前語言重新解析。

## 對八人 Mod 的實際可用性

### 可以直接使用的部分

1. **本地配置入口**：八人 addon 可以用 `register_option` 提供 `enabled`、`host_only`、`diagnostics`、`enemy_budget` 或測試階梯等 UI 選項。
2. **本地診斷 callback**：`on_change` 可在使用者按 APPLY 後更新本地設定、開關 debug log 或觸發目前已存在的 caller-owned sidecar；這不會自動觸發 native peer callback。
3. **版本 gate 參考**：它已示範在 Steam build `25480438`、EXE `1.8.46015.0` 上做 hash 和 entry-point 檢查。八人 Mod 可以沿用「版本不符就拒絕啟用」的原則。
4. **既有 loader 入口**：若八人 addon 採用 Bingus Shared Loader，可用自己的 `mods/<author>/<addon>` entry，並依 loader 的 archive/manifest 契約打包。

### 不能由它完成的部分

1. **沒有 Session/Party API**：源碼沒有 lobby member count、max member、join result、peer index、host migration 或 Party endpoint 介面。
2. **沒有玩家建立或 entity replication API**：native 表只有 UI widget、row、category、text 和 escape menu 的函式；沒有 Player Clone、NetworkOverride、confirmed-peer 或 entity network data 的 callback。
3. **設定不是跨 client 狀態**：值保存在每台電腦自己的 `%LOCALAPPDATA%` 檔案，`on_change` 也是該 process 的 Lua callback。房主在選單中把容量設成 8，不會讓其他七個 client 得到同一設定，也不會提高 lobby 或 Party 容量。
4. **host-only 不會因此成立**：只安裝 Mod Options Menu 到房主最多只能提供房主的 UI。若八人 native bridge 要求每個 client 改讀取、建立或接收第 5 至第 8 個 player entity，仍須讓所有需要修改的 client 安裝相同版本的實際八人 addon；Mod Options Menu 本身不能轉送這些修改。
5. **版本範圍固定**：README 和源碼都鎖定 Steam build `25480438`，而且每個 UI native entry point 都要通過 bytes 檢查。遊戲更新後，MOM 可能保持 `ready()==false`；這不是八人容量失敗的證據，但八人 addon 必須另做自己的版本 gate。

## 建議接線方式（尚未加入 production）

八人 addon 若需要 UI，可採用以下邏輯：

```lua
local menu = rawget(_G, 'ModOptionsMenu')
if menu and menu.api == 1 and (menu.version or 1) >= 2 then
    menu.register_option('eight_player.diagnostics', {
        type = 'toggle', label = 'Diagnostics', mod = 'Eight Player', default = false
    })
    menu.on_change('eight_player.diagnostics', function(value)
        -- 只更新本 client 的診斷設定；真正 native bridge 仍需另外驗證。
    end)
end
```

不要把 `menu.ready()`、選單中的 8 個分類或單機顯示的 8 個選項當成 network capacity 證據。真正的八人 gate 仍需通過既有 Session/Party admission、client confirmed-peer、player creation、entity replication、cleanup 和八帳號同任務驗收。

## 公開驗證的邊界

倉庫的 `docs/VALIDATION.md` 說明：離線測試在遊戲自己的 `lua51.dll` 上以模擬記憶體涵蓋選單、row、APPLY、未套用變更、保存值、對齊與讀取預算；記錄的遊戲測試涵蓋兩個註冊 mod、toggle、slider、APPLY、丟棄和重啟保存值，但 controller navigation 尚未在遊戲中驗證。這些證據只驗證 Mod Options Menu 的 UI/設定功能，沒有八人聯機證據。

## 結論

`ModOptionsMenu v1.1` 對八人專案的定位是 **可選的本地設定與診斷 UI 依賴**。它能讓八人 addon 暴露開關和測試參數，並提供 Shared Loader 的 Lua entry/update 鉤子；它不能提供第五至第八 peer 的 admission、player index、entity 建立、跨 client 設定同步或完整任務生命週期。因此不改變目前八人專案的 `installable=false`、`runtime_verified=false` 和 `multiplayer_verified=false` 判定。
