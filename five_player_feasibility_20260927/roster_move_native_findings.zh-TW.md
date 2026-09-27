# P3：roster `60C410` 四陣列搬移的原生候選

## 完成範圍

[Native/roster_move.py](../eight_player_candidate_20260927/Native/roster_move.py) 產生完整 `60C410` 函式的 x64 clone，將其**指標、`70h` 紀錄、`38h` 紀錄與 `20h` property** 四組搬移一同導向八槽 sidecar。保持原來源→目的 copy 次序與原 S 中的 entity ID→ordinal map 修正。這是離線機器碼資料產生器，沒有配置記憶體、安裝 hook、登錄 Windows unwind、執行遊戲或驗證多人任務。只改這個 mover 仍不可啟用八槽 roster；其餘插入、壓實、分類、移除與讀者須改接同一 sidecar。

本函式確定的同一物件記作 `S=roster_address`，八槽 sidecar 起點記作 `B=storage_address`。新的 property 起點是 **`B+580h`**；既有 producer／receiver 候選必須收到這個地址作為它們的 `property_address`，才能與 mover 改接同一批記錄。

## 固定來源與原生契約

來源是 Steam build `25480438` 保存 capture：`capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`、`captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，capture identity `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。[完整 evidence](roster_move_native_evidence.json) 保存 `move.instructions` 的全部 78 條 RVA、bytes、每條 SHA，以及 CFG、三個 chained unwind fragments、位移修補清單。原 body `[60C410,60C5BE)` 為 **430 bytes／78 條**，SHA-256 `b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b`。五條內部條件分支的目的地都在此 body 指令邊界；沒有外部 RIP-relative memory 或 call，clone 不需外部 rel32 relocation。

入口 ABI：`RCX=S`、`EDX=目的 ordinal`、`R8D=來源 ordinal`。原 `C410 cmp r8d,edx`／`C413 je C5BD` 在低 32 bits 相同時直接返回；候選**原樣保留**，即使相同值超過 7 或 S 不匹配，仍不讀寫 S／sidecar、也不進入新 guard。不同值才到 `C419`。原四組搬移的順序是：`C438/C440` 複製指標、`C44B..C4C9` 複製七個 16-byte 的 `70h` 紀錄、`C4D9..C516` 複製 `16+16+16+8` bytes 的 `38h` 紀錄、`C51F/528/531/53A` 複製兩個 16-byte property，然後 `C543..C5B7` 讀目的 slot 的 entity 指標並修其 map ordinal。

## 八槽布局與機器碼改接

| sidecar 範圍 | 每筆 stride | 原內嵌範圍 | 原主要基址 |
|---|---:|---|---|
| `B+[000h,040h)`：8 個指標 | `08h` | `S+E8h` | RCX／R11 |
| `B+[040h,3C0h)`：8 個 primary | `70h` | `S+108h` | RCX |
| `B+[3C0h,580h)`：8 個 aux | `38h` | `S+2C8h` | RBX |
| `B+[580h,680h)`：8 個 property | `20h` | `S+3A8h` | RBX |

第一個切點 `C419` 的原五 bytes 是 `48895c2420`（`mov [rsp+20h],rbx`），完整替成 `E9 rel32`。在 original equal fast return 後、原 prologue 保存及首次 mutation `C440` 前，trampoline 依序對目的 EDX、來源 R8D 做 unsigned `<8` 檢查，再要求 RCX 等於預期 S。成功時把 RCX 設為 `B−E8h`，重播原 `C419` 指令並回 clone `C41E`。隨後原 `C420 mov rbx,rcx` 使 RBX 暫時也採同一偏置。原指標讀寫的 `+E8h` 位移不變；`C430` 的 R11 目的地址與 `C543` 的目的指標讀取因此也都落在 sidecar。

Clone 中只重算固定 26 個終端 disp32，指令長度不變：14 個 primary 指令的位移 `+20h`、8 個 aux 指令 `+1E0h`、4 個 property 指令 `+2C0h`。例如新 primary `+128h` 配合 `B−E8h` 得到 `B+40h`，新 aux `+4A8h` 得到 `B+3C0h`，新 property `+668h` 得到 `B+580h`。最後一筆 16-byte property 讀寫到 `B+680h` 的不含端點。每個原 disp32 與整體 source SHA 在產生前都經固定檢查；全部 26 個修改的 RVA／原值／新值保存於 evidence 與 emitter 輸出。

第二個切點 `C54A` 的原七 bytes 是 `448b9bd8000000`（`mov r11d,[rbx+D8h]`），替為 `E9 rel32 + 2 NOP`。`C543` 已用偏置 R11 從 sidecar 取出移動後的 entity 指標；第二 trampoline 在**第一次 map 欄位讀取前**把 RBX 恢復為原 S，重播 `C54A`，回 clone `C551`。因此後續 `+D0/+D8/+DC/+E0` map 查找與 `C5B7` 更新 ordinal 仍以原 S 為基址。原 epilogue 從 stack 還原 RBX 等非揮發暫存器。兩處切點不改 body 內部其他 branch 位移。

## 拒絕、原副作用與必要前提

`reject_address` 必填；沒有回退到原四槽或合成正常返回。不同 ordinal 路徑的拒絕 reason 依序是 R10D `1`：目的不在 `0..7`；`2`：來源不在 `0..7`；`3`：入口 RCX 與預期 S 不符。三者都在 `C419` 原 prologue 指令**執行之前**進入 reject，因此 RSP 與全部非揮發暫存器仍是原入口狀態，沒有讀取陣列／map，也沒有本 mover 的 stack 或共享資料寫入。RCX 仍是原輸入 S，EDX／R8D 仍是兩個原 ordinal；reason 3 的 RAX 已變成預期 S，不能視為原 RAX。整合者須提供會診斷並終止整個上游操作的 continuation，本候選不決定該操作的安全恢復語義。

**成功 guard 不能證明 map 有效。** 原碼在完成四組 copy 後，若 map count 為零或查找耗盡，`C5A0` 會把 R8 設為零，`C5B7` 仍寫 `[R8+4]`。候選保留這一段原行為；有效 entity 指標、map backing、對應 entry 與適當 map 容量是啟用前提，不能把 null-map 路徑說成成功或安全拒絕。四組 sidecar 也必須先由有效來源初始化或搬移，保留活記錄的 opaque bytes 與原指標；不能把整片清零當作原生可用八格。配置、綁定世代、並行存取、外部 aliases、其他插入／刪除／分類路徑與 Windows unwind 仍未閉合。

## 重播與驗證狀態

[重播程式](roster_move_native_replay.py) 只讀上述保存 capture，固定 430-byte body、78 條指令、三個 fragment、完整 CFG、兩個切點、26 個位移修改與所有原指標 site。從工作區根目錄以尚不存在的輸出檔名重跑：

```powershell
python -B five_player_feasibility_20260927/roster_move_native_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-roster-move-native.json
```

正式 evidence 與[同來源 recheck](roster_move_native_recheck.json) SHA-256 均為 `115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242`；replay SHA-256 `e09468e6e3da6ab80e505c52287273ef530d7646467a501ccbe92480d54bde1c`；emitter SHA-256 `cc6df86a567fda45fcac9a258372df52aad085fff67a620b5f4a2d46c100c23f`。離線合成地址輸出為 545 bytes，Capstone 已確認原 equal branch、兩處 E9 splice、trampoline guard／replay／回跳，示例 code SHA-256 `0764b7277cca27d7b9638e018151c16a8dd4dd4c57ff22ed9d1ef8768016a1a9`。

主線的[Unicorn 測試報告](../eight_player_candidate_20260927/verification/native_roster_move_tests.json)記錄 **11 組、103 次 x64 模擬執行全部通過，零 failure／error**：64 組來源／目的八槽組合、原四槽對照、低 32-bit ordinal、相同值早返、三種前置拒絕、兩 splice／26 位移、非揮發 GPR／XMM 與 stack、原 copy 順序／整頁資料變化，以及 producer→mover→receiver 的合成資料橋。測試對 Unicorn 將 16-byte MOVUPS 寫入拆成兩次 8-byte hook 的行為，以精確有序 byte-address stream 比對；沒有把 hook 事件寬度誤當指令寬度。測試 source SHA-256 `603259862dcc109b0be9c3227954ff771342fbfd416eb71eb9f0687e770bb687`，結果 JSON SHA-256 `42022b52384a82f7c8108f86c8ac253dbc6d542c8205e0a586c2af3325eff659`。另一代理從固定 capture 獨立核了四陣列 operand、改寫位移、兩切點和 map restore，未發現局部靜態缺陷。這些仍是合成記憶體的離線驗證；實際 sidecar 初始化／生命週期、Windows unwind、hook 與多人遊戲未驗證。
