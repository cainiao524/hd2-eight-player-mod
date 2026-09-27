# 完整 `6054F0` 狀態更新候選：獨立靜態審查

## 結論與實際範圍

已獨立核對固定1111-byte body與實際1917-byte產物，包含入口乾式lookup、19處四陣列改接、全部原local／external relocations、R11存活值、兩段較長flags生命期、GS cookie及reject狀態。完整共同bundle重建結果與保存sample一致。**本輪沒有需要修改source的具體發現。**

本次執行Python builder／Capstone解碼及四項有限地址碰撞檢查，沒有執行host原生碼、沒有重跑Unicorn套件或操作遊戲。原始流程及外部條件見[有限前提](../../five_player_feasibility_20260927/roster_arrival_native_prerequisites.zh-TW.md)；`arrival`檔名不代表真實加入caller已證。

## 1. 固定指紋

| 項目 | SHA-256 |
|---|---|
| `Native/roster_arrival.py` | `2744e367accb26d022807984b8a573d95cc6e9ec15c011c5b403ee187e030771` |
| `roster_arrival_native_evidence.json` | `c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64` |
| 原 `6054F0..605947`，1111B／241指令 | `6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a` |
| `native_roster_arrival_addresses_synthetic.json` | `e2ca74722a5d6eed3d2ede6eebd1b7130a2a931e9316a92333f170559fc552a6` |
| `native_roster_arrival_bundle_synthetic.json` | `a9268253612ad82778491308acec824e83a27afb1f9d19313994657f3dc248e0` |
| 保存sample中1917B的arrival code | `97864f4b98d2a700a640785e3c0cc6b2859154fb70c46368d17a68187be180c9` |

Builder先驗evidence整檔及body指紋。本次另外從原body完整解碼，核每條instruction長度與硬編碼LENGTHS相同，避免只相信emitter自報metadata。

## 2. 完整body與重定位

逐條比較原指令及相應生成segment，分類如下：

| 類別 | 指令數 |
|---|---:|
| 完整保留原bytes | 154 |
| 四陣列改接 | 19 |
| 原local branches | 41 |
| 外部RIP／direct call重定位 | 27 |
| 合計 | **241** |

27個外部位置是23個RIP及4個direct calls。四個call仍到原game-base RVA `FD9AF0`、`94C9C0`、`60C2A0`、`2088770`；沒有替換業務callee。四個原indirect calls（關聯接口兩次、palette及player_count）也保留原bytes。由实际解碼operand重算target，全部符合原RVA或local mapping。

所有41個原local edges均對上相同原instruction的生成位置；短branches升near不改條件。生成code中的所有立即jump落在有效解碼邊界。1917B完整解碼為426項，含前置區末端不可達INT3對齊；原body在496B前置區之後。Preflight成功跳到body入口，原body內部迴圈不回到preflight。

## 3. Preflight、參數與拒絕

入口依序push RCX、RDX、R8、R9、RBX、RSI、RDI，保存56B，RSI=entry target。實際解碼確認：七次push後 `[RSP+20h]`正是保存的**entry R8**，所以新null-caller-state檢查沒有誤讀其他參數。

乾式檢查包含：

1. global roster等指定S。
2. target與caller-state R8非null。
3. `0<T<=8`及unsigned `P<=D<=T`。
4. map capacity恰8、target ID不同於empty及global invalid sentinel。
5. 最多8次linear probe，普通empty miss／full miss明確拒絕。
6. map value<T，故亦<8；同B的pointer record等於target。

Hash使用原DWORD乘法及mask7，探測每次加一再mask。沒有配置或非stack寫入／calls。T0拒絕與原流程不同，是避免任意miss繼續寫陣列的明示候選前提；D0且T>0仍可通過。沒有強加target ordinal<D或entity bit0⇔P。

成功及10個拒絕分支均逆序pop七個保存值。成功進原body時entry RSP及RCX／RDX／R8／R9／NV均恢復；拒絕亦同，僅R10D為1..10原因碼，RAX／R11／flags未承諾。RBP、R12–R15及XMM寄存器在preflight未觸碰；沒有把stack scratch寫入說成完全無寫入。

Guard只核所需target關係，不驗全map bijection、其他dense pointer records、OS可讀性或caller-state首byte非零時的+48／+624資源。其source limits保留這些前提。Callbacks可在後面破壞state，guard不提供同步、重入防護或rollback。

## 4. 19處array改接與R11

所有替換bytes重新解碼確認SIB：

- Pointer direct `6055BB`：base由RDI改R11，先載B−E8h；原ordinal仍在RDX。
- Dense衍生起點 `60561F/605626`：R11=B+584h、R10=B；原迴圈間接讀及20h／8 stride不變。
- Primary四處：R11=B−C8h，原n×70h offset／DWORD1,5,8及QWORD0寫入保持。
- Aux九處：R11=B+F8h，原n×38h及+2C8/+2D0/+2DC/+2E0/+2E8位移保持，對應B+3C0h的同一record。
- Property其他位置：R11=B+1D8h，原OR800h／低byte讀／full DWORD network index保持；`605760`只改SIB base，不誤改RBP的20h offset。

RDI始終保留原S，header／map／count及S+8繼續讀原位置。Byte MOV新加REX只擴展memory index，不改CL等資料register，也沒有引入high-byte register歧義。

已核R11存活值：

- 前兩個direct patches位於原map完成後，舊R11 map backing不再使用；後續dense loop另重新定義R11。
- Dense loop內沒有插入任意R11 scratch；從兩個MOVABS起點到間接讀／stride，R10/R11一直保留其新陣列pointer。
- 三條primary status stores都是離開迴圈後的路徑。此時R11的loop pointer已不再需要，後續primary清零及aux改接可重用它。
- Aux／palette／mode4各patch後沒有未重新定義的原R11需求；cookie check返回後，原`605924`會重新LEA R11作epilogue frame anchor。
- 固定FD9AF0在一般查找中自行定義R11D hash，sentinel分支不讀R11；無對本caller舊R11值的依賴。其他opaque callbacks僅在已列ABI契約下保留。

EAX的初始ordinal跨整個primary支線到`6056B2`仍live；所有patch只以R11承载地址，沒有把它當scratch。RSI/RBP/R14各階段的原定義亦保持。

## 5. Flags、palette、counts與cookie

### Flags

`6056F0 AND CL,1`的ZF必須到`605707 JNE`。中間兩個aux patches使用MOVABS＋原MOV，RIP MOV亦保持，不改flags；property bit0為1才寫aux+18=3的原條件保留。

`60579D`的mode比較flags跨MULSS／MOVSS到`6057CA`，該整段原bytes保留。Palette對index4..7的fallback因此沒有受新增地址計算破壞。

### Palette與counts

原unsigned CMP index,4、四列table及>=4時三個1.0仍原樣；乘255後4..7得到三個255.0。没有新增顏色資源、將bound改8或clamp network DWORD。

原globalS.D到94C9C0 stack+28，以及heldS.D到60C2A0／player_count均保持，沒有加一、減一、預測值或擅自snapshot。共同產物帶既有player_count plan，但這不保證完整context／真實資產與命名資源。Global／held S及三個D值相同仍依赖state穩定契約。

### Cookie與frame

Preflight成功先完全還原entry RSP，原prologue隨後執行。保存GPR、pushR14、sub80h、XMM6+70h、global cookie XOR RSP到+60h皆保留；没有原RSP operand偏移改動。

結尾原cookie XOR、`2088770` call及R11 frame anchor／NV／XMM6還原保持。Player_count是原CALL，沒有誤改成tail jump。Reject發生在原prologue／cookie建立之前；不需要把原epilogue套到尚未建立的frame。這些局部正確性不能取代新code的Windows unwind註冊。

## 6. 共同bundle及有界builder檢查

使用保存地址與所有固定source，獨立執行build_bundle；完整dict與保存sample相同，內嵌v0.13 registry bundle也逐dict相同。共同產物為**16個roster函式＋獨立player_count計畫**，known regions62項；沒有把trampoline算成第17個roster函式。

四項有限地址碰撞檢查均拒絕：

1. Arrival code與registry root code重疊。
2. Arrival code與player_count trampoline重疊。
3. Arrival reject落在registry helper code內。
4. Arrival code放在原game image的6054F0。

Standalone核完整1917B extent、S的428h已知範圍、B的680h、reject入口及原SizeOfImage=74727424。Bundle另加原arrival範圍與既有regions互查。地址沿用strict低canonical／對齊及rel32檢查；結果不表示地址已配置、可執行、unknown aliases閉合或完整reject handler範圍已知。

## 7. 保留的界限與停止條件

本次source／metadata未把arrival檔名當成已證caller，也未聲稱palette fallback提供八種獨立顏色、原D通知具備callback一致snapshot或任意context-map安全。FD9AF0的原cap0／full-miss null缺口、caller-state深層資源、其他dense entity pointers、callback副作用及GS checker實際執行均仍有明示契約。

完整原轉譯、19個位點、guard／ABI、R11／EAX／flags存活值、4個indirect calls、GS cookie及共同regions已有限核對。至此停止額外source／callee擴搜；後續指令測試／oracle需各自列實際案例與stub範圍，不能用本靜態審查替代測試或多人驗收。

仍缺引擎序列化／生命週期、sidecar配置／初始化／發布／回收、reject handler、hook／unwind、runtime版本確認、真實資產／通知與五至八帳號同任務；候選尚不可安裝。
