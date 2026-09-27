# `interface_probe.py` 離線審查

時序補充：以下是實際擷取之前的獨立審查記錄。審查後第 1 項的欄位已更名為 `utility_file_sha256_at_output`；使用者其後另行同意並完成一次限定唯讀擷取，見 [操作與結果](INTERFACE_PROBE.zh-TW.md)。以下「未測試」描述保留為當時的審查狀態，不代表後續擷取失敗。

結論：**沒有發現本輪必須修正的 blocker；未做任何 live capture。** 工具仍只是供未來明確授權時使用的唯讀觀測準備。

## 核對結果

- 以本機 64-bit Windows Python 的 `ctypes` 檢查：`MODULEINFO` 為 24 bytes，欄位 offset 0/8/16；`MEMORY_BASIC_INFORMATION` 為 48 bytes，欄位 offset 0/8/16/20/24/32/36/40。布局符合 Microsoft 的結構宣告。`OpenProcess(0x0410)` 只要求 `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`；其後用到的跨程序 API 均為查詢或讀取。
- 磁碟檔案全 SHA-256 檢查、loaded PE header 比對和兩處 loaded-code pin 順序在指標走訪之前。兩個 pin 的 SHA-256 已從固定 capture 獨立重算，完全匹配。末尾再驗一次已載入 PE/pin、程序路徑、模組列表及磁碟檔案。
- `--plan` 無程序存取；說明文件指定的 `unittest discover` 指令與直接執行 `test_interface_probe.py` 都通過 9 項 mock。mock 沒有覆蓋 Windows adapter，本工具也未在目標程序測試。
- `atomic_snapshot: false`、`eight_player_verified: false` 及每個前綴的 ABI/語義未證明標註是正確的。欄位重讀相同仍可經歷短暫變動、位址重用或程式碼頁替換；輸出未聲稱一致快照。

## 改善項（不阻擋保留為準備工具）

1. `capture_utility_sha256`（`interface_probe.py:271`）於執行結尾重新讀取腳本檔案。若腳本在執行期間被更換，該值不一定是已執行程式的內容指紋。可在啟動時讀取並固定；輸出欄位也可明確命名為 `utility_file_sha256_at_report`。
2. 磁碟 SHA-256、兩處 loaded-code pin 和 PE header 不能證明已載入 `game.dll` 的每個位元組相同，也沒有釘住函式目標所屬的第三方模組。`build: 25480438` 應維持為「磁碟雙檔匹配、載入頁面局部匹配」的解讀；後續分析需以輸出中的實際前綴位元組為準。
3. `observed_fields_unchanged_on_reread` 僅涵蓋指標／設定欄位；函式程式前綴只讀一次。這在目前輸出名稱和 `atomic_snapshot: false` 下是誠實的，但後續分析不應把「欄位未變」寫成「程式前綴一致」。
4. 測試使用文件中的 `unittest discover` 入口；若在研究目錄直接以 `python -m unittest tools\\test_interface_probe.py` 執行，會因 `import interface_probe` 的搜尋路徑失敗。這不影響指定的測試指令或執行工具。

參考官方 API 定義：[MEMORY_BASIC_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-memory_basic_information)、[VirtualQueryEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualqueryex)、[EnumProcessModulesEx](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumprocessmodulesex)。
