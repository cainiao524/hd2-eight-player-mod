# Registry 更新的八格 roster 改接：有限原生前提

## 成品需求、決策與停止條件

需求是讓 `B54E00` 經 registry 取得的 roster，與既有八格候選共用同一 S／B：搜尋關聯 ID、讀 entity pointer、更新 aux state 及 property flag 都不能繼續使用四格 inline 儲存。完整函式亦處理其他 tags，必須保留其呼叫、資料與原順序。

本輪固定完整 root，加上直接必要的 `606520`、`FD9BA0`；有限核 `FD9AF0` 以區分其他 tag 的 ID 域。沒有全 capture 掃描、沒有擴展其他 callee。實作決策為完整 root clone、僅兩個使用 roster 的分支加檢查，以及完整 `606520` helper clone；不能只改 tag69，亦不能把 `606520` 換成 network-index getter。下列完整存取與 helper 契約足以形成局部候選，真實 registry／context／回呼生命週期另列，至此停止來源擴搜。

這是保存指令的離線前提文件，沒有查詢或操作遊戲程序，沒有配置 sidecar、安裝補丁或驗證真人帳號。

## 1. 固定來源

沿[既有 consumer 清單](roster_property_consumers_native_findings.zh-TW.md)選定 root；inventory／recheck SHA-256 為 `0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2`。以下另外從同一固定 capture 完整解碼。

| 完整範圍，不含末端 | Bytes／指令 | SHA-256 |
|---|---:|---|
| `B54E00..B55169` | 873／203 | `8f679d31841a3cce6ee1f4d66ec47bc89aa9a347b68939bc4264ec25bf8bd783` |
| `606520..60662F` | 271／72 | `ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e` |
| `FD9BA0..FD9C7C` | 220／59 | `d81d3d8b8d73c6301dae0432dbb840658fe113ba8a356c084da5c6d28ab51ad7` |
| `FD9AF0..FD9B9E` | 174／44 | `7fa3870d13305c77997147167ccca1f07b199c5011883b9d8442f31e831393fc` |

`B54E00` 的三個 contiguous unwind fragments 為 `B54E00..B54E28 / 24AD4C8`、`B54E28..B5515F / 24AD4D4`、`B5515F..B55169 / 24AD4F8`。`606520` 是單 fragment，unwind `2424B38`。`FD9BA0` 的三段為 `FD9BA0..FD9BD2 / 24CD914`、`FD9BD2..FD9C49 / 24CD91C`、`FD9C49..FD9C7C / 24CD93C`。

Capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`；report SHA `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，data SHA `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。根目錄的 capture reader 為 `research_handoff_20260927/indirect/inspect_capture.py`，`Image.read(start,end-start)` 對上述固定 ranges 可重做 SHA 及解碼。沒有以載入中的 PE 取代保存來源。

## 2. 入口、registry 與其他 tags

`B54E00` 的可見輸入是 **ECX 的 32-bit ID**，`B54E14 MOV EBX,ECX` 保存；不可由此命名為 network index。R13 在 `B54E0A` 從 global `3326E68` 取得 registry。遍歷 count 位於 `R13+10F0`，entry 步幅 `10h`：tag 在 `R13+1100+i*10h`，object pointer 在 `R13+10F8+i*10h`。迴圈每次末端重讀 count；R13 本身只在入口載入一次。

| Tag | 入口分支 | 保留的原來源／行為 |
|---|---|---|
| `69h` | `B54E58/B54E5B → B55003` | R14=該 registry entry 的 S；property／pointer 讀取，另以 global roster 查 map／更新 aux |
| `73h` | `B54E61/B54E64 → B54F09` | RDI=該 tag 的獨立物件；先以 global roster S 呼叫 `606520`，再查該物件自己的 map、操作其 `28h` 記錄 |
| `115h` | `B54E6A/B54E6F → B54E75` | RSI=不同物件；`FD9AF0` ID 轉換、兩次間接呼叫、搜尋 `1690h` 記錄、寫 `+20/+29` 並增加 `+2FC80` counter |
| `2Eh` | `B54E4F/B54E52 → B55122` | `7B5760(RCX=entry object, EDX=input ID)`；副作用限原 call 契約，未展開 |
| 其他 | `B55131` | 不做 tag-specific 動作，繼續 registry 迴圈 |

tag73 的自己的 map 為 object `+37D58/+37D60/+37D64/+37D68`，命中後的記錄為 `object+37D98+ordinal*28h`。這些不是 roster S 的陣列，不能跟著 B bias 改寫。

全 root 沒有明確狀態值返回契約。它保存全部使用的 nonvolatile；一般 frame 為 entry RSP 減 `68h`（三次 push 與 `sub rsp,50h`）。`+30/+38/+40/+48` 保存 R15/R14/RDI/RSI，`+70` 保存 RBP，`+78` 存 registry index，`+80` 是 tag73 out DWORD，`+88` 是 tag69 out DWORD。後四者位於 caller home 範圍；新增 locals／reject epilogue 不可覆蓋它們或錯用 early-empty 與普通 epilogue。

## 3. tag69 的完整 roster 資料流

`B55003` 的 `4d8bb4cdf8100000` 取得 registry S 到 R14。`B5500D` 的 `418bae84000000` 讀 **D=[S+84h]** 到 EBP，ESI 從0開始；D=0直接下一 registry entry。這是 dense 上界，不能自行改為 T。P 在原 root 未讀，T 亦未用於安全檢查。

八格布局沿用：pointer `B+0`，primary `B+40h`，aux `B+3C0h`，property `B+580h`；各 stride 為8、70h、38h、20h。

| 位點／原 bytes | 原存取 | 八格目的與保留條件 |
|---|---|---|
| `B5501C` `498dbea8030000` | LEA RDI=`R14+3A8` | RDI=`B+580`；是持續使用的衍生 pointer |
| `B55030` `8b17` | EDX=`[RDI]` | 讀 property 首 DWORD，保留原 ID 域 |
| `B5504A` `4883c720` | RDI+=20h | 每輪與 ESI 同步，不能只改一個 direct operand |
| `B55057` `498b84f6e8000000` | RAX=`[R14+ESI*8+E8]` | `B+ESI*8` 的 entity pointer，隨後讀 entity+8 ID |
| `B550CD` `4283bc18e002000002` | 比較 `[R11+mapOrdinal*38h+2E0]` 是否2 | `B+3D8h+mapOrdinal*38h`，即 aux+18h |
| `B550D8` `42c78418e002000001000000` | 上述 aux DWORD 非2時寫1 | 保留「2不改，其餘寫1」及先後 |
| `B550E9` `498b84f6e8000000` | 再讀 `[R14+ESI*8+E8]` | 同 B pointer；不可假定第一次值可永遠快取 |
| `B550FB` `4383a431ac030000fe` | `[R14+ESI*20h+3AC] &= FFFFFFFE` | `B+584h+ESI*20h`，僅原 entity+14h bit0為1時執行 |

完整 root **沒有 roster primary 存取**。tag69 的六個需換基址位點是 LEA、兩個 pointer MOV、aux CMP/STORE、property AND；間接 `[RDI]` 讀及 stride 保留。aux 更新在 property flag 清除之前；即使 entity bit0為0，aux 仍可能先改成1。原流程不修改 T/D/P、不搬移 record、不修 map。

### 兩個 S 必須相同

`B5505F` 重新讀 global `3326468` 到 **R11**；後續 hash map及aux使用 R11。R14則一直是registry S，供pointer/property。已有身分證據連結 tag69 與 roster物件，但候選執行不能只假定這兩個runtime指標必然相等。綁定檢查應同時核 registry S、global S與指定 S；保留R14/R11的原物件語義，僅改陣列目的。

### 搜尋與 map 的原缺口

每輪 `FD9BA0(RCX=&stack+88h, EDX=property[ESI].firstDWORD)` 後，比較 out DWORD與input EBX。第一個相同即進matched路徑，後面重複關聯 ID不再處理；全D未命中則下一registry entry。

命中後從entity+8取key；global invalid sentinel `3483C20`、零cap、完整probe miss或遇不同empty key都可令EAX=`FFFFFFFF`，仍進 `B550C7` 計算 `ordinal*38h`，原碼沒有安全停止。其map使用 S+D0 backing、D8 capacity、DC empty key、E0 multiplier。若key等empty sentinel，原lookup另可能採用empty bucket的stale value。

有效同S、唯一entity/map bijection下，mapOrdinal應等於搜尋到的ESI。候選可在共同入口 `B550C7`、aux第一次讀／寫之前檢查此關係及範圍；這是新增拒絕，不能稱原miss已安全。R12在map中暫作capacity−1，但所有抵達C7的路徑均已還原registry index，或根本未改；不可漏掉此載入／控制流。

## 4. 必要 helper `606520`：tag73 亦需共同改接

ABI：**RCX=S、RDX=out DWORD pointer、R8D=input ID；RAX返回out pointer**。無calls。它遍歷D筆property，將每筆首DWORD的關聯ID查context逆表，轉換後若等於inputID，就返回該roster entity的 `+8` DWORD。它返回entity ID，並非property+Ch network index。

| 位點 | 必要處理 |
|---|---|
| `60653D` `448ba984000000` | R13D=D；保留D上界及D=0直接missing |
| `606559` `4c8db1a8030000` | R14=S+3A8，改成B+580h |
| `606560` `458b0e`、`6065EA` `4983c620` | 間接讀及逐20h前進保留 |
| `60661D` | 從原entry保存位置取回S，仍是原物件 |
| `606622` `488b8cd9e8000000` | matched pointer `[S+RBX*8+E8]` 改B+RBX*8，接著 `60662A` 讀entity+8 |
| `6065F7` | missing輸出global `3483C34` DWORD；保留原值，不硬編碼FFFFFFFF |

`606520` 遇property關聯ID=`7FFF`會直接略過該record。這與tag69的`FD9BA0`不同：後者會輸出global `348456C`，tag69仍會拿它與inputID比較。因此兩種搜尋不能以「應該等價」為由合併或改用新共同演算法。

它從global `346BF98` 取得context；逆map在`+F22EC8/F22ED0/F22ED4/F22ED8`，value選`context+F32F20+ordinal*18h`的DWORD。遇不同empty key時以global `348456C`作比較值；零cap或full-table miss仍可能在`6065C3`比較`[NULL]`。這是必要context契約，roster的八格guard不會修好任意context map。

tag73原callsite `B54F23` 可轉向完整改接helper。該helper專屬roster API，因此entry可加binding／counts guard；不應把相同guard無條件加在整個`B54E00`入口，否則只有其他tags的合法registry也會受影響。

## 5. 必要外部契約與副作用邊界

### `FD9BA0`

RCX=out pointer，EDX=associated ID。`7FFF`直接把global `348456C`寫到out；一般路徑使用與`606520`相同context逆map及`F32F20+ordinal*18h`欄位。唯一非stack寫入是傳入out DWORD，本caller的out在stack；RAX=out pointer。完整body沒有call、沒有S或roster inline存取，**不需改接**。

零cap／full probe miss在`FD9C44`可能CMP `[NULL]`；associated key等context empty key也可假命中。有效context、backing、合法key與lookup終止條件需外部維持，或另外明確設計防護。沒有在本輪以roster guard冒稱完整state validator。

### 其他 tag 保留

- tag115：`FD9AF0(ECX=inputID)`是context forward map讀取，無roster存取或calls；其返回與`7FFF`比较。非7FFF時先呼global `3326308`介面 `[+38]->[+8]`，再以第一回傳RAX作RCX、EDX=轉換ID，呼從`[global+40]+160`取出的目標。後續搜尋／寫入自己的1690h記錄；找不到亦增加自己的counter。opaque callbacks的實际資源或重入未核。
- tag73：roster helper先執行；missing out則略過。自己的map命中後，`1731A60(RCX=object+37D98+ordinal*28h, EDX=62048502h)`至多呼兩次。保留返回pointer的原檢查及寫入，不展開其內部。fallback只設stack+28 byte=0、+2C DWORD=2，`B54FEB`仍複製stack+20..2F完整16B到result+4；首8B在本root未初始化，不能改成全零或宣稱固定值。最後result+Ch byte=0。
- tag2E：`7B5760`參數及呼叫次序保留，未替它宣稱無副作用。

tag69支線本身只有無CALL的`FD9BA0`，故沒有該支線內的外部callback。完整registry迴圈可在較早／較晚的其他tags執行callbacks；它們可能改registry或其他state，沒有由此證明全root排他／可重入安全。

## 6. 可實作的 guard 位置與限制

1. **tag69 `B5500B`之前、R14剛載入之後：** 只對此分支核registry S/global S/binding及unsigned `P<=D<=T<=8`，允許空roster。該位置早於D解參、property讀及helper；D=0的正常略過仍須保留。若新政策在binding錯誤時先reject，應明示它優先於原D0略過。
2. **matched pointer第一次解參之前：** 確保選取ordinal在既有D／T／8範圍，pointer非null；OS可讀性及entity生命週期仍為前提。
3. **global roster map開始probe之前：** 核已選capacity、backing前提及entity key不等empty sentinel，避免stale empty value；八bucket候選可要求capacity=8。global invalid key亦須走明確拒絕，不能讓FFFFFFFF進aux地址。
4. **共同 `B550C7`之前：** 核返回ordinal有效，及其與ESI一致；有效bijective roster應成立。保留aux==2的比較分支與entity bit0決定property清旗標的原流程。原碼沒有证明flag等同ordinal<P；不得為了易測試擅加此拒絕條件。
5. **`606520` helper entry：** 核同一S/B/counts，將两處陣列來源改接；合法D0或遍歷未命中仍輸出原global missing值。對其context查找維持明示外部契約，不能以roster map檢查取代context。

tag69的拒絕可以先於**當前tag的roster寫入**，但較早registry entries可能已有外部副作用。不可宣稱整個root拒絕是無副作用交易，也不能無條件跳RET而略過原caller的失敗處理。reject需還原當時frame與保存registers，並由整合者定義是否停止或繼續registry遍歷；沒有自動rollback。

固定幀／helper無calls可減少局部回呼不確定性，但跨執行緒、registry更新及sidecar生命週期仍未有序列化證明。候選只可在這些契約成立下執行。

## 7. 完整 relocation 與下一步

完整root須保留四種tag、所有局部分支、6個直接call sites與2個間接calls；其中只有`B54F23→606520`改向對應clone。原root有7處RIP-relative references，包含registry/global S、其他interface與兩種sentinels，全部依載入game base重定位。`606520`有3處RIP references及多條局部分支、無calls；entry RCX原S的保存位置不可因新frame／guard改壞。

不能永久把R14或R11當B：它們分別承載registry/global S；不能把tag73的RDI物件或tag115的RSI物件誤認為roster。aux CMP→JE及entity flag TEST→JE的flags必須完整保留。register scratch應逐位點證明不破壞原live值；以Windows volatile分類本身不足以證明函式內dead。

下一步是完整兩body emitter與有界原四格／八格指令對照：涵蓋tag69第一／最後匹配、D0／無匹配、aux=2保留／其他變1、flag bit0兩側；tag73實際helper讀到八格及missing；其他tags的完整保留與混合registry前後順序；新reject只保證其明示範圍。context helper可執行固定原碼，opaque callbacks則逐個列contract，不能把替身成功當真實資源或重入驗證。

本輪來源前提已足夠進入局部候選，停止新增callee研究。仍缺實際caller／registry與context生命週期、完整sidecar發布／撤回、其他consumers、reject handler、hook、unwind及五至八帳號全流程；本文件不宣稱八人Mod已完成。
