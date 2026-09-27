# Roster getter 候選：有限獨立靜態審查

## 結論與範圍

固定 source 與已選雙 guard 契約內，**未找到阻止採納的具體 emitter 缺陷**。已核原43條指令、完整354-byte／70-instruction輸出、兩段guard、唯一sidecar DWORD讀取、共同reject還原，以及十二函式bundle的47個有限known regions。

本輪只讀 source／固定 evidence，用Capstone5.0.7核bytes、operands及branch；在Python內重新build sample並作四個具體碰撞拒絕試建。沒有執行host native bytes、遊戲程序或Unicorn suites，沒有修改emitter。這是靜態source review，不是十二函式執行測試或八人網路驗證。

## 固定指紋

| 檔案／body | SHA-256 |
| --- | --- |
| `Native/roster_getter.py` | `3de7432a9c1218ab98f2e92679583cb299c93d4ba8bcb739fea8aa980520ef5d` |
| `roster_getter_native_evidence.json` | `1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd` |
| 原 `606AD0..606B75`，165 B／43 instructions | `96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb` |
| `native_roster_getter_addresses_synthetic.json` | `694b37a93e38210b09f2b36170ffe017f4a48c4a219a1a78e81db9d282714d99` |
| `native_roster_getter_bundle_synthetic.json` | `26418f22275098fcf8378285f2c065be07c8137d0b8099ddef8687f211520bde` |
| 合成 sample getter code，354 B | `3528373182a4958c675f5f16e3c74df820b668ddb435647d1a5698986349b765` |
| `roster_getter_native_prerequisites.zh-TW.md` | `449110d87310c8e7f827b6c511431acf90bec1ddb2de5a2698388a6d3ce10e48` |

原body由前提分析直接重核固定capture：report SHA `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，data SHA `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。本次載入pin後重建整份sample，其所有欄位與已落盤bundle一致。

## 1. 完整指令與 relocation

原43條指令的length逐項與獨立解碼一致。分類如下，沒有未處理指令：

| 類別 | 數量 | 核對方式 |
| --- | ---: | --- |
| 原bytes保持 | 32 | 按原RVA→新地址mapping，扣除該位點新guard後逐byte比較 |
| local Jcc／JMP relocation | 8 | 新目標等於原target對應的新instruction起點 |
| RIP-relative global參照 | 2 | 解碼後仍指向`game+3483C20`及`game+3326468` |
| property operand改接 | 1 | 只替換SIB index，保留原opcode／disp32／DWORD寬度 |

完整輸出354 bytes全部解碼成70條指令；全部JMP／Jcc目的都是輸出instruction boundary或指定reject入口，沒有CALL。原`606AF1`的global-invalid分支仍跳到原missing對應位置；其fallthrough才遇到新增binding guard。原`606B65`的ordinalFFFFFFFF分支同樣先走missing，未經late guard。

`instruction_address_map`在有guard的原位置指向guard起點，不會讓原分支略過新增檢查。兩個原RIP參照與八個local branch都重算signed rel32，不再沿用原短分支距離。

## 2. Early binding guard與flags

`606AF3`前的19-byte新增段解碼為：`movabs R11,boundS; cmp R10,R11; jne reject1`。其中`4d3bd3`確認為R10與R11的64-bit比較。

此時原`cmp EDX,global-invalid-ID`及JE已執行，global-invalid-ID保留原FFFF return。其他ID若binding不同，會在第一次`[S+D8h]`讀取前拒絕；這個新拒絕優先於普通map miss，是有意的策略改變。新增CMP的flags不污染原lookup：原後續`xor EAX,EAX`與capacity TEST會建立其分支所用flags。

guard只核指標身分，不證明相符地址已配置／存活，也不驗map backing/header。這些有效性及同步仍由外部維持。

## 3. Late guard、missing與raw DWORD

`606B67`前的49-byte guard已獨立解碼核對：

1. `83f808 / JAE`：ordinal>=8 → reject2。
2. `4183ba8000000008 / JA`：`DWORD[S+80h]>8` → reject3。
3. `413b8280000000 / JAE`：ordinal>=T → reject4。
4. `413b92dc000000 / JE`：EDX==map empty key → reject5。

均為unsigned比較；沒有讀D或P，pending但已tracked的member不會因分類範圍被拒絕。valueFFFFFFFF早已由原分支返回；T和sidecar不在原自然missing路徑讀取。map capacity仍用原mask/probe流程，不新增cap==8條件。

最後一項只攔截原lookup成功後的empty-key/stale-value假命中。它是新增防護；不能稱原函式本來就拒絕所有empty-key ID。global-invalid-ID、binding相符時的capacity0／ordinary miss／ordinalFFFFFFFF保留原回傳。

原`SHL RAX,5`在guard後照常執行，覆寫flags；後面property MOV不讀flags。EAX從property取得完整DWORD，上32位自然清零；沒有把network index設為ordinal，也沒有對network index加4／8上限。property值本身為FFFFFFFF仍是合法raw return，與自然missing同值但不同讀取路徑。

## 4. 唯一sidecar讀取

原`428b8410b4030000`是`mov EAX,[RAX+R10+3B4h]`。候選先載`R11=B+1D8h`，再將SIB byte `10h`改為`18h`；REX.X仍是1，所以index由R10變為R11。獨立解碼確認core為：

```text
mov eax, dword ptr [rax + r11 + 3B4h]
```

RAX仍是原ordinal<<5，故有效地址=`B+580h+ordinal*20h+Ch`。R10保留S；沒有把map或count基址改成sidecar。除唯一SIB byte外，core bytes完全等於原指令。整段沒有額外stack操作或shared-data寫入。

## 5. Reject恢復與ABI

所有五個reason都先`mov R10D,reason`，再跳同一restore block。該block的20 bytes逐條解碼為从`[RSP+8/+10h/+18h/+20h]`恢復RBX／RBP／RSI／RDI，然後JMP外部reject。這四筆原入口保存位於guard之前，因此early與late rejection都有可用的原值。

RSP從未改動，外部continuation得到入口RSP；EDX ID從原body到guard均未被寫入，保持原值。其餘nonvolatile GPR／XMM未被新碼觸碰。RAX／RCX／R8／R9／R10／R11／flags可被原lookup或guard改動，metadata沒有宣稱保留它們。32 bytes原shadow saves是實際stack寫入，不能聲稱零寫入。

正常return仍走原四register epilogue與RET；新reject不是把錯誤偽裝成missing return，也沒有自行RET。Windows unwind與外部reject handler仍未由這個emitter建立。

## 6. 十二函式bundle與已知區域

getter使用分類bundle提供的同一game base、S與B；在原44個known regions上加入完整getter code、1-byte reject入口、165-byte原getter，成為47個區域，逐對檢查重疊。

本輪四個具體離線試建均拒絕：

- getter code與classify enter code同址。
- getter reject與producer code同址。
- getter code與原getter同址。
- sidecar從getter code前600h開始，680h跨度覆到getter前80h；確實由完整sidecar／code overlap檢查拒絕，不只比較起點。

地址檢查同時限制positive、alignment、low-canonical完整span與rel32可達範圍。這是有限已知區域表，不涵蓋完整reject handler、heap map backing、實體、外部配置及全部image aliases，通過不代表空間已配置或可執行。

## 停止條件與未完成事項

本輪source靜態範圍已完成，停止擴掃caller或callee。接續由獨立執行測試驗證原四格／新八格、missing、新拒絕、ABI與分類／移除換位後的entity→network-index讀值；本檔不引用尚未固定的測試次數。

getter本身沒有證明map完整雙射、pointer-array identity、property初始化／生存期或所有caller。其他reader改接、sidecar生命週期、hook／unwind／外層reject及真人同場任務仍待完成；`installable=false`、`game_execution=false`、`multiplayer_verified=false`符合本輪實際能力。
