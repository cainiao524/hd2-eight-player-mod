# 八格名冊：完整記錄搬移與共同建置

## 交付狀態

`0.6.0-offline` 新增 [roster_move.py](Native/roster_move.py) 與 [roster_bundle.py](Native/roster_bundle.py)。前者產生 545-byte x64 搬移候選；後者讓既有 producer、receiver 與 mover 使用同一個原名冊 S，以及同一份八格儲存 B。三段程式各自保留版本指紋、拒絕介面與固定原指令檢查。

**這是可重現產生的機器碼資料，尚無可安裝的八人 Mod。** 沒有配置遊戲記憶體、建立或搬移活名冊、安裝 hook、登錄 unwind 或進行遊戲／多人測試。目標仍是八個獨立帳號的完整任務驗收。

支援研究 profile 為 Windows x64 Steam build `25480438`。EXE SHA-256 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`；game.dll SHA-256 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。這是固定來源目標，尚非經八人實測的相容聲明。

## 為什麼四組資料要一起搬

玩家的名冊 ordinal 可能因離隊、壓實或分類改變。原 `60C410` 依序複製 entity pointer、`70h` primary、`38h` auxiliary、`20h` property，再更新原 S 的 entity ID→ordinal map。只搬 property 會讓同一個槽位的四組資料指向不同玩家。

本候選將四組陣列完整改接，保留原 copy 次序、來源 bytes、map key 與 counts；最後將搬入 entity 的 map value 設成目的 ordinal。這段 helper 不清除舊來源、不移除目的舊 key、不改 counts，也不完成整個離隊或壓實流程。

| B 中的陣列 | 起點（十六進位） | 每筆大小 | 八筆總大小 |
|---|---:|---:|---:|
| Entity pointer | `0` | `8h` | `40h` |
| Primary state | `40h` | `70h` | `380h` |
| Auxiliary | `3C0h` | `38h` | `1C0h` |
| Property | `580h` | `20h` | `100h` |

總長 `680h`，即 **1,664 bytes**；B 必須 16-byte aligned。Producer 與 receiver 的 `property_address` 固定等於 **B+580h**。共同建置器會檢查完整儲存區、三段候選 code、三個拒絕入口、原函式及有限已知 global/helper 區域的交疊；這些檢查不代表輸入地址已實際配置。

## 指令變更與拒絕契約

固定原 mover 共 430 bytes／78 指令。新候選保留原函式內指令位置，改動限 26 個陣列 displacement，以及 `C419`／`C54A` 兩個完整指令切點。前者在第一次資料存取和 prologue 寫入之前檢查兩個 ordinal 與 S 綁定，成功後以新基址搬資料；後者在讀 map 前恢復原 S。完整來源與 CFG 見[原生證據](../five_player_feasibility_20260927/roster_move_native_findings.zh-TW.md)。

原入口為 `RCX=S、EDX=目的 ordinal、R8D=來源 ordinal`。當兩個 ordinal 的低 32 bits 相等時，原直接 RET 路徑保留，不檢查 S 或上界、不讀陣列；RET 仍會讀返回地址。不同時才檢查：

| R10D reason | 拒絕原因 |
|---:|---|
| 1 | 目的 ordinal 不在 0..7 |
| 2 | 來源 ordinal 不在 0..7 |
| 3 | RCX 與預期原 S 不符 |

三者均保留入口 RSP 與非揮發暫存器，沒有本 mover 的資料或 stack 寫入；RCX／RDX／R8 保留，reason 3 的 RAX 已用作預期 S。整合者必須提供終止上游操作的拒絕處理。Producer 與 receiver 在拒絕時已建立不同的 stack frame，不能將三個入口隨意接到同一個普通 RET；前兩者的契約見[產生／接收文件](NATIVE_PROPERTY_PAIR.zh-TW.md)。

**有效 map／entity／caller 狀態是成功路徑的前提。** 原函式在四組 copy 後才查 map；capacity=0 或 full-map miss 可能導致寫 `[4]`，命中空 bucket 亦不會插入 entity key。新 ordinal／binding guard 沒有處理這些既有失敗情況。不得在未維持 map membership 與有效來源 entity 時啟用本 helper。

## 實際離線驗證

[測試報告](verification/native_roster_move_tests.json)的 11 個測試方法通過，共 103 次 x64 模擬執行：

- 八格來源／目的全部 64 種組合，逐 byte 比對所有非 stack 記憶體頁、四組目的記錄、原來源保留及 map 更新。
- 原四格布局的 16 種組合，核對原行為；沒有把原四組 inline 陣列假裝成可容納八筆。
- 高 32-bit 雜訊與第二組 ASLR、相等 ordinal 的無資料存取返回、超界與錯誤綁定拒絕。
- 所有非揮發 GPR／XMM 與正常 stack 恢復；三條拒絕跳轉共同 rel32 範圍的兩端。
- 指令改動範圍、完整 sidecar 與跨程式區域碰撞。
- 實際執行 producer → mover → receiver：entity 17 的 ordinal 從 7 搬至 2，map 隨之改為 2，接收端把新的 32-byte property 寫到槽 2；network index 仍為 4，槽 7 原來源保留。

最後一項使用合成記憶體、成功 allocator 契約及人工提供的 incoming payload，沒有真實 serializer 或網路傳输。測試先前的 SSE hook 粒度不符已修正，詳見[審查紀錄](verification/native_roster_move_review.zh-TW.md)。

## 可重現方式

在工作區根目錄，已有 [native test 依賴](requirements-native-tests.txt) 時執行：

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/tests/test_native_roster_move.py
```

以下命令只在工作區產生 JSON，所有地址都是合成範例。輸出檔名須尚不存在；已保存的結果見[共同建置範例](verification/native_roster_bundle_synthetic.json)。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 eight_player_candidate_20260927/Native/roster_bundle.py `
  --move-evidence five_player_feasibility_20260927/roster_move_native_evidence.json `
  --producer-evidence five_player_feasibility_20260927/roster_property_producer_native_evidence.json `
  --receiver-evidence five_player_feasibility_20260927/roster_property_receive_evidence.json `
  --game-base 0x7FF600000000 --roster-address 0x18200100400 --storage-address 0x18200800100 `
  --move-code-address 0x7FF610040000 --producer-code-address 0x7FF610000000 --receiver-code-address 0x7FF610020000 `
  --move-reject-address 0x7FF610048000 --producer-reject-address 0x7FF610004000 --receiver-reject-address 0x7FF610024000 `
  --output NEW-roster-bundle.json
```

CLI 與純 bytes 建置不需要執行遊戲。本資料夾沒有遊戲安裝或移除步驟。

## 接入前的確定缺口

1. **初始化與生命週期。** 原名冊 constructor 沒有初始化全部四組記錄；部分加入分支跳過 primary 清零，auxiliary 還有非零預設欄位。不能把全零的 680h 儲存視為原生可用名冊。活記錄須保留完整 opaque bytes，新增槽須完成對應路徑初始化後才發布。詳見[初始化前提](../five_player_feasibility_20260927/roster_move_native_prerequisites.zh-TW.md)。
2. **其餘讀寫者。** 插入、壓實、分類、移除及其他讀者仍需改接同一四組陣列；各自 count／map 更新與 ownership 必須一致。
3. **執行整合。** 配置、搬移、發布、清理、外部 aliases、引擎同步、三種 reject frame、Windows unwind、版本檢查與可恢復 hook 尚未實作。
4. **完整八人條件。** 平台加入、第五人角色建立與其他玩家元件仍有缺口；四人基線及五至八人任務驗收均未通過。

四條插入的局部候選已於 [0.7 插入契約](NATIVE_ROSTER_INSERT.zh-TW.md)完成；下一個離線實作切點為壓實，再接分類／移除。已核合的 mover 指令可停止重查，除非來源版本、依賴或新風險改變。
