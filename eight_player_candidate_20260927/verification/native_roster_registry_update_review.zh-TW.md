# Registry updater 原生候選：獨立靜態審查

## 結論與範圍

已獨立核對完整 `B54E00` root及必要 `606520` helper的保存指令、兩個實際生成產物、guard／reject、八處陣列改接、所有原分支及外部相對位置，並重建共同bundle核對保存範例。**本輪沒有需要修改source的具體發現。**

這是受[有限前提](../../five_player_feasibility_20260927/roster_registry_update_native_prerequisites.zh-TW.md)約束的靜態審查。實際執行Python builder及Capstone解碼，沒有執行生成的host原生碼、沒有重跑Unicorn suites、沒有操作遊戲程序。本文件不替其他代理的指令／oracle測試宣稱全面通過。

## 1. 固定指紋

| 項目 | SHA-256 |
|---|---|
| `Native/roster_registry_update.py` | `1e97c7e52c6d723fe43824c599cfc27871650dea3fe4357f9fcf14dfaa2edd01` |
| `roster_registry_update_native_evidence.json` | `7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1` |
| 原root `B54E00..B55169`，873B／203指令 | `8f679d31841a3cce6ee1f4d66ec47bc89aa9a347b68939bc4264ec25bf8bd783` |
| 原helper `606520..60662F`，271B／72指令 | `ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e` |
| `native_roster_registry_update_addresses_synthetic.json` | `9e55ffae537f449fea5ffc7a8fe63df4204963c2090acd75ccd57d0b3b0fc432` |
| `native_roster_registry_update_bundle_synthetic.json` | `01925487570c19244c577f2a8664e733f64c047f9914b30428105e02ead5198c` |
| 保存sample root產物，1683B | `8756fc449d8ee42aeeccd56385ef1cff14edf4df652207f1e24b15dc8746c3b0` |
| 保存sample helper產物，416B | `8501214157521feed45d56e03ef4ecfc3ecf25c92655bc1ba3adc73126d79d40` |

Builder驗evidence整檔及兩個完整body指紋。獨立從body重新解碼確認每條instruction長度與SPECS相同，不只讀取emitter自報的patch表。

## 2. 全部原指令的去向與CFG

對每條原指令，獨立比對生成segment：未改指令須保留原bytes，array replacement重新解碼核地址，local branch從實際operand取得目的，RIP／direct call重算實際target與原指令比較。

| 分類 | Root | Helper |
|---|---:|---:|
| 完整原bytes | 141 | 56 |
| guard後保留原指令（不重複下列relocation分類） | 3 | 0 |
| 陣列改接 | 6 | 2 |
| 原local branches | 40 | 11 |
| 原RIP／direct call relocations | 13 | 3 |
| 原指令總數 | **203** | **72** |

Root的13個外部relocations為7個RIP及6個direct calls。只有 `B54F23→606520` 改向本bundle helper；其餘5個direct call sites仍指向相同game-base RVA。`B54EA7 CALL [RAX+8]`、`B54EAF CALL RDI`原bytes保留。Helper的3個RIP仍指向原context及兩種sentinel，沒有call。

所有短Jcc／JMP升級後仍取同一原條件及目標。共51條原local edges均對上instruction mapping，生成碼內所有立即branch目的都落在解碼邊界。Root實際生成356條可解碼指令，helper90條；連同reject blocks完整覆蓋1683／416B，無未解碼尾段。

各原標籤先於該處guard建立，因此跳入 `B550C7` 的原分支都先執行ordinal guard；沒有透過原forward/backward edge繞過它。Helper entry guard在原prologue之前，原內部branches仍指向body mapping，不重跑entryguard。

## 3. Binding／count guards與ABI

### Root分支限定

- `B5500B`：registry R14已載入後，核R14等指定S及global roster等指定S；再用unsigned比較核 `T<=8`、`D<=T`、`P<=D`。D0合法，但binding／order失敗比原D0略過更早拒絕。
- `B54F23`：原RCX=globalS、RDX=out pointer、R8D=inputID已準備，緊接helper call前核相同binding/counts。只改tag73依賴roster的時點。
- tag115／tag2E／未知tags不新增roster檢查；原空registry入口也完全保留。

`_binding_guard`只使用R10／R11及flags；RCX／RDX／R8、EBX、registry R13及其他nonvolatile不變。CMP編碼實際解碼分別是 `cmp [S+84],T`、`cmp [S+88],D`接JA，方向正確，允許P=D=T=0。

### Match後的檢查

- `B55069`前檢查matched pointer非null，再執行原entity+8 ID讀取。
- `B5506C`前檢查globalS map capacity=8及entity ID不等map empty key；原global invalid sentinel比較仍執行。
- `B550C7`前檢查mapOrdinal<8、mapOrdinal<T及mapOrdinal=ESI。Missing／invalid轉成FFFFFFFF後會在這裡拒絕；不再形成極大aux offset。

Map guard只在property搜尋命中後才要求capacity8；no-match及D0不新增map要求。沒有把原entity bit0改成prefix分類規則，也沒有遍歷P至T的pending records。

### Helper與拒絕frame

Helper entry只驗RCX等指定S及counts，不另外要求globalS；這與其明示API一致。Tag73 caller在call前另驗它所載的global，兩處在serialized lifetime契約下相容。Entry guard沒有stack／out寫入或calls，reject保留RCX／RDX／R8及entry RSP，R10D為原因碼，R11／flags不保證。

Root五個guard位點均在原nonempty prologue與全部NV save之後。各reject先 `MOV ECX,EBX` 恢復原32-bit inputID，再複製原 `B55146..B55168` epilogue（不含RET）：恢復R15/R14/RDI/RSI/RBP，add50h，pop R13/R12/RBX，最後以R10D原因碼跳明示reject地址。原entry RSP及nonvolatile恢復；RDX/R8/R9等volatile不承諾原值。

若root與helper之間state被並行修改，helper仍可能進自己的entry reject；產物明列沒有通用nested-call unwinder。候選依赖既定state穩定，不能把兩次guard說成排他或回復機制。

## 4. 六加二處陣列改接及R10存活值

實際解碼的地址為：

| 位點 | 實際目的 |
|---|---|
| `B5501C` | `MOVABS RDI,B+580h`；原 `[RDI]`讀與 `RDI+=20h`保留 |
| `B55057/B550E9` | `MOVABS R10,B−E8h`；`MOV RAX,[R10+RSI*8+E8h]` |
| `B550CD/B550D8` | `MOVABS R10,B+F8h`；原aux CMP／STORE改為 `[RAX+R10+2E0h]`，即 `B+3D8h+n*38h` |
| `B550FB` | `MOVABS R10,B+1D8h`；AND目的 `[R9+R10+3ACh]`，即 `B+584h+n*20h` |
| `606559` | `MOVABS R14,B+580h`；property衍生loop保留 |
| `606622` | `MOVABS R10,B−E8h`；`MOV RCX,[R10+RBX*8+E8h]`，隨後讀entity+8 |

Pointer operands只改SIB base為R10；aux/property operands只改SIB index為R10。原ordinal、scale、displacement與資料寬度都保留。R14 registryS和R11 globalS沒有永久改成B；tag73的獨立RDI object及tag115的RSI object亦未被修改。

有限R10／R11 liveness核對：

- tag73 call前guard覆寫的R10/R11不是三個helper輸入。Helper原路徑在讀取map capacity/hash前重定義兩者；root call返回後亦會重新定義自己的tag73 map registers。
- tag69入口guard後，原程式不依賴舊R10/R11。每輪固定 `FD9BA0`自行定義其R11 context；matched路徑 `B5505F`另重新載入globalS。
- 第一次pointer patch使用R10之後，map路徑在 `B55074`重新定義R10D=capacity；invalid-ID分支也不需舊R10。
- aux patch抵達時map probe已結束，R10D capacity不再live；到property flag更新及下一registry entry均無未重定義讀取。
- helper的matched-pointer patch位於context map搜尋及input比較完成後；R10D capacity不再使用，直接返回outID。

MOVABS不改flags。aux CMP緊接其原JE，若不等2才寫1；property的entity bit0 TEST及JE保留，AND僅清property+4 bit0。新lookup guard之後原MOV／IMUL／CMP重建所需flags，不依賴guard前flags。

## 5. 原搜尋差異與其他tag副作用

Tag69原FD9BA0 call完整保留；propertyID=7FFF會以context default作out，再與inputID比较。Helper的原7FFF分支則跳過該record。兩者沒有合併，missing也保留各自global sentinel來源。

Root沒有修改tag73 map／資源流程、tag115兩次間接call／1690h記錄更新、tag2E callback或各tag的順序。Tag73 fallback的stack+28 byte、+2C DWORD初始化及後續完整16B MOVUPS皆保留，沒有將原不明的stack+20..27改為零。

Root與helper frame保持原大小；無額外push/pop包array operands，原caller home out slots及tag73 outgoing／opaque slots沒有位移。只有明示reject paths複製原epilogue。

## 6. 共同建置與區域檢查

獨立載入所有固定source，使用保存地址JSON執行 `build_bundle()`；回傳完整dict與保存sample完全相同。共同產物為**十五個roster函式**（原十三個加本輪root/helper）及獨立player_count兩處patch／51Btrampoline，known regions為59項。

另外執行四項有限builder檢查，均拒絕：

1. Registry root code與departure code重疊。
2. 新helper code與player_count trampoline重疊。
3. Registry root reject落在新helper code內。
4. 新helper reject落在既有mover code內。

Standalone build核完整1683／416B extent、S的428h已知範圍、B的680h、兩個reject入口及完整原SizeOfImage=74727424；shared bundle追加兩個原body範圍並與既有區域互查。所有地址沿用strict低canonical／對齊檢查，所有相對位移核rel32。這只覆蓋列出的區域，不證明地址已配置／可執行、完整reject handler長度或未知aliases。

## 7. 保留的執行期限制與停止條件

- Context reverse map的原cap0／full miss可CMP `[NULL]`；empty sentinel key亦可假命中。原FD9BA0及606520演算法保留，roster guard不是任意context資料驗證器。
- Binding/counts檢查不驗OS可讀性、不提供registry／S／B／entity生命週期或執行序列化。Helper matched entity pointer的有效性仍是契約，不能因root有null guard就說所有callee均防null。
- 較早registry entries可能已有callback及寫入；晚拒絕只阻止當前guard之後的工作，沒有rollback。其他tag真實資源／回呼重入仍未驗證。
- 沒有caller hook、reject handler、sidecar配置／發布／清理、Windows unwind、同步改碼、執行期版本驗證或可安裝封裝；也沒有五至八帳號任務結果。

完整source轉譯、ABI、R10存活值、flags、原兩個間接calls及共同已知區域已有限核對，停止額外source／callee擴搜。後續指令測試及oracle應各自列實際涵蓋的代表分段、tags及拒絕，不以本靜態核對冒稱完整執行期或真人八人驗收。
