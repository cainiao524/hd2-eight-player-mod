# 94BE10 玩家數 consumer：完整 body 的有限語義前提

## 1. 成品需求、決策與停止條件

本輪釐清 `94C9C0` 將限制於 1..4 的玩家數傳入 `94BE10` 後，該值究竟是索引、倍率、迴圈界限或資源資格條件。這決定八人 departure 配套是否需要擴充陣列，以及哪些數值／資源契約仍缺。

**結論：在完整 `94BE10` 中，玩家數只用作每筆來源 record 的 unsigned 最小／最大人數資格判斷；不是原生陣列索引、配置大小或權重倍率。** 1..8 可用相同指令比較，沒有函式內部硬編碼玩家上限 4。但是實際 record 的 `+F4/+F8` 邊界值尚未取得，也有明確 override 支線能跳過人數判斷。因此可以決定保留這個 consumer 的比較形式，不能單凭此結果把上游 clamp 改 8 後聲稱資源選擇或 departure 生命週期完成。

本輪停止於完整 body、既有 caller 的 15 個傳參點，以及判斷所直接使用的 record 位置。未展開 `94A0A0`、`949E10`、`177E3C0`、allocator 等無直接玩家數傳遞的 callee；未泛搜來源、未操作遊戲程序、未修改候選程式。

## 2. 固定來源

固定 capture 目錄：

```text
C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438
```

| 來源 | SHA-256 |
| --- | --- |
| capture-report.json | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| captured-data.bin | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| capture identity | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |
| 既有 departure_callee evidence／recheck | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |
| 完整 `94BE10..94C44A`，1594 bytes，359 instructions | `0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e` |

最後一列由既有 `inspect_capture.Image` 直接讀取並獨立解碼。完整範圍都是程式碼；末尾 `94C43E..94C44A` 是清零／跳回共用退出段，不能因前面已有 RET 而省略。

| Fragment（右端不含） | Unwind | SHA-256 |
| --- | --- | --- |
| `94BE10..94BEBC` | `247E8BC` | `35d06954b9ea75ea1d559c01747bd38d50547f9c1d33a0217431aecb764245b9` |
| `94BEBC..94C423` | `247E8D0` | `18be75dbc40f86bbef194b3b487cfc6bc79d8d0e72219a0d6e71feeea53b1e07` |
| `94C423..94C43E` | `247E90C` | `d5a7a37a76e2805ac9718760857fd12239059d542563ab20b284fbeb936d7170` |
| `94C43E..94C44A` | `247E91C` | `9820cb293211876f816bfab9b73da36d0e49f2b766e6aa2020faf19dc7f2df02` |

可重現方法：載入固定 capture 的 `Image`，核 `im.root(0x94BE10)`，僅沿上述四個已列 fragment 讀取；`im.read(0x94BE10,0x63A)` 必須匹配 body SHA，解碼須恰有 359 條指令並覆蓋全 1594 bytes。本文關鍵位點可逐一用 `im.instruction(RVA)` 重新核對，不需要全 capture scan。

## 3. ABI：玩家數與 tech level 是不同參數

設 `94BE10` 的 entry RSP=E。函式 push RDI、R13，再 sub RSP,108h，故 body RSP X=E−118h。CALL 本身還占 8 bytes；所以 caller 在 CALL 前的 `[RSP+38h]`，相當於 entry `[E+40h]`、body `[X+158h]`。

| caller CALL 前 stack 位置 | body 位置 | 已證用途 |
| --- | --- | --- |
| `+20h` | `+140h` | 輸出 record buffer，稍後每筆 stride D8h |
| `+28h` | `+148h` | 輸出數量 DWORD 的指標；entry 先清 0 |
| `+30h` | `+150h` | `tech_level`；由 caller ESI 對應的已存欄位傳入 |
| `+38h` | `+158h` | `num_players`；由 caller 經 clamp 的 EBP 傳入 |
| `+40h` | `+160h` | tag／selector 結構指標 |
| `+48h` | `+168h` | 可跳過部分正常資格檢查的布林輸入 |
| `+50h` | `+170h` | 選擇後段兩種權重計算分支的布林輸入 |

其餘主要輸入：RDX 保存為 R13 的來源／配置結構；R8 為來源 record array，R9D 為該 array 筆數。原 RCX 在 `94BE2D` 已被 stack 的輸出 count 指標覆寫，不能把它當持續的 roster S。

`94C9C0` 的 15 個固定 callsites 全部在該次 call 前以 EBP 寫 `[RSP+38h]`：

```text
94CC7A  94CCD3  94CD92  94CDDB  94CE24
94CE6D  94CEB6  94CF05  94CF54  94D03D
94D0DC  94D12A  94D1B6  94D204  94D252
```

這些 callsites 之中，`94CDDB` 明示將兩個布林 stack inputs `+48h/+50h` 都寫 1，其餘寫 0（第一個 call 用已清零的 SIL）。不得只驗所有 bool=0，便聲稱涵蓋既有 caller 的完整語義。

## 4. 玩家數的全部局部資料流

來源每筆 record 大小／遍歷步幅 `118h`。初始化 `94BEF4` 令 R15=R8+F0h；每轮尾端 `94C3AD` 加 118h。來源 record 起點 A=R15−F0h。

玩家數在 body 的唯一讀取是 `94C06E`，之後直接與該筆 record 的兩個 DWORD 比較：

```text
94C06E  8B 84 24 58 01 00 00    mov eax,[rsp+158h]  ; players
94C075  41 3B 47 04             cmp eax,[r15+4]     ; A+F4h min
94C079  72 0A                   jb 94C085
94C07B  41 3B 47 08             cmp eax,[r15+8]     ; A+F8h max
94C07F  77 04                   ja 94C085
94C081  B0 01                   mov al,1
94C083  EB 02                   jmp 94C087
94C085  32 C0                   xor al,al
```

因此 AL=`(min_players <= players <= max_players)`，兩個比較均 unsigned，包含上下界。這段沒有 clamp、乘法、count−1、陣列位移或記憶體寫入，也沒有把玩家數直接傳入 callee。

### 正常資格與 override

- `94C08E` 讀 body `+168h`；若非零且 `94C098` 的 SIL 為真，`94C09B` 直接跳到 `94C0BD` 接受此 record 的處理入口。
- 其餘走正常資格鏈，依序測 BL、CL、AL、DL。其中 `94C0AD test AL,AL / 94C0AF je 94C3A8` 才執行人數不符時跳過本筆 record。
- BL／SIL 來自該筆 tags 與 selector list 的原處理；CL 是 tech-level 範圍比較；DL 是前段計算得到的正權重判斷。這裡不把 SIL 簡化成「任何 tag 命中」，仍以保存的原迴圈結果為準。
- override 非零且 SIL 為真時，跳过的是整組 BL/CL/AL/DL 正常資格檢查，包含玩家數。不能把 `+F4/+F8` 說成無條件 hard gate。

接受路徑在 `94C0C2` 以輸出 count 重新寫 EAX；拒絕路徑在 `94C3A8` 以迴圈剩餘數重新寫 RAX。因此玩家數的暫存 EAX 在後續 calls 之前已被覆寫。完整 body 沒有其他 `[RSP+158h]` 讀取、該參數地址逸出或另一路 player-count 傳遞。

## 5. 鄰近的索引與容量不能誤認為玩家數

`94BEDC` 載入 R12D 的是 body `+150h` 的 tech level。後續 `94C1DB / 94C21A / 94C3A0` 重讀的也都是 `+150h`。其資料流包括：

- `94C034 EDX=R12D` 傳給 `94A0A0`。
- `94C05D / 94C063` 比較來源 record `+ECh/+F0h` 的 tech-level 範圍。
- `94C1E6` 以 EDX−1 形成索引，`94C1E9` 讀 `subrecord +30h + 4*(tech_level−1)` 的 float。
- `94C24B` 保存同一 tech-level−1 到 R14D，`94C26F / 94C2E3` 再讀相同 float 權重表。

這些 float 表不是 4-player 欄位。caller 既有 tech-level clamp 為 1..10，對應本地表取值窗口 `+30h..+58h`（右端不含）的十個 DWORD；該筆 subrecord 步幅為 80h。不能因本輪要八人而把這個 clamp／表改成八項。

其他界限也有不同來源：

- 最外層遍歷次數来自 R9D 的來源 record 數，步幅 118h。
- 多個 8 次內迴圈用於每筆 record 的 tag 或 12-byte 子條目，不表示玩家人數。
- 配置大小由 `[R13+8] * 4` 得到，為匹配 subrecord ordinal 的暫存索引列表；不是玩家數。
- 輸出每筆 stride D8h，由接受的來源 record 數累加。函式沒有本地 destination-capacity 參數／檢查；現有資料配置的有效性仍是 caller 契約，不能把更多 record 通過篩選當成已證明整體輸出容量安全。

本輪無須展開上述 callee，便可排除玩家數直接進入其算術／記憶體索引；這不宣稱那些 callee 的其他契約都已驗證。

## 6. 八人改動的具體判斷

| 問題 | 已證結論／仍缺來源 |
| --- | --- |
| `94BE10` 能否比較 player count 1..8？ | 能，使用原 DWORD unsigned 範圍比較即可；沒有 player-count 原生索引擴容需求。 |
| 5..8 能否選出正確資源？ | 未證。需實際生效來源 records 的 `+F4/+F8` 邊界、其建立／載入來源與資源意義。記憶體位址在 record 內並不證明保存值允許 5..8。 |
| 上游固定 clamp 4 是否仍需處理？ | 若要傳遞完整八人數值，`94CA30` 的 upper bound 4 必須有明示候選決策；目前仍把 5..8 折成 4，影響通知及全部 15 個 calls。 |
| 是否應把所有 record max 都改 8？ | 無此依據。每筆 record 可能用 min/max 分組；全面放寬可能啟用原本互斥的資源。需依有效資料選定規則。 |
| override 要否取消？ | 無此依據。已知 caller 確有 arg10=1 的路徑，需保留並測原選擇行為。 |
| departure pending／D=0 公式是否已解？ | 沒有。這個 consumer 不足以證明 `D−(n<D)` 或 0→1 clamp 是真實生命週期契約。 |

接下來若做局部候選驗證，應先以合成來源 records 對照 count 1..8、min/max 邊界、override 真／假與輸出選擇結果，證明完整原 consumer 不會讀取不存在的 player-index 欄位。這只能證明參數處理和選擇規則；真實資源資料、輸出容量、回呼不重入、pending 可達性及八帳號任務驗收仍分別需要證據。

本輪的停止條件已達：玩家數的完整局部用途已確定，與 tech-level 索引分離；已知可以保留原 consumer 的比較形式，下一個真正缺口是有效來源 record 的人數域／資源契約，以及上游 departure 計數語義。無須為此擴張無關 helper 樹。

## 7. 明示新候選政策：5..8 沿用原四人選集

目前已採用的[局部補丁候選](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)將 `94C9C0` upper clamp 由 4 改 8；`94BE10` 比較時只在 **max==4 且 min<=4** 時將 effective max 視為 8，min 與其他 max 保留，tech level 完全不變。兩個原位修改及 51-byte 跳板已完成[獨立 source 靜態審查](../eight_player_candidate_20260927/verification/native_player_count_review.zh-TW.md)。這是明示的新候選語義，不是對真實資產／平衡的發現；目前 source 沒有加入整批 profile 前置驗證或外層拒絕 handler。

在每筆來源 record 都符合 `1 <= min <= max <= 4` 的契約下，選集等價可直接成立：

```text
原 count=4 合格  <=> max=4                 （min 必定 <=4）
新 count∈5..8 合格 <=> effective_max=8      （min 必定 <=4）
effective_max=8 <=> 原 max=4 且 min<=4       （在本契約內 min<=4 必定成立）
```

原 count 1..4 的比較結果也保持。override 分支的條件不含玩家數，兩邊一樣略過 AL，所以不破壞上述等價。在其餘輸入、selector、flags、來源 bytes 與外部 callee 結果相同且穩定的前提下，可用完整原 body 的 count4 執行作為新 count5..8 的選擇／輸出 oracle；已選記錄、輸出量及 tech-level 計算應相同。上游 `num_players` 則按新政策保留真實 5..8 值，這個通知差異是刻意的。

**未驗 profile 不具普遍四人選集等價保證。** 原提案對 min=5,max=4 的空區間會使新 count5 意外通過；目前已採用的額外 `min<=4` 條件消除了這個反例，該筆會回到原 max 比較而拒絕。另一方面，min=1,max=6 仍保留原 range：原 count4 接受，新 count8 拒絕，這是保留其他 maximum 意義的預定行為，不能宣稱與原四人選集等價。未知 runtime assets 仍不能當作已通過上述 profile 契約，也不能藉由未整合的新 reject，把外部輸入縮小後稱為完整八人支援。

目前採用及未來整合的驗證範圍應分清：

1. 現有候選保留其他 ranges 的原處理，對合成或上游已驗證且受同步保護的有效 profile，承諾上述域內的等價；它不會把域外 profile 一律拒絕。
2. 若未來另增整批 profile 驗證，須在 `94BE4F` 首次寫輸出 count 之前乾式核所有 R8/R9 來源 records 的 F4/F8；這不是目前 source 已有的功能。拒絕仍需要 caller 契約。逐筆寫完後才拒絕不能宣稱無 partial state，下游拒絕也無法回復 `94C9C0` 先前已發生的通知與修改。

現有候選已保留原 raw count=0→1：原四格合成 dense T1/D1 departure 會傳 0，原 consumer caller 將它 clamp 到 1，沒有新增 `1..8` input guard 將它排除。現有候選對 raw count>8 仍走 upper clamp，並沒有拒絕入口；因此 pending D=0 產生 FFFFFFFF 時會轉為 8。其源頭契約仍未解，這個結果不能視作合理的八人數值或 pending 問題已修復。

因此目前政策**已作為局部候選實作**；沒有在完整 `94BE10` 中發現會使有效 profile 域內四人選集等價失效的其他玩家數用途。完整 body 指令驗證的具體範圍以候選文件為準；profile、穩定性、原零值 clamp 與 pending／外層生命週期界限仍須保留，不能把局部補丁及離線驗證當成可安裝或八帳號驗收完成。
