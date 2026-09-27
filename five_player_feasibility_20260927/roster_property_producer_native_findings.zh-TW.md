# P3 roster property producer：完整原生 clone 候選

## 本輪交付與界限

在保存的 Steam build `25480438` 擷取中，`60C77D` 只是 network index 欄位的 store；真正函式入口是 **`60C640`**。本輪新增 [完整 body 證據](roster_property_producer_native_evidence.json)、[可重播讀取器](roster_property_producer_native_replay.py)與 [x64 emitter](../eight_player_candidate_20260927/Native/roster_producer.py)。Emitter 使用與既有 roster receiver 相同的 `roster_address`、`property_address`、八格容量與 `0x20` stride，在 `60C6C9` 增加容量／綁定 guard，然後讓原八次 property store 寫向 sidecar。

這是**單一 producer 的離線機器碼候選**，並未安裝、hook 或操作遊戲程序。其他 roster 插入、搬移、分類交換、移除與讀者仍須改接同一份 storage；不能把 producer 與 receiver 候選單獨啟用，也沒有五至八人的遊戲結果。

## 固定來源、完整函式與 ABI

固定 capture 的 `capture-report.json` SHA-256 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，`captured-data.bin` 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`；capture identity 是 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。已保存 unwind 表給出單一 producer fragment **`[60C640,60C882)`**，578 bytes、130 條完整指令，body SHA-256 `8b9a20e5207ae395e99e45f153cba1994ff50c10cb258101fd16a74285824c34`。130 條都從入口可達；七條內部 branch 的目標都是本 body 的指令邊界。

已證 wrapper `[540AE0,540B03)` 在 `540AF9` 直接 `call 60C640`；wrapper body SHA-256 `237b7b9c16901d17b8837023007058479291f72f7d35ed2caa8a4a9c4ff6516c`。Callee 的 RDX 是 entity record，R9 是 descriptor output array，stack 第五參數是 count pointer，第六參數是 allocator pointer。入口 RCX **不是**此函式選取 roster 的來源；`60C667` 從 global `[game_base+3326468]` 載入 roster S 到 RBP。後續用 entity record `+8` 的 ID 在該 S 的 map 找 roster ordinal，命中值進入 EBX；miss 是 `FFFFFFFF`。

函式原本先在 `60C6DA` 透過外部 allocator 配 32 bytes，再建立八組 `{hash,type,pointer}` descriptors，並把初始值同時寫入 buffer 及 `S+ordinal*20h+3A8h` 的八個 DWORD。第四欄由 `60C778 call 134F190` 取得本地 network index，寫到 property 的 `+0xC`。這是**單一 entity 的八個屬性**，不是八人容量。`134F190` 的完整已證 leaf `[134F190,134F1EC)` 不使用 RBP；leaf body SHA-256 `a87faad9809cfc17449641152c938f42b5063daf33cf506360d93d6e1eb976f9`。外部 allocator 及 helper 仍須按其已核對 ABI 正常返回，且保留 Win64 非揮發 RBP。

## 切點與 sidecar 映射

`60C6C9` 原指令 `488b4c2468` 是完整五 bytes 的 `mov rcx,[rsp+68h]`，指令 SHA-256 `8e2e13e1c76aeb7efa01b2baa2bbc5a07ca0326480b6a65c284aa98d929fb5f0`。此處可用一條 `E9 rel32` 替換；emitter 在 trampoline 成功路徑重播原指令，跳回 clone 對應 `60C6CE`。CFG 中移除 `60C6C9` 後，`60C6DA` allocator 與所有八個 property store 都無法由入口到達；晚期 `60C87D` 的內部回跳也正是 `60C6C9`。因此 guard 會在首次 allocation、descriptor、count、output-buffer 或 property 寫入之前執行。

切點時 EBX 是零延伸的 uint32 ordinal，RBP 是原 global roster，EAX 仍為 entity ID；RAX 在原成功路徑到 allocator 返回前沒有被讀。附加程式以 unsigned `cmp ebx,8; jae` 拒絕 `FFFFFFFF` 與所有 `>=8` 的值；接著用 RAX 暫存預期 `roster_address`，比較 RBP，再將 RBP 改為 `property_address−3A8h`。這裡比對的是實際 global 載入的 roster，而非未用的入口 RCX。成功路徑重播 `mov rcx,[rsp+68h]` 後進入原 allocator 呼叫；RAX 隨後由其回傳 buffer 覆寫。

原八筆 store 的目的地因此成為 `property_address + ordinal*20h + [0,4,8,C,10,14,18,1C]`。第七筆不是直接 `+3C0h` 的形式：`60C7FF/C803/C807` 算出 `(ordinal+1Eh)*20h+RBP`；代入偏置 RBP 後仍精確等於 sidecar `+ordinal*20h+18h`。原 buffer、descriptor、count 的建構順序、正常 epilogue 及 caller ABI 不另改寫。

| 原 RVA | 原 bytes | 類型／原目標 RVA | clone 必要動作 |
|---|---|---|---|
| `60C65E` | `3b05bc75e702` | RIP memory → `3483C20` sentinel | 重算 disp32 |
| `60C667` | `488b2dfa9dd102` | RIP memory → `3326468` roster global | 重算 disp32 |
| `60C6DA` | `e8f1f11201` | direct call → `173B8D0` allocator | 重算 rel32 |
| `60C778` | `e8132ad400` | direct call → `134F190` index helper | 重算 rel32 |

完整 body 唯有這四個外部相對參照。Emitter 對每條原 bytes 與整體來源 SHA 作固定檢查，四處都檢查 signed rel32 可達；整體 clone 保持原指令 offset，七條內部 branch 的位移原樣保留。`60C6C9` 的 E9、成功返回及 reject 入口也逐一檢查 rel32 範圍。地址必須是明確提供的 low canonical 值；配置、權限、實際 game image 指紋與物件存活並非 emitter 所能證明。

## 拒絕入口及尚未完成的原生契約

`reject_address` **必填**，沒有舊四槽 fallback 或假裝成功的預設返回。reason 1 是 ordinal 不在 `0..7`，reason 2 是 RBP roster binding 不符，均以 R10D 傳給 continuation。兩者在 `60C6C9` 的內部 frame：`RSP=entry_rsp−38h`；`[rsp+20h/+28h/+30h]` 分別保存 R15／R14／RDI，`[rsp+40h/+48h/+50h]` 保存 RBX／RBP／RSI。RBX 仍是 ordinal，RBP 仍是原 roster，R14 是 descriptor array，R15D 為零。reason 1 時 RAX 是原 entity ID；reason 2 時 RAX 已是預期 roster 位址。

拒絕之前已執行 prologue stack 保存、entity record ID、global roster 與 map 的讀取；**尚無 allocator 呼叫或上述 output/property 寫入**。Guard 位於 map lookup 後，不能保護壞 entity、roster、map backing pointer 的較早讀取。整合者必須提供能正確恢復此 frame、診斷並終止本次完整 property stage 的 continuation；目前沒有證據允許直接 `ret` 或自行略過這個 producer。Clone／trampoline 的 Windows unwind、執行頁配置、hook 原子性、sidecar 建立／釋放及與 receiver 和其他讀寫者的同步仍需完成。

主代理另完成[來源與 CFG 核對](roster_property_producer_native_review_checks.json)；另一代理已獨立審查四個 relocation、RBP 偏置後的八個 stores、R11 保留及測試界限。詳細紀錄與共同建置候選見[審查文件](../eight_player_candidate_20260927/verification/native_roster_producer_review.zh-TW.md)及[產生／接收共同契約](../eight_player_candidate_20260927/NATIVE_PROPERTY_PAIR.zh-TW.md)。

## 可重播檢查

從工作區根目錄，以**已保存** capture 路徑執行；輸出檔名必須尚不存在：

```powershell
python -B five_player_feasibility_20260927/roster_property_producer_native_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-roster-property-producer-native.json
```

正式 evidence 與同來源 [v2 recheck](roster_property_producer_native_recheck_v2.json) 的 SHA-256 均為 `f73ec903d06f2304f4f944c25e011a7ef86d78737cb1b197101a1c96daaabacb`；replay SHA-256 為 `74fd3c2ecfd295843cc8149f6cf4ed66d3c1dfbefa218219650ca450eb6ff54d`。固定證據含全 130 條的 RVA、bytes、每條 SHA、完整 CFG、四處 relocation 和直接 caller pin。Emitter 檔 SHA-256 為 `015b2240847019bfb62fa62a72ce8af93894f2d61b0369d5079aa40d40697a4b`。

Emitter 用合成明確地址離線產生 662-byte code；Capstone 已核四處外部目標、切點 E9、trampoline 分支及成功返回目標，示例 code SHA-256 `7f41581cb50bfecd9bcee1aece8f4f4ac449b904863f8201f6ee77e857d527a6`。另一代理的 [Unicorn 實際指令測試](../eight_player_candidate_20260927/verification/native_roster_producer_tests.json) 已有 **10 組、54 次 x64 模擬執行通過，零 failure/error**，包含兩組 ASLR、ordinal 0–7、原版與候選對照、保存的 `134F190` leaf、allocator 的 Win64 volatile clobber、超界／binding reject、四 relocation 的邊界，以及 producer descriptor 與 receiver 的同 S／跨 S 合成資料橋。測試檔 SHA-256 `68b6d7573c219a977903e345e67fa24792e852ef234392da12c4f4ad312e7fe7`，結果 JSON SHA-256 `3176b9e9e5b4cd59ca609fe810f6d3cc69e208a56991d4ee7d1b08370203a642`。這些只是保存指令與合成記憶體的離線結果，沒有驗證 Windows unwind、hook、並行生命週期或多人任務。
