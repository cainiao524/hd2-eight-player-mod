# Roster remove 候選：有限獨立靜態審查

## 結論與審查界限

在下列固定 source、固定原指令及有限地址範圍內，未找到阻止採納的具體 emitter 缺陷。兩個輸出是 **717 bytes（legacy）／705 bytes（registered）**。這個結論只支持離線候選；新增 pending 修復的外部 ownership、實際 caller 契約、同步、配置、Windows unwind 與八個真人帳號連線均未由本審查證明。

本審查只讀 source、既有固定證據與已產生的合成 bundle，並用 Capstone 5.0.7 解碼、核對指令 bytes 和分支目的。不操作遊戲程序，不執行 host native bytes，不重跑另一支線的 Unicorn suites，不修改 emitter。測試仍在補強，**本檔不固定過渡測試 SHA、執行次數或通過宣稱**；最終測試 oracle 另行審查。

成品需求是：兩個 remove ABI 共用同一八格四陣列 sidecar 與 mover，保留有效三分區中的全部其他實體、map ordinal 和必要返回值；無效移除在刪 map 前拒絕。實作決策是保留原移除順序，再補原程式缺少的 dense→pending 邊界修復。停止條件是這兩個固定 body、直接 map-delete helper、共用 mover 契約及有限 bundle 交叉範圍核完；不擴大 caller 掃描。下一步是最終合成指令測試及外部生命週期整合。

## 固定來源

| 來源 | SHA-256 |
| --- | --- |
| `Native/roster_remove.py` | `097e34c1087f3b311ecf6c9ed85de9165fa739b416e9c99ff7a834aa021c9716` |
| `roster_remove_native_evidence.json` | `67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af` |
| 原 legacy `60CEA0..60CF4C`，172 B／43 instructions | `0c6e7607bf93a1e9fba1b8eeba998053b316670295e7d8db432352b3ce49cc7d` |
| 原 registered `540A40..540AE0`，160 B／40 instructions | `35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8` |
| 原 map delete `172F8A0..172F9A3`，259 B | `d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f` |
| `Native/roster_move.py` | `cc6df86a567fda45fcac9a258372df52aad085fff67a620b5f4a2d46c100c23f` |
| `Native/roster_insert.py`（bundle 整合入口） | `b7bfcd2184382925b4abade40c5e81f21fcdd689f1aea47a2546c055f0bbf551` |
| `native_roster_remove_addresses_synthetic.json` | `c653b65a48b6be4eff8d5b4829b883da47e80aa54caeaaf2100dd68b663880be` |
| `native_roster_remove_bundle_synthetic.json` | `e57f22e651193abf3fac07b7d5e71442771e14ca9bae812a8b0794f7d302d73f` |

原證據的 capture report SHA 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`；captured data SHA 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。本次沿用已固定完整 body，沒有重新取得執行期資料。

## 1. Preflight lookup 與拒絕狀態

- `515241504151535657` 依次保存 RCX、RDX、R8、R9、RBX、RSI、RDI，共 56 bytes。legacy 用 `488BF2` 取 RDX entity；registered 用 `488BF1` 取 RCX entity。所有 accepted／reject 出口都以 `5F5E5B415941585A59` 逆序還原，回到入口 RSP，之後才進原 body 或外部 reject continuation。
- 在讀 roster count 前先核 `[game+3326468] == bound S`。count 比較採 unsigned，依序要求 `1<=T<=8`、`D<=T`、`P<=D`，再要求 map capacity 恰為 8。容量不符時不解參照 map bucket。
- 查找的起點是 32-bit `key*multiplier & 7`，probe 每次 `(index+1)&7`，最多讀 8 個 bucket。解碼核對 `413B14C0` 為 `cmp edx,[r8+rax*8]`，`418B5CC004` 為 bucket ordinal；命中後以 unsigned `ordinal<T` 限定 sidecar pointer 讀取。
- `4D8B1CDB` 確認為 `mov r11,[r11+rbx*8]`。隨後比對 pointer 指向實體的 `+8` ID 與要求 key；dense target 才檢查 `ordinal<P` 與 entity `+14h` bit 0 一致。pending target 不把其 flag 當成 prefix 成員資格，與原 remove 的分支一致。
- missing key／sentinel／ordinal 越界／target ID 不符／dense target flag 不符均在原 map-delete call 前拒絕。`R10D` 傳 reason；RAX、R10、R11、flags 屬可變部分。RCX/RDX/R8/R9 與所有 nonvolatile GPR/XMM 保持；不是「完全沒有寫入」：preflight 明確寫 56 bytes 的暫存 stack。

這是有限 guard。early-empty 停止依賴正確 probe chain；八個 bucket 的唯一 key、對所有 tracked records 的雙射、所有 dense flag、有效 entity/map 指標與同步仍是外部前提。guard 只檢查本次 target，沒有宣稱完整驗證整張 map 或所有 record。

## 2. 原 body 與 relocation

獨立逐條解碼原 83 條指令，再按 `instruction_address_map` 比對 bundle 的輸出。legacy 有 31 條原 bytes 不变、11 個 relocation、1 個 pointer-array 改接；registered 對應 28／11／1。兩個輸出均完整解碼到末端。

- `60CEEB`／`540A81` 注入 `movabs R11,B−E8h`，原讀取改成 `mov RCX,[R11+RDX*8+E8h]`，有效地址為 `B+ordinal*8`。RDI／RBX 仍保存原 S，用於 count、map 及 mover RCX。
- 每個原短 Jcc／JMP 升為 near 後，目的仍是同一原 instruction 的新地址。原 global RIP load 重新指向 `game+3326468`；delete call 仍到 `game+172F8A0`；全部原 mover call／tail-jump 改到顯式共用 clone。
- `60CF32`／`540AC8` 的 dense-only `test R8D,R8D` 被跳往新 dense completion 取代。pending 分支的 `cmp ordinal,newT` 仍經原 unconditional jump 到 `60CF35`／`540ACB` 對應的 JE；中間沒有改動 flags 的新指令，因此不會誤用 dense 條件或執行 pending repair。
- registered pending 路徑的原 epilogue＋tail-jump 完整保留。dense 路徑在尚有 frame 時先 call mover，再經已重定位的原返回 epilogue 結束。

## 3. 新 pending repair、RAX 與 stack

新增 completion 先重做原 `test R8D,R8D`。**newD=0 只跳過原 dense-tail move，仍進入 repair check**。repair 重新從 S 讀 `EDX=newD`、`R8D=newT`；若 `newD<newT`，以 `RCX=S` 呼叫共用 mover，將舊 tracked 尾槽 newT 複製到新的 pending 起點 newD。只有 dense 分支會到此處。

在有效唯一 record 與 ordered partition 前提下，前面的 prefix／dense moves 只動舊 `[0,D)`，而 pending 存在時旧 tracked 尾 `T−1>=D` 未受前面搬移破壞。新增 move 因此補回原 remove 會留在新 count 外的 pending survivor。當原 `D==T`，新 `D==T`，沒有額外 record/map 搬移。這是明確新增的候選語義；原 body 沒有這段修復。

registered 原 dense 尾跳的 RAX 結果，在新 completion 的第一次 mover call 後保持。repair 前的 `MOV EDX`、`MOV R8D`、`CMP` 不改 RAX；額外 call 以 `50 4883EC28`（push RAX；sub RSP,28h）及 `4883C428 58`（add RSP,28h；pop RAX）保存／恢復。newD=0 時保留未呼叫 dense mover 的原 RAX；legacy 最後仍依原 body 把保存的 entity `+10h` 放回 EAX。

兩個原 body 完成 prologue 後 `RSP=entry−28h`。以 Windows x64 入口 `RSP mod16=8` 計，普通 call 前 RSP 對齊 16 bytes；repair 的 push8＋sub28h 共減30h，call 前仍對齊。新增 call 保留至少20h shadow space，saved RAX 位於新 call-site RSP+28h，與 callee shadow 及既有 mover 的保存位置不重疊。這是固定指令的靜態 stack 分析，未聲稱已建立 Windows unwind metadata。

## 4. Bundle 與範圍

`build_bundle` 沿用 insert 的七函式 bundle，向每個 remove 傳同一 S、B、game base 與同一 mover address，加入兩個 remove code、reject entry、原 body，以及直接 delete helper。合成 bundle 的 36 個已知範圍逐對檢查重疊；包含與 producer、receiver、四個 insert 及其 reject 區的跨元件碰撞。每個 remove 自身也檢查完整輸出 span、sidecar 680h、S 428h、mover 545 B、global 8 B、delete helper 259 B 及兩個原 body。

reject 只描述入口的 1 byte；map backing、實體、完整 reject handler、整個 game image 的任意其他資料或全部配置區間不在這張有限表內。通過只證有限地址关系，不能推論地址已配置或可執行。`installable=false`、`game_execution=false`、`multiplayer_verified=false` 與未提供 hook／unwind／allocation 的欄位符合實際能力。

## 5. 測試 oracle 的有限閱讀紀錄

已讀當時的測試結構，沒有重跑。fixture 實際映射並執行固定 map-delete bytes 與原／clone 四陣列 mover；hook 只记录入口，不將 helper stub 成成功。成功 oracle 由三個身份分區的 unordered erase 建立所需 survivors，檢查 T/D/P、map 雙射與碰撞 probe 可達，以及 pointer／70h／38h／20h 四組完整 record。非 stack 頁面比較限制最終資料變動；map 的 64 bytes 使用實際結果再另驗語義，不是 deleted bucket 殘餘 value 的逐位元基準。拒絕案例另外檢查寫入 hook 僅有 stack 範圍及 helper 未執行。

這一概要不能取代最終測試 source／result fingerprint、執行數及 chain oracle 審查；測試仍有修改，交由其最終審查紀錄固定。合成八槽、remove／reinsert／receiver chain 不能解讀為八個帳號、真實網路或完整遊戲生命週期成功。
