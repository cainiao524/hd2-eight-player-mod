# 快照交接、環境與來源

## 目前交付範圍

本倉庫保存研究與必要依賴。2026-09-28已恢復離線工作並收尾 `0.14.0-offline`；6054F0審查、文件與交付收據已更新。原快照清單與上傳收據仍對應2026-09-27資料提交；比對目前工作區出現後續研發差異是預期結果，若要核原快照應使用其指定提交。現有歷史版本、絕對路徑及報告保留原文。

`research_handoff_20260927` 也保存較早 projectile 等研究的來源沿革。該歷史內容可能引用其他工作目錄；本次可重建範圍是目前八人研究及其已核對的必要依賴。其他 Mod、遊戲安裝、語音包及 FileDiver 完整建置環境不包含於本倉庫。

## 取得與驗證

以下 PowerShell 命令供新的 Windows 環境使用。先備妥 Git 與 Python 3.12，並以有權限的 GitHub 帳號存取此私人倉庫：

```powershell
git -c core.autocrlf=false clone https://github.com/cainiao524/hd2-eight-player-mod.git
Set-Location hd2-eight-player-mod
git config --local core.autocrlf false
py -3.12 -B github_handoff_20260927/verify_snapshot.py
```

驗證工具需要 Git 與 Python 標準庫。預設讀取目前 Git `HEAD` 中上傳收據的 `payload_commit`；亦可用 `--revision <commit>` 指定資料提交。工具會核對該提交的完整 tree、檔案數、大小及逐檔 SHA-256，不修改檔案。快照清單本身由 Git commit 定位，無法也不需要記錄自己的雜湊。

上傳收據與 `STATE.json` 的上傳欄位是在資料提交成功後另行提交的行政更新。它們不會改寫資料提交或其快照清單；資料提交內原本的 `workspace_uploaded: false` 記錄的是推送前狀態。目前上傳結果以最新 `HEAD` 的收據與狀態為準。

## 重建離線 Python 依賴

原工作環境為 Python 3.12.10。依賴版本已由需求檔固定，可從倉庫根目錄重建到既有程式使用的位置：

```powershell
py -3.12 -m pip install --target eight_player_candidate_20260927/.native-test-deps -r eight_player_candidate_20260927/requirements-native-tests.txt
py -3.12 -m pip install --target eight_player_candidate_20260927/.test-deps -r eight_player_candidate_20260927/requirements-offline-tests.txt
```

原生測試依賴為 `unicorn==2.1.4`、`capstone==5.0.7`；Lua 離線測試依賴為 `lupa==2.6`。依賴目錄不納入 Git。

## 倉庫內既有 capture

共用 reader 僅需這兩個檔案；此次為複製既有證據，未新增程序擷取：

| 倉庫相對路徑 | SHA-256 |
|---|---|
| `evidence/existing-code-evidence-25480438/capture-report.json` | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| `evidence/existing-code-evidence-25480438/captured-data.bin` | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |

capture identity 為 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。Reader 會自行拒絕不符固定值的來源。

以下命令是使用者明確恢復離線研究後的重播範例；輸出寫入新的暫存目錄，保留原研究快照：

```powershell
$taskReplayDir = Join-Path ([System.IO.Path]::GetTempPath()) ('hd2-replay-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskReplayDir | Out-Null
$taskOldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (Resolve-Path eight_player_candidate_20260927/.native-test-deps).Path
    py -3.12 -B five_player_feasibility_20260927/roster_arrival_native_replay.py --evidence evidence/existing-code-evidence-25480438 --output (Join-Path $taskReplayDir 'arrival.json')
    if ($LASTEXITCODE -ne 0) { throw 'Offline replay failed' }
} finally {
    $env:PYTHONPATH = $taskOldPythonPath
}
```

此 replay 只接受 `--evidence`、`--output`，且輸出父目錄必須先存在。它讀取已保存的 code/readonly bytes，不建立遊戲程序連線。若使用共用 `inspect_capture.py --function`，輸出僅涵蓋該 unwind fragment；完整 6054F0 body 應明確使用 `--dump 0x6054F0 0x457`。

多份測試腳本直接執行時會重寫 `verification` 報告。僅驗證既有 arrival 測試而保留原收據，可在恢復研究後使用 `py -3.12 -B -m unittest discover -s eight_player_candidate_20260927/tests -p test_native_roster_arrival.py -v`。本次上傳驗收只核對檔案與 Git 物件，未重新執行研究套件。

## 外部來源子集

FileDiver 來源為 https://github.com/xypwn/filediver ，本機 checkout revision 為 `bf0ce329db3cf0043994eb717ea86433c303cb36`。保留其 `LICENSE`、`README.md`，並納入以下 13 個重播所需檔案；逐檔內容以快照清單及既有 replay pins 為準：

- `stingray/hash.go`、`stingray/hash_test.go`。
- `hashes/hashes.txt`、`thinhashes.txt`、`material_textures.txt`、`cracked.txt`、`dl_type_names.txt`。
- `datalibrary/generated_entities.dl_bin`、`generated_entities.dl_bin.gz`、`entity_component_settings.go`、`entity_deltas.go`、`datalib_instance.go`、`datalib.go`。

`.dl_bin` 與 `.gz` 均保留，因既有 replay 同時檢查兩份 SHA。此子集不足以完整建置 FileDiver；如需完整上游工具，依來源 revision 另行取得。

另保留三個既有工作區單檔：

- `voice_tw_integration_20260927/extract_baseline.py`：rank asset extractor 固定 SHA 載入的封包讀取 helper。八人研究所需的已擷取 rank payload 已在研究目錄內保存。
- `loader_v18_compat_20260927/external/v18/source/README.md`：原研究報告連結的 Loader 說明；來源參考為 https://github.com/CowboyBingus/BingusSharedLoader 。
- `pcf_four_scope_test2_v18_20260927/Source/runtime/image_windows.lua`：原研究報告連結的唯讀 FFI adapter。

另有早期研究參考 https://github.com/MrChengl11/hd2-lua-mod-skill 。這些參考連結不表示已在新環境安裝 Loader 或執行遊戲。
