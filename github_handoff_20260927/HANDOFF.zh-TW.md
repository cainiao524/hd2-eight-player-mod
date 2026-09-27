# GitHub 接續交接：依使用者要求停止

## 先讀這兩份檔案

1. [完整目標](GOAL_OBJECTIVE.zh-TW.md)：原目標逐byte副本，沒有縮小八人驗收範圍。
2. [暫停時檔案指紋與待辦](STATE.json)：辨認已交付版本和尚未收尾的新候選。

使用者已要求暫停，準備建立新GitHub倉庫並上傳相關工作，之後另行交接。所有三個研究／測試分支均已中斷。目標工具查詢回傳 null；不要自動重建或繼續目標，須等使用者明確恢復。此交接文件的保存不是恢復研發。

## 完整目的與實際狀態

完成八名真人、八個獨立帳號在同一任務合作的可安裝HD2 Mod，包含原始碼、相容版本、建置／安裝／移除、錯誤診斷與完整實測紀錄。第五人只是中途門檻。

目前仍沒有可安裝、已驗證可玩的五人或八人Mod。現有產物是版本固定的離線原生候選、合成記憶體指令測試及研究證據；不可把模擬八筆資料、綠色測試或loader載入當作多人成功。

## 最後完成的正式交付：v0.13

- `eight_player_candidate_20260927/candidate-manifest.json` 仍為 `0.13.0-offline`。
- `verification/delivery_checks.json` 仍是v0.13收据；15個候選來源檔、14份測試報告、144組／4,272次套件執行或觀察。
- v0.13共同bundle有15個roster函式與獨立player_count計畫，59個已知區域。
- 4,272包含原版基準、拒絕、26次context前綴觀察及預期原版反例，不能稱為候選成功次數。
- 五份全域文件在暫停時尚未升到v0.14；它們列6054F0為下一切點，應與下述未發布實作一起閱讀。

## 暫停時的新實作：6054F0狀態更新，尚未發布v0.14

工作檔名使用`arrival`，但這個函式沒有新增map項目或增加T/D/P，沒有證明它就是完整加入／append流程。

已保存：

- `Native/roster_arrival.py`：完整1111-byte原body產生1917-byte候選；19個陣列／衍生基址改接共同B，41個局部分支、23個RIP參照、4個直接及4個間接calls保留。
- 入口guard檢查綁定、target／caller-state非null、數量、map key／ordinal及實體pointer；保留原frame、cookie、暫存器與重要條件旗標。
- 原network index 0..3走四列palette，>=4保留原白色fallback，沒有把四列表直接擴讀至八列。
- 原三處通知繼續傳當時D，沒有套用departure的預測公式。
- 新共同sample含16個roster函式、原player_count計畫及62個已知區域；嵌入v0.13產物相同。主代理已經由CLI重建，逐byte一致。
- `tests/test_native_roster_arrival.py`及報告已凍結：5組／42次頂層執行全部通過，分為原版完整4、候選完整21、入口拒絕17。內層真FD9AF0共25次，另列不加總。
- 全19位點靜態核對，其中17個有效輸入可達位點有動態斷言；6056C8／6056D6的invalid-ordinal分支被入口guard擋住，只有靜態核對。
- `verification/native_roster_arrival_review.zh-TW.md`獨立source審查已落檔，未發現局部阻塞缺陷。
- `five_player_feasibility_20260927/roster_arrival_native_*`保存replay、兩份逐byte一致evidence、findings及prerequisites。

尚未完成的收尾：

1. 獨立oracle審查代理已回報有限核對未見缺陷，但被暫停時**尚未寫出**`verification/native_roster_arrival_test_review.zh-TW.md`。口頭回報不能當作已交付審查文件，恢復後需據實檢查並補存。
2. `NATIVE_ROSTER_ARRIVAL.zh-TW.md`是已保存的契約／CLI草稿，測試段尚未完成正式數字與審查連結。
3. Manifest、README、REPORT、WORKLIST、PLAN、VERIFICATION與delivery receipt尚未納入新候選。不能聲稱v0.14正式交付完成。
4. 完成上述核對後，本輪套件總數應為149組／4,314次；目前正式v0.13仍是144／4,272。先查實檔與報告，再更新總數。

恢復後先收尾這份已有實作，避免從頭重做6054F0研究或重跑未改的舊套件。候選以外的下一有限reader可考慮既有清單的`1277920..1277F7B`（network-index／32-bit mask流程）；尚未開始該研究。

## 授權與確定缺口

前三次各一次的本機唯讀擷取均已使用。第四次EXE+1AE380限定擷取未收到明確答覆，`spawn_callee_live_20260927_1.json`仍不存在。不要把第三次同意當成新授權，也不要重問既有待答覆問題。沒有程序查詢、新capture、注入、遊戲修改或安裝授權的延伸。

目前尚不能安排五位玩家／五個帳號。平台加入、額外原生角色、所有客戶端同步、死亡／增援／重連／撤離／結算，以及八人負載仍缺真人驗收。Sidecar配置／發布／清理、完整reader集合、真實資源、callback期間狀態穩定、reject handlers、hook、Windows unwind及封裝也仍未完成。

## 移到新倉庫時的資料位置

目前workspace：`E:\File\Codes\0\26.10.1\HD2`。核心相關目錄至少包括：

- `eight_player_candidate_20260927`：候選、測試、合成產物與交付紀錄。
- `five_player_feasibility_20260927`：研究、固定證據、重播程式及全域計畫。
- `research_handoff_20260927`：保存capture reader等重播依賴。
- 本目錄：完整目標副本與暫停交接。

各研究可能引用其他既有工作目錄；此清單不是可刪除其他資料的白名單。保留使用者原有武器／治療手槍等無關工作。

原目標位於workspace外的Codex附件，已複製到本目錄。另有重播所需的原始capture仍在workspace外：

`C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438`

該capture的report/data SHA分別為`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`與`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。此次GitHub移交會將這兩份既有檔案逐byte複製至`evidence/existing-code-evidence-25480438/`；新環境依[SETUP](SETUP.zh-TW.md)使用倉庫內路徑。原始檔保持在原位置，沒有新增擷取。已保存的evidence內也有本輪完整函式及指定readonly bytes。

目前測試使用`C:\Program Files\Python312\python.exe`（Python3.12.10），Unicorn2.1.4／Capstone5.0.7位於候選目錄`.native-test-deps`。這些本機絕對路徑不是新機器已配置的證據；恢復時先依現有需求檔與可用runtime處理環境。

依使用者後續要求，已建立私人GitHub倉庫：https://github.com/cainiao524/hd2-eight-player-mod ，並準備保存八人研究與必要依賴。資料推送完成後的結果與資料提交編號會記錄於`UPLOAD_STATUS.json`，`STATE.json`的上傳欄位亦會更新。快照清單對應資料提交，狀態收據為後續提交；詳見[SETUP](SETUP.zh-TW.md)。研發保持停止，待使用者明確恢復後再接續。

## 可貼給新對話的接續指示

> 先讀`github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md`、`HANDOFF.zh-TW.md`與`STATE.json`，以實際檔案為準。完整目標仍是八帳號同任務全流程的可安裝Mod。先核對並收尾已實作但尚未正式發布的6054F0狀態更新候選，再按工作清單推進。前三次擷取授權已用完，第四次尚待答覆；不要自行存取遊戲程序或把離線通過當作多人成功。保留所有無關工作。
