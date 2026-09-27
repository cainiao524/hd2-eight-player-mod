# Arrival／palette 更新：完整 `6054F0` 的有限原生前提

## 需求、決策與停止條件

成品需求是讓已建立的八格 roster 在這條狀態／關聯物件／palette／玩家數通知路徑仍使用共同 B，完整保留四組記錄與必要副作用。`arrival` 是本輪的工作名稱；本函式不新增map項目、不增加T/D/P，也沒有因此證明它構成完整加入流程。

本輪決策為完整 `6054F0` clone：改接19個陣列基址位點（含兩個衍生pointer起點），在首次寫入前確認有效membership；保留原palette對index≥4的fallback、原D計數及全部calls，共同帶入既有player_count patch計畫。沒有要求新色盤、資源hash或新的玩家數公式。

範圍限完整保存body、既有binding／count／callee證據及固定readonly資料。沒有全capture掃描、新程序擷取或callee樹擴張。下列完整局部契約足以形成候選；caller／state／資源條件明列後停止研究，接實作與有界原指令對照。

## 1. 來源與ABI

完整範圍 **`6054F0..605947`，1111 bytes／241條指令**，單一unwind fragment `2424950`，body SHA-256：

`6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a`

固定capture identity `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`；report SHA `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，data SHA `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。沿[既有consumer清單](roster_property_consumers_native_findings.zh-TW.md)選定root；[binding證據](roster_component_binding_findings.zh-TW.md)原先已固定network index來源及palette的有界fallback。本輪另外逐條核完整body。

入口可見輸入：

- **RDX=entity pointer**，`605521`讀entity+8 ID；`60552D`保存到R14。
- **R8=參數物件pointer**，`605524`保存到RBP。其首byte決定是否執行primary支線；非零時讀其+48 pointer，繼而讀該物件+624 byte。不能只因類似creation params便聲稱所有caller的實際來源已證。
- Entry RCX、R9沒有在首次覆寫前作業務輸入使用。
- `605530`載global `3326468`至RDI，作持有的roster S；map與所有四陣列最初均來自此S。

RBP在`6056B2`改為32-bit ordinal，之後`605754`乘20h；RSI在`6056B4`變成ordinal×38h，較後`605847`又改為registry pointer；R14在`60571D`變成FD9AF0返回的32-bit ID。不能跨這些定義保留原寄存器身分假設。

原prologue先將RBX/RBP/RSI/RDI保存到entry home，push R14後sub80h，當前RSP=entry−88h；XMM6保存於+70h，GS cookie位於+60h，palette暫存+50..5Bh，通知outgoing參數+20/+28/+30/+38。Epilogue先呼cookie check，再依entry-relative位置還原GPR／XMM6與RSP。clone及reject必須保持frame／alignment，不能刪cookie協定。

## 2. Map、ordinal與counts

原map使用S+D0 backing、D8 capacity、DC empty key、E0 multiplier，key=entry entity+8。Global invalid sentinel `3483C20`、cap0、full probe miss或不同empty key最後令EAX=`FFFFFFFF`，仍進`605599`。若entity key等empty sentinel，原lookup也可能採用empty bucket的stale value。

**原miss不是安全noop。** 即使參數首byte=0，也會在`6056B8`以這個ordinal写aux+8；若首byte非零，primary及其他global寫入可能更早發生。候選membership guard應在`605599`之前，或在完整原prologue前作乾式檢查；不能等palette讀取或aux store才拒絕。

八格候選可核globalS/binding、target非null、合法entity key、八bucket map、命中ordinal<T≤8、`P≤D≤T`及`B.pointer[ordinal]==target`。本body沒有要求ordinal<D的證據；pending ordinal可在T內，不能只為排除測試情境額外加dense-only target限制。參數物件及其條件式+48物件可讀性仍需契約，或另明示有限null guard；這不是完整OS記憶體驗證。

原遍歷只讀D：`60560E`把held S+84讀到ESI，逐一檢查dense records；未使用P/T作loop bound。本函式不更新T/D/P或map。原通知各自讀當時D，詳見第6節。

## 3. 完整四陣列與衍生地址清單

沿用共同布局：pointer B、primary B+40h／stride70h、aux B+3C0h／stride38h、property B+580h／stride20h。n是map ordinal，不是network index。

| 原位點（共同前綴 `60`） | 原操作 | 八格目的／保留要求 |
|---|---|---|
| `55BB` | `[S+n*8+E8]` entity pointer | `B+n*8`；後讀entity+14 bit0 |
| `55CD` | `[S+n*20+3AC] OR 800h` | property[n]+4；只在原參數／物件／entity條件成立時設bit11 |
| `561F` | LEA R11,S+3AC | `B+584h`，dense loop的property flag衍生pointer |
| `5626` | LEA R10,S+E8 | B，dense loop的pointer衍生pointer |
| `5665/5684/5691` | primary[n]+38h分别寫5／8／1 | `B+78h+n*70h`，三個互斥結果 |
| `56A6` | primary[n]+60h QWORD清0 | `B+A0h+n*70h` |
| `56B8` | aux[n]+8 DWORD=7FFFh | `B+3C8h+n*38h` |
| `56C8/56F3` | aux[n]+14h BYTE=1或inverse-property-bit0 | `B+3D4h+n*38h`；C8為原invalid-ordinal支線 |
| `56D6/5700` | aux[n]+20h DWORD=global3483C34 | `B+3E0h+n*38h` |
| `56E6` | 讀property[n]+4低byte | `B+584h+n*20h`，取bit0 |
| `5709` | aux[n]+18h DWORD=3 | `B+3D8h+n*38h`；property bit0為1時 |
| `5758` | aux[n]+0 QWORD=關聯物件返回值 | `B+3C0h+n*38h`，可能為null |
| `5760` | property[n]+Ch DWORD network index | `B+58Ch+n*20h`，原full DWORD保留 |
| `5801` | 重讀aux[n]+0作manager搜尋key | 與5758同一八格記錄 |
| `583C` | aux[n]+18h DWORD=1 | mode4且相關manager record有效時覆寫 |

以上共**19個基址位點**：pointer2、primary4、aux9、property4。`605630`透過R10讀pointer、`60563E`透過R11讀flags；`605658/60565C`分別推進8／20h。兩個LEA改接後必須保留這些衍生迭代；RDI仍是原S，供header、map、count與S+8讀取。

直接memory operands可按family使用原位移差：pointer B−E8h、primary B−C8h、aux B+F8h、property B+1D8h；這是地址算式，不指定尚未審查的scratch實作。不能永久bias仍live的RDI。

### Primary支線與外部寫入次序

只有入口參數首byte非零才執行：

1. 條件式設target property bit11。
2. `6055E3`把S+8的QWORD寫到`[global346D538]+3EF280`。
3. 讀global347CEF0的B3A8／B398。B3A8為null或兩者相等時primary+38=1；否則檢查D筆records。
4. Dense loop略過entity ID等target的record。其他record若property bit1或bit11為1則接受；任何一筆兩bit都0使primary+38=8，全數接受則為5。
5. `6056A3`把`[global347CE68]`首byte設1，再清primary+60h。

這些是原數值與條件；未替1／5／8狀態及global欄位杜撰正式業務名稱。參數首byte=0會略過這組primary／global動作，但仍繼續aux、palette及通知。

## 4. Aux、關聯物件與必須保留的flags

在有效ordinal路徑，先寫aux+8=7FFF；由property bit0計算inverse值至aux+14 byte，寫aux+20 global sentinel；property bit0為1才把aux+18設3。

**`6056F0 AND CL,1`的ZF跨三條MOV與兩處要改接的aux stores，直到`605707 JNE`仍live。** 中間位址改接不可插入改flags的算術或CMP。相同地，`60579D`的mode比較flags跨palette浮點MUL／MOV，至`6057CA JNE`仍live。

`605718`呼 `FD9AF0(ECX=target entityID)`。返回7FFF時設RAX=0；其餘值先呼global3326308介面`[+38]->[+8]`，再以第一回傳RAX作RCX、轉換ID作EDX，呼从`[global+40]+160`取出的目標。返回QWORD保存到aux+0。

模式global3326340+AC21C等4時，以aux+0搜尋global347CE50的1690h records，count在+2D200；第一個pointer匹配且其+29 byte非零才把aux+18改1。Null返回值也沿原比較流程，未擅自提早返回。

這些間接calls及後續notification可能有外部副作用。S、B、target、map ordinal與記錄生命週期需在整段保持一致；entryguard不提供callback排他、重入安全或部分寫入rollback。

## 5. Palette：index4–7的原行為已完整有界

`605760`讀property+Ch原32-bit network index。`605767 CMP EAX,4`接unsigned JAE：

- n<4：讀 `213F4E0+n*10h`的16B，使用每筆第1／2／3號float，忽略第0號。
- n≥4：不讀table，三個分量各取readonly1.0；同樣適用FFFFFFFF。
- 共同將三分量乘readonly255.0，寫stack+50／54／58，组成12B。

| Network index | 原float32輸出三分量 |
|---|---|
| 0 | 255,157,66 |
| 1 | 129,172,254 |
| 2 | 246,138,255 |
| 3 | 110,215,84 |
| 4–7及其他unsigned≥4 | 255,255,255 |

固定readonly pins：

| 範圍／值 | SHA-256 |
|---|---|
| `213F4E0..213F520`，64B四列palette | `100fab4b4513b242012b69af448eab3a532fcbb49865c74bdaed4b4ee9b287a8` |
| `23C6D70`，`0000803f` =1.0 | `e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c` |
| `23C79AC`，`00007f43` =255.0 | `270696d298cc689d8e5bd75897918aa617a25a5030ccae98017053dddd974995` |

只有global347D620 DWORD等1，才於`6057E6`呼palette間接endpoint；RDX=&stack三個float，RCX來自global347D6A0。指標鏈為global3326308→首QWORD→+10 QWORD→首QWORD函式。資料符合RGB色盤，但沒有具名endpoint證據，不直接稱為HUD或手把燈。

**保留原fallback即可定義此局部對index4–7的行為，不需新增政策。** 不得只把CMP4改8而讀四列之外；若未來需要八種區別色，那是額外候選政策及顯示驗證，不能杜撰來源資源。這裡沒有拒绝第五帳號的邏輯。

## 6. 玩家數：保留當時D，接現有count plan

後段遍歷另一registry（global3326E68，count+1598，entry16B，tag3E）。只有mode4且tag符合才呼`94C9C0`。原call準備：

- RCX=該tag物件；RDX=物件+3A538。
- XMM2／XMM3分別來自物件+518B0／+518B4。
- stack+20 DWORD=物件+518C4；stack+28 DWORD=重新讀取的global roster **D**；stack+30 float=1.0；stack+38 DWORD=global33266A0 count存在時的+40值，否則0。
- `6058D3`呼`94C9C0`，返回後重載mode物件，再繼續registry迴圈。

其後`6058ED/6058F3`以held RDI的D作EDX呼`60C2A0`；`605906/605910`再次以held S的當時D、literal `player_count`作RCX，呼global3326308第二通知表的+480方法。這裡是普通CALL，之後還要cookie檢查及epilogue，不是tail jump。

**沒有D+1／D−1，也沒有必須新增的預測count政策。** 原body未改count；arrival候選可保留當時D，共同帶入既有v0.11 plan，使94C9C0上限8及94BE10有效四人profile上界延伸成立。0仍被94C9C0夾1；60C2A0對5–8只有既有數值通知，未提供新命名資源。沒有把departure的`D−(n<D)`公式套用到這裡。

第一個countconsumer從重新載入的globalS讀D，後兩者從heldS讀D；中間有callbacks，故不能聲稱三個值天然同一snapshot。需要globalS身分及state穩定契約，或後續有證據的同步方案；本輪不以未證的新快照語義遮蔽此差異。真實pending arrival可達性與所有caller所處加入階段仍未閉合。

## 7. Callee選擇與完整轉譯界限

原body有4個direct calls：`FD9AF0`、`94C9C0`、`60C2A0`、security-cookie helper `2088770`；另有4個間接calls（兩個關聯介面、palette、player_count）。没有调用insert／classify／move／receiver／network getter，因此那些候選不能替代整個body或其副作用。property+Ch的單一直接讀取可直接改接B，不必為使用現有getter而重寫ABI／live registers。

`FD9AF0..FD9B9E`為174B／44指令，SHA `7fa3870d13305c77997147167ccca1f07b199c5011883b9d8442f31e831393fc`。它不讀roster陣列、無calls；以global346BF98 context forward map查entryID，返回`context+F32F28+ordinal*18h` DWORD。Input等global348456C時回readonly2154544。Cap0／full-table miss可CMP `[NULL]`，valid context/backing及key仍是契約。沒有擴展任意callee樹。

94C9C0／60C2A0已有[既定count資料流](roster_player_count_native_prerequisites.zh-TW.md)及[departure callee證據](roster_departure_callee_evidence.json)，無新的直接roster array來源要改。外部資源、完整context15 calls、通知及cookie checker可在有界測試中使用明示contract stubs，不能因此稱真實資源或security helper全程已執行。

完整clone應保留全部原local branches、RIP、4個direct及4個indirect calls、GS cookie／frame。尤其EAX初始ordinal跨整個可選primary支線仍live，到`6056B2`才保存到EBP；不得拿EAX作臨時B基址。R10/R11是dense loop的衍生pointer，不能在迭代內用作任意scratch。所有scalar／byte／QWORD寬度及第4節flags生命期都須逐處核對。

## 8. 下一步與停止邊界

來源已足以實作完整body候選，下一步以原四格配對及八格代表狀態執行指令驗證：参数flag兩側、primary1／5／8、D-loop忽略self及property bit1／11、aux bit0兩側／mode4覆寫、palette0..7及FFFFFFFF、mode1 endpoint與其他mode略過、原D計數／tag3E多項迴圈、首次寫入前拒絕、cookie/frame/nonvolatile、與既有countplan共同建置。

固定FD9AF0可執行真實保存leaf的有效路徑；其餘calls若用stubs，必須逐項列ABI／參數／出參／副作用與未驗證的實際資源行為。沒有理由再泛查無關callee，也不需要新增palette資源政策。

仍缺caller完整生命週期、sidecar配置／發布／清理、跨callback及執行緒state序列化、拒絕handler、hook／unwind、實際資產／通知及五至八帳號任務全流程。本輪到局部契約交付停止，不把它當作可安裝或八人已成功。
