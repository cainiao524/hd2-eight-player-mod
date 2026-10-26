# Registry 更新與關聯 ID 查詢的 HellForge 移植

2026-10-26。固定 HellForge SDK 13、遊戲 build 25480438。本次補上 `B54E00` registry 更新與 `606520` 關聯 ID 查詢，兩者使用既有 S 與八槽 B。程式碼與 Windows 例外還原資料皆來自保存的 capture；本次沒有啟動、檢查或讀取遊戲。完整八個獨立帳號同任務的目標保持不變。

## 實際改接範圍

`ep_registry_image.*` 產生可重定位的 C++ 映像。`B54E00` 的 tag 69 分支改接 B 的 property、pointer 與 aux 區，tag 73 使用同組 `606520` 主體。`606520` 的 property 遍歷與 pointer 讀取亦改接 B。關聯 entity ID 和 network index 是不同欄位；這裡不使用 `606AD0` 的 network-index 結果替代關聯 ID。

原 tag 2E、115、73 的其他操作、資源呼叫與間接回呼保留。tag 69 在首次名冊存取前要求 registry S、global S 和指定 S 相同，並檢查 `P≤D≤T≤8`。命中 property 後才檢查 pointer 非空、map 容量八、非 empty key，以及 map ordinal 在範圍內且等於 property 遍歷位置。這些拒絕是候選的新政策，不能當作真實 caller 已接受它們的證據。

| 入口 | 原始 bytes | 移植映像 bytes | 回溯記錄 | 加上共同入口後 bytes / 記錄 |
|---|---:|---:|---:|---:|
| `B54E00` registry 更新 | 873 | 1,836 | 4 | 1,884 / 5 |
| `606520` 關聯 ID 查詢 | 271 | 488 | 3 | 536 / 4 |

## 共同切換與存取範圍

`ep_roster_group.*` 現在準備十七入口。原十二入口編號保持不變，新增 `EP_ROSTER_REGISTRY_UPDATE=13` 和 `EP_ROSTER_ASSOCIATION=14`。registry 的內部查詢連到同組 association 的 `base+32` 主體，使用同一 S/B；十六次發布全部成功後才允許提交共同開關。

選擇 `prepare_owned` 時，兩個新入口的完整舊路徑與新路徑都進入既有 owner。registry 按 writer 處理，association 查詢按 reader 處理；後者不自行增加名冊 revision。registry 內部的 association 呼叫沿用外層保護。權威身分來源、真實排空、失敗策略與生產初始化仍須由整合者實作，沒有自動綁定或遊戲發布。

## Windows 例外還原

registry 的原始條件式保存使用 chained unwind。移植保留完整三段來源覆蓋，並為拒絕尾段建立相應的已保存暫存器狀態。拒絕原因先寫入 R10D，再還原非易失暫存器和堆疊，讓 `ADD RSP / POP / JMP` 保持 Windows 可辨識的尾段。association 的入口 guard 與末端拒絕各使用獨立的 leaf metadata，原函式主體使用自己的還原資料。

共同入口增加 32 bytes 時，同時調整函式表及 metadata 內的 chain parent 三個 RVA。程式碼所有者目前因離隊獨立映像擴展而接受最多十五段；這裡的 registry 共同入口仍使用五段，每段維持獨立的 metadata，重複引用仍拒絕；chain parent 必須完全等於同表中較早的一筆。拒絕循環、向後續紀錄引用、表外 parent、語言 handler 和不支援的 flags。這只適用目前有來源及測試的格式。

## 驗證與邊界

[專用收據](evidence/native-registry-validation.json)記錄 8 個原有方法、87 次頂層保存指令執行、63 項參數/配置拒絕檢查與 3,963 個 Windows 還原現場。原四槽基線和新八槽路徑都保留；歷史十五函式 bundle 的完整比對仍獨立使用原 builder，沒有修改舊 golden file。另測實際配置、封存、註冊、查詢、釋放、封存失敗和清理重試，並拒絕循環/向後續紀錄的 chain 等錯誤 metadata。

功能測試的 tag 69 `FD9BA0` 使用保存的真指令；其他 tag 的 opaque calls 仍是明示參數、順序與副作用的替身。完整映像只在 Unicorn 執行。Windows 原生測試只執行自己的普通測試函式，以及對不可執行映像呼叫 `RtlVirtualUnwind`，沒有原生執行遊戲函式。

[十七入口收據](evidence/roster-gate-validation.json)與[引擎總收據](evidence/engine-roster-validation.json)另外記錄共同開關、內部 helper、發布/封存失敗、owner 與關閉場景。精確檢查數量以本輪收據為準。

仍有以下實際限制：

- tag 69 或後續 registry entry 拒絕之前，較早 entry 可能已回呼或改動外部物件，沒有整體回滾。
- 其他 context map 的 backing、容量、missing 與 empty-key 契約尚未被 roster guard 證明。
- 實際 caller/外部 helper ABI、回呼期間全體 writer 的覆蓋與鎖順序仍待核對。
- departure、其他 roster consumer、角色建立/控制、其他固定四槽容器及完整容量交易仍未全部接通。
- 尚未進行五至八個真實帳號同場任務、戰鬥、死亡增援、離開重連或撤離結算驗收；本研究包不可安裝，亦不是可用八人 Mod。

重現使用總交接中的兩個離線建置命令。單獨驗證可在建好 `build/property_image_test.dll` 後執行：

```powershell
py -3.12 -B hellforge_multiplayer/tools/validate_registry_images.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

舊的 PID / 64 KiB 一次性採樣授權不延續；新遊戲存取仍需新授權。
