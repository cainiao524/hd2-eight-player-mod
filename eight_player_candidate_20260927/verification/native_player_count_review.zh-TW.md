# player_count 局部原生補丁計畫：獨立靜態審查

## 結果與範圍

**本輪未發現阻止採納此局部候選的具體 source／機器碼缺陷。** 這個结論限固定來源、兩处原位 bytes 與 51-byte 跳板；沒有認證執行中套用、Windows unwind、真實資產、同步生命週期或八帳號玩法。

本輪唯讀 source、固定 evidence 與保存 capture，獨立重新建置及解碼一組合成位址，核對完整原 body 的已知控制轉移與四個具體地址拒絕案例。未執行 Unicorn 套件、未修改 emitter、未操作遊戲程序。實際指令 oracle 另由主線／測試代理交付。

## 固定指紋

| 檔案／資料 | SHA-256 |
| --- | --- |
| `Native/player_count.py` | `d89b5cb7d8c6a574dbb4d1ef24346524c3a9d2cfeae36357a9bf8fd94967d8ab` |
| `roster_player_count_native_evidence.json` | `8f0fad49d9f5bc7e95ffe8735007b59c302034704707602c8d8093ad795676e3` |
| `roster_departure_callee_evidence.json` | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |
| 原 context `94C9C0..94D308` | `7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2` |
| 原 filter `94BE10..94C44A` | `0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e` |

兩個 body 均由 `load_sources` 驗證完整 JSON 指紋及完整 body SHA，再獨立與原 capture bytes 相等比較。capture 的 report/data SHA 分別為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`、`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。

## 1. 兩個原位切點及完整已知控制流

### Context upper clamp

`94CA30..94CA35` 原 `B8 04 00 00 00` 修改為 `B8 08 00 00 00`，仍為同長度 `mov EAX,imm32`。後面的 unsigned CMOVA 保留；原下限 1 邏輯也保留，因此 raw 0 仍轉為 1。

重新核對完整 context 的 467 條 code instructions、已列 local direct branches 及三張 RVA jump table：進此區段的已知局部分支是 `94CA27→94CA30`，沒有目標落入五 bytes 的內部。完整 unwind 範圍末尾的 jump table 不當成可執行指令解碼。

### Filter upper-bound splice

`94C07B..94C081` 原 bytes `41 3B 47 08 77 04` 為：

```text
cmp eax,[r15+8]     ; 4 bytes
ja  94C085         ; 2 bytes
```

六 bytes 整段改為 `E9 rel32` 加 NOP。重新核對完整 filter 的 359 條指令，沒有已知 direct branch/call 的目標落在 splice 內部。原前段 `94C075/94C079` 的 unsigned minimum check 保留；`94C079` 失敗仍直接到 `94C085`。沒有分割一條原指令，也沒有遺留原 `94C07F` short JA 作可達入口。

此控制流核對限完整已保存 body 和已固定 context tables；不聲稱排除了未知外部 computed entry 或遊戲執行中的非法跳入。

## 2. 51-byte 跳板與資料流

合成建置採 game base `180000000h`、trampoline `190000000h`。輸出恰為 51 bytes、10 條指令，code SHA：

```text
e4b78d6dfc472dea51d7b7d07f376b7f65c3194b72ff7ce44d4f582e682b15cc
```

| 跳板 offset | 指令／目的 |
| --- | --- |
| `+00` | CMP DWORD `[R15+8]`,4 |
| `+05` | JNE `+24h`，保留其他 maximum |
| `+0B` | CMP DWORD `[R15+4]`,4 |
| `+10` | JA `+24h`，保留 min>4 的原 maximum 行為 |
| `+16` | CMP EAX,8 |
| `+19` | JA 原 `94C085` 失敗點 |
| `+1F` | JMP 原 `94C081` 成功點 |
| `+24` | 原 CMP EAX,`[R15+8]` |
| `+28` | JA 原 `94C085` |
| `+2E` | JMP 原 `94C081` |

六個 branch 的解碼 target 與 metadata 全相符；內部 fallback label 是 `+36` 十進位，即 `+24h`。外部 continuation 皆以 game base+RVA 計算，使用實際 branch 結束位址計算 rel32；原位 E9 也以五-byte E9 結束點計算，尾部 NOP 不錯計入 next RIP。

跳板只有 CMP 和 branch，沒有 scratch GPR、XMM 使用、stack 存取、calls 或 writes。它只讀取原本已被原最小／最大比較使用的兩個 DWORD，未新增 record 外欄位。

### Flags 與 AL

跳板保留入口 EAX，讓成功點原 `94C081 mov AL,1` 或失敗點原 `94C085 xor AL,AL` 產生資格布林。兩路隨後抵達 `94C087 COMISS`，在任何後續條件分支前覆寫比較旗標。因此新增 CMP 所產生的 flags 差異不逸出該局部，且未破壞後續測 AL 的語義。fallback 路徑仍執行原比較。

原最低值判斷已在進跳板前完成。新增的 `min<=4` check 不會重新允許 min>max 的原空區間：例如 min=5,max=4、count=5 雖通過前段 minimum check，也會回原 maximum 比較而拒絕。其他 maximum 值全部保留原規則。重複讀取 min/max 的等價仍以記錄在該次處理期間穩定為前提。

## 3. 新語義及輸出宣稱

`policy` 明列：count clamp `[1,8]`、只有 maximum=4 且 minimum<=4 才延伸至 8、tech level 不變、原 override 保留。對 `1<=min<=max<=4` 的既有 profile，新 count5..8 可與原 count4 選集相等；程式沒有將此條件式證明擴張為所有未知 runtime records 的覆蓋。

以下限制均已在輸出保留：

- `installable=false`、`game_execution=false`、`multiplayer_verified=false`、`installation_plan=null`。
- 保存 source 指紋不表示已驗證載入中的 image。
- 需協調兩處補丁與跳板的套用／移除、處理 instruction cache 及適當 unwind。
- runtime records、資源、輸出容量與同步生命週期仍未知。
- 原 pending D=0 下溢為 FFFFFFFF 後會被新 clamp 轉為 8；元件不把這件事宣稱為已解決 departure。
- 跳板不是可獨立 CALL 的函式；入口契約為原 `94C07B` 狀態，已完成原 lower-bound check。

未見把本元件說成完整 departure emitter、平台加入補丁或八人實測成果的宣稱。

## 4. 位址與失敗檢查

`pointer()` 拒絕非整數／bool、低於 10000h、對齊不符，以及完整 extent 超出低 canonical user-space 上界的地址。game base 要 1000h 對齊，跳板要 10h 對齊。`IMAGE_SIZE=74727424` 已與固定 report 核對，跳板完整 51-byte extent 必須位於原 image 範圍外。

`rel32()` 逐次檢查正負 32-bit 範圍。獨立建置確認四個具體無效输入均拋出 ValueError：image 內重疊、過遠 rel32、跳板不對齊、末端跨 canonical 邊界。這些是建置器拒絕檢查，不是遊戲執行測試。

known regions 僅提供原 image 與跳板，並未宣稱此地址已配置、可執行、與其他模組無衝突。未提供的 Windows unwind、atomic patch/apply、真實 caller 與資產驗收仍是明確整合缺口。

## 停止條件與下一步

本輪已完成固定 source、局部切點、完整已知控制流、解碼結果、flags/live-state 與有限位址拒絕核對。沒有再展開 callee。下一個有意義的驗證是主線已安排的完整 body 指令 oracle：對照原 count4 與新5..8、原1..4／raw0、其他 maxima、invalid min>max 及 override 分支，並驗輸出／副作用的實際範圍。該測試仍不能代替 runtime 資產及八帳號驗收。
