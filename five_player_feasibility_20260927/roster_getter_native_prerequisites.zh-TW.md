# Roster network-index getter：原生前提與八格改接切點

## 成品需求、決策與停止條件

本輪解決八格 roster 在移動／分類／移除後，仍能由 entity ID 找到更新後的 ordinal，並從共用 property sidecar 讀回同一 entity 的 **network index**。它不是把 ordinal 當 network index，也不是增加 DWORD 的寬度。

實作決策是保留 `606AD0..606B75` 的原 lookup，於 `606AF3` 增加早期 binding guard，再於已找到且非 `FFFFFFFFh` 的 ordinal 路徑、`606B67` 的 property 讀取之前增加有限 guard，把唯一 property operand 指向共用 B。global-invalid-ID 仍保留原 missing return；其他 ID 的 binding mismatch 新拒絕會優先於普通 map miss。停止條件是完整 body、ABI、map 查找順序、missing 分支及單一 property 讀取核完；本輪不新增全 capture caller scan、不擴 callee，也不操作 live 程序。下一步是固定 bytes emitter 與分類換位後的合成 getter oracle。

## 固定來源

透過 `research_handoff_20260927/indirect/inspect_capture.py` 的 `Image` 驗證既有 capture，再完整解碼：

| 項目 | 固定值 |
| --- | --- |
| 完整範圍（end exclusive） | `606AD0..606B75` |
| bytes／instructions | 165／43 |
| unwind | 單一 fragment，`2424C2C` |
| body SHA-256 | `96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb` |
| capture report SHA-256 | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| captured data SHA-256 | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| capture identity | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |

既有 `roster_index_usage_evidence_v2.json` 的 `roster_map_direct_index_getter` 已固定 `606AE4..606B75`，block SHA `09ae2c62ef595d0eebcd7641688b644910f03a0ba608fcd0fecaaf48ef1db1e1`；本輪補核其入口四條保存指令，沒有把局部 block 冒充完整 ABI。`roster_property_consumers_native_inventory.json` 也將此 root 列為同 S 的必要 reader。本輪未以新 caller 掃描補推實際遊戲可達性。

## ABI 與讀取順序

**EDX 是 raw entity ID，不是 entity pointer。** RCX 不用作 roster S。`606AEA` 從 `[game+3326468]` 載入 R10=S。

入口 `606AD0/AD5/ADA/ADF` 將 RBX、RBP、RSI、RDI 保存到 `[entry RSP+8/+10h/+18h/+20h]`。全 body 沒有 push／sub RSP、沒有 call 或 allocator。正常結尾 `606B45..606B54` 恢復這四個 nonvolatile registers，`606B59` RET。只讀 roster／map／property；原本有上述四筆 caller shadow-space 寫入。

原查找依序為：

1. `606AE4`，bytes `3b1536d1e702`，比較 EDX 與 global `[game+3483C20]` invalid ID。
2. `606AEA`，bytes `4c8b1577f9d102`，讀 global S 指標；這個 MOV 保留前面比較的 flags。`606AF1` 若 invalid ID 相等，直接走 missing。
3. `606AF3` 讀 map capacity=`[S+D8h]`；`606AFC/B03` 讀 `[S+E0h]` multiplier，做32-bit `multiplier*ID`。`606B06` 形成 capacity−1 mask。
4. `606B0A/B0D` 對 capacity=0 走 missing。此時已讀 S 的 capacity／multiplier，但沒有讀 bucket backing pointer 或 bucket。
5. `606B0F/B16` 才讀 `[S+D0h]` bucket pointer、`[S+DCh]` empty key。每次 probe 以 `((hash+probe) mod 2^32) & (capacity−1)` 找8-byte `{key,ordinal}`，最多 capacity 次。
6. 命中時 `606B5E`，bytes `418b4304`，讀 EAX=`bucket+4` 的 uint32 ordinal；`606B62/B65` 若 ordinal=`FFFFFFFFh`，走 missing。
7. `606B67`，bytes `48c1e005`，把零延伸的 ordinal 左移5；`606B6B`，bytes `428b8410b4030000`，讀 EAX=`[S+ordinal*20h+3B4h]`。
8. `606B73` 跳到正常還原寄存器／RET，不再改 EAX。

## 自然 missing 與 sentinel 特例

`606B40` bytes `b8ffffffff` 令 **EAX=FFFFFFFFh、RAX=00000000FFFFFFFFh**，然後共用 epilogue。以下自然路徑均不讀 property：

- ID 等於 global invalid ID。
- capacity=0。
- probe 遇到不同於要求 ID 的 empty key。
- 完整 probe capacity 次仍未找到。
- 找到 bucket，但 ordinal 為 `FFFFFFFFh`。

不能把 map empty key 与 global invalid ID 當成已證相同值。`606B31/B33` 遇到 empty key 時轉到 `606B5A`，**仍再次比較 empty key 是否剛好等於要求 ID**；若相等，原碼可讀其 bucket value。因而當兩種 sentinel 不同、要求 ID 恰為 empty key、該 bucket 的殘餘 value 也非 FFFFFFFF，原碼可能走 property 讀取。有效 map key 通常應排除 empty key，但本 body 沒有無條件拒絕它；不能把新增限制說成原行為。

property 本身也可能存 `FFFFFFFFh`，則成功讀取的返回值與 missing 相同。若離線測試要證明走了哪條路，需看 property read trace，不能只看返回值。

## 八格 guard 的位置與範圍

已選定兩個 guard 切點：

1. **`606AF3` 原 capacity load 之前**核 global S 與 bound S。不相符為新 reject1，早於任何 S／map 解參。先前 `606AF1` 的 global-invalid-ID JE 已執行，故 global-invalid-ID 仍自然返回 FFFFFFFF，即使當時 global S 不匹配。其他 ID 在 binding 不符時新拒絕優先於可能發生的普通 miss，這是明確新增策略。新增 CMP flags 不影響原查找：下一段原 `606AFA xor EAX,EAX` 及 capacity TEST 會建立所需 flags。
2. **成功路徑 `606B67` 之前**，即原 `cmp ordinal,-1; je missing` 之後，依序核 `n<8`（reject2）、`T<=8`（reject3）、`n<T`（reject4），再核 `EDX!=map empty key`（reject5）。最後一項是防止原 empty-bucket stale value 假命中的新防護，不能稱作原有條件。若 bucket.value=FFFFFFFF 已走原 missing，則不進這個新 reject5。

在 binding 相符前提下，capacity0、early-empty 普通 miss、full-table miss 與 valueFFFFFFFF 維持原自然返回，沒有在 missing 路徑讀 T 或 sidecar。成功 property 原值為FFFFFFFF亦仍可返回。

在 `606B67`，RAX 是由 `MOV EAX` 零延伸的 ordinal，R10 是實際查找使用的 S，R11 的 bucket pointer 已無後續用途；EDX 仍是輸入 ID。選定的有效成員條件為 **n<T**，沒有套用分類路徑的 n<D；getter 原來沒有要求 target 位於 dense 或 prefix，pending record 的 property 若已初始化，同樣可被查到。

getter 原來沒有讀 P／D／T，也沒有 cap==8 護欄。完整 lookup 的容量邏輯可以保留，不必因八格 sidecar 把 map capacity 改成8。mask 探測對一般合法 hash map 的前提是適用的容量／probe chain（例如 power-of-two capacity）；不應把任意未驗證 header 說成有效 map。

選定的共同 interior reject 會由上述四個 shadow slots 還原 RBX／RBP／RSI／RDI，RSP 保持入口值，EDX 保留輸入 ID，再交外部 continuation。其他 volatile registers 已可能被原 lookup 改動，不保證等於入口值。不能在尚未恢復時假稱入口 frame 完整，也不能把診斷拒絕自行冒充自然 missing／正常 RET。

早期 binding guard 能在讀 S 欄位前拒絕錯誤綁定；它不能證明相符地址實際有效／存活。map pointer、header／probe chains、無並行 mutation 仍是前提，late guard 也不驗證所有 entries。global-invalid-ID 路徑仍只讀 global 指標而不解參照 S；本設計沒有在它之前加 binding／count 檢查。

## 唯一 property 改接

令整份四陣列 sidecar 為 B，property base=`B+580h`，則目標讀取地址為：

```text
B + 580h + ordinal*20h + Ch
```

若介面直接接受 property base Q，則為 `Q+ordinal*20h+Ch`。本次選定 `movabs R11,B+1D8h`，保留原 RAX=`ordinal<<5`，將原 `606B6B` SIB index 的 R10 改為 R11，沿用 displacement3B4h；`B+1D8h+3B4h=B+58Ch`。R10 仍是 S，不改 map ordinal、不寫 property。完整 emitter 仍需重定位兩個 global RIP load／cmp 與所有內部分支。

EAX 返回**原始 DWORD**：沒有 `<4`、`<8` clamp，也沒有把 property 值重新解釋成 ordinal。八格改接應保留任意 DWORD（包括高位為1與FFFFFFFF）並以 MOV EAX 的零延伸方式返回。分類／move 改變的是 map ordinal，network index 應隨完整20h property record保持 entity 身分。

## 必要驗證與仍缺前提

下一步合成驗證應至少區分：

- ordinal 0、3、4、7 讀 sidecar正確第四DWORD，舊inline保留不同值以捕捉漏改。
- 成功返回值不是ordinal，且原值4–7、任意高DWORD／FFFFFFFF不被額外clamp。
- global sentinel即使S binding不符亦自然回傳；binding相符時capacity0、early empty miss、full-table miss、valueFFFFFFFF皆自然回傳，不進新reject、不讀property。
- 非global-invalid ID的早期binding拒絕；late guard的n>=8、n>=T、T>8與mapempty/stale value情境；拒絕恢復四個nonvolatiles、入口RSP及EDX ID。
- 使用分類／移除後更新的map查同一entity，從新ordinal讀回其原network index；不能只用固定slot測試。
- 原四格body與候選的成功／missing返回及ABI比對，並核唯一sidecar read與無shared-data寫入。

本輪用到的既有證據沒有提供此getter的具體直接caller契約；未因此推論沒有caller，也沒有新增caller掃描。hook入口選取、拒絕外層協定、Windows unwind、property初始化／生存期／其他讀者整合與真人網路資料仍需後續工作。這個有限reader可獨立實作，不能藉getter正確宣稱完整八人Mod可用。
