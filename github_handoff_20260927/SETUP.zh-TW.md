# 環境重建、離線驗證與來源 — 2026-10-19

## 目前交付範圍

本倉庫保存研究與必要依賴，最新狀態見 [CURRENT](CURRENT.zh-TW.md)。快照清單與最新上傳收據對應本次整理的資料提交；原 2026-09-27 收據保存在 `archive/UPLOAD_STATUS_20260927.json`，可使用其中的提交編號核對舊快照。歷史版本、絕對路徑及報告保留原文，並不要求在原機器路徑上重播。

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

## 最新接手的最小離線驗證

以下在倉庫根目錄執行。建立專用 Python 3.12 環境，避免把原生重播依賴裝入其他專案；此節不需要遊戲啟動或遊戲安裝檔。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r github_handoff_20260927/requirements-handoff.txt
$handoffRunDir = Join-Path 'work' ('handoff-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $handoffRunDir | Out-Null
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  five_player_feasibility_20260927/tools/test_party_manager_binding.py `
  five_player_feasibility_20260927/tools/test_capture_live_party_slots.py `
  five_player_feasibility_20260927/tools/test_party_dispatcher_supplement.py `
  --basetemp (Join-Path $handoffRunDir 'pytest') `
  --junitxml (Join-Path $handoffRunDir 'sampler-tests.xml')
if ($LASTEXITCODE -ne 0) { throw 'Offline sampler checks failed' }
.\.venv\Scripts\python.exe -B five_player_feasibility_20260927/tools/capture_party_dispatcher_supplement_20261016.py `
  --plan --output (Join-Path $handoffRunDir 'supplement-plan.json')
if ($LASTEXITCODE -ne 0) { throw 'Offline plan failed' }
.\.venv\Scripts\python.exe -B five_player_feasibility_20260927/tools/decode_captured_party_entries_20261016.py `
  --output (Join-Path $handoffRunDir 'entry-call-boundary.json')
if ($LASTEXITCODE -ne 0) { throw 'Offline replay failed' }
```

三個測試檔使用假讀取器及工作區證據，預期合計 63 項通過。計畫輸出應為 16 筆請求、33,018 bytes、65,536 bytes 硬上限，且 `process_accessed=false`。入口重播應得到六個固定 PartyWin RVA，其中 `0x19880`、`0x1BE80` 仍未命名，`new_game_reads=0`。這些結果不證明實機 ABI 或多人功能。新輸出使用新目錄，不覆寫保存證據。

工具會優先搜尋既有 `.native-test-deps`；新 clone 沒有該目錄時，使用虛擬環境中的固定依賴即可。保存的歷史 pytest／Unicorn 日誌含 Windows access-violation 診斷；接手時應保留實際 stderr 和退出碼，不能只看 passed 數量。

檢查既有 v0.14 離線交付內容，可另執行：

```powershell
.\.venv\Scripts\python.exe -B eight_player_candidate_20260927/verify_v014_delivery.py
```

此驗證核對來源指紋、固定報告、文件連結及離線 CLI bundle，不連接遊戲。不要為消除不符而直接使用 `--write`；先查明來源與收據差異。本次實際結果見 [VALIDATION_20261019.json](VALIDATION_20261019.json)。

## 原生候選的建置入口

原生部分使用 Windows x64、MSVC C++20 與 Windows SDK。現有 `Native/*/build_x64.bat` 多數固定呼叫 `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat`；新機器若安裝位置不同，先調整該路徑，再在獨立 clone 建置。這是現有可移植性限制，本次沒有重建所有 native 產物。

- 整合入口：`eight_player_candidate_20260927/Native/OfficialPlugin/build_x64.bat`。
- 個別元件：`Native/Bridge/`、`Native/ClientReplication/`、`Native/PlayerResource/`、`Native/PlayerCreationGate/` 內的建置腳本與 README。
- 腳本會編譯並執行各自的合成測試，部分工具會更新 receipt。保留原快照後再建置，按實際結果更新指紋。
- 建置完成的 DLL／EXE 是研究候選與測試工具；安裝至遊戲與實機載入仍是另行授權和驗收的步驟。

## 歷史工具的原路徑依賴配置

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

多份測試腳本直接執行時會重寫 `verification` 報告。僅驗證既有 arrival 測試而保留原收據，可在恢復研究後使用 `py -3.12 -B -m unittest discover -s eight_player_candidate_20260927/tests -p test_native_roster_arrival.py -v`。本次交接只重跑上列限定離線檢查，未重新執行完整研究套件或全部 native build。

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
