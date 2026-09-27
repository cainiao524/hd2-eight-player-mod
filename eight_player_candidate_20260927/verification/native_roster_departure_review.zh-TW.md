# roster_departure 完整候選與共同建置：獨立靜態審查

## 結果、範圍與固定來源

**未發現阻止採納此局部離線候選的具體 source／relocation 缺陷。** 這個結論限完整固定 body 的轉譯、入口檢查、六處 storage 改接、frame、兩個新 count 參數及共同建置的已知區域；不認證真實 callback、資產、重入、Windows unwind、載入或八帳號遊戲。

本輪唯讀審查 emitter、固定 evidence 及其已生成 sample，獨立重建共同結果、解碼輸出並核每條原指令。沒有修改 source/tests/global docs，沒有執行 Unicorn suite，沒有程序操作。完整指令 oracle 的結果及範圍另由測試代理／主線記錄。

| 來源 | SHA-256 |
| --- | --- |
| `Native/roster_departure.py` | `a0d9a350254955a840a6039795eb42b89ea8f48e86c3ce00b921e3b1c6f165ba` |
| `roster_departure_native_evidence.json` | `0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609` |
| `roster_departure_callee_evidence.json` | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |
| 原 `605950..605F2F` 完整1503B | `4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681` |
| 本 sample 的 departure code 2262B | `467c3936ff30c995e963e860a7b16af69623dddb203859cef443d3e40de2733a` |
| `native_roster_departure_bundle_synthetic.json` | `6df0fd14f0241426ec84a7f716c24f5d1453fa2e9f8f5747416a7ee5696cd39d` |
| `native_roster_departure_addresses_synthetic.json` | `c24a3b5cb6ce31ca8a5fae5c803de41fd06a8baafa8962b08abfa7673f36b231` |

完整設計前提另見 [roster_departure_candidate_contract.zh-TW.md](../../five_player_feasibility_20260927/roster_departure_candidate_contract.zh-TW.md)。該文件有可選 frame/guard 設計；本審查以下按**實際 source**敘述：目前保存 remainingD 到新 frame+60h、entry ordinal到+64h，不聲稱另外保存 D0 或 ID0。

## 1. 全原指令與機器碼對照

獨立 Capstone 解碼原 body，使用 source 的結果 mapping 逐條核對實際輸出指令及 target，沒有以 metadata 數量代替機器碼檢查。

| 分類 | 原指令數 | 核對結果 |
| --- | ---: | --- |
| 原 bytes 保留 | 215 | 包括兩個原間接控制點、RAX-entry saves、outgoing args、原 tail current-D 讀取 |
| Frame 修改 | 14 | 2處 sub/add80→90；12處 RSP displacement 加10h |
| RIP 重定位 | 24 | 22 memory＋2 LEA，全部回到同一原 image RVA |
| Local branches | 62 | 所有 target 為對應的新原指令入口；short 分支升級後仍同語義 |
| Direct calls | 21 | 20處仍呼原 RVA；唯一 `6059EE` 改為共用 getter |
| Array 讀取 | 6 | 目的 register、width、其餘 index/scale 保留，有效 B 位址一致 |
| Count 修改 | 4 | 2處載新 frame+60h；2處 DEC 改2-byte NOP |
| **合計** | **346** | 全部原指令恰分類一次 |

另在映射 `605978` 前新增兩條共10B的 stack stores。輸出完整2262B可解碼，含入口 guard、reject blocks、alignment padding及body，共535條解碼項；body起點在code+544。對整份輸出所有 immediate branch/call，位於生成區域內的 target 均落在已解碼指令邊界。

## 2. Guard、入口 ABI 與資料 carrier

入口 guard 先保存 RCX/RDX/R8/R9/RBX/RSI/RDI，共56B；沒有CALL或nonstack write。RSI保存輸入target，RDI為global S。它檢查：

- 指定 S binding、target非null、`0<T<=8`、`P<=D<=T`。
- map capacity恰8、target ID不等map empty或global sentinel。
- 最多8次的bounded lookup，空bucket或probe耗盡拒絕；命中ordinal必須<T。
- `B[n].pointer` 必須與傳入target**指標相等**，比只比較ID更嚴格；因target先驗nonnull，後續flag讀不會因合法命中而讀null。
- dense target的bit0須與n<P一致；pending不因n>=D而拒絕。

這仍不是全map bijection／heap有效性檢查。target、map backing、B以及各header必須符合有效、穩定的輸入契約。指標相等也是新候選有效域的一部分，沒有證明所有未知caller均滿足。

成功段先 `MOV R10D,[S+84h]`，再 `CMP n,[S+84h]`、`SBB R10D,0` 得到 `D−(n<D)`；R11D承載ordinal。其後還原全部saved參數/NV，跳到原body。原 `605950..605975` prologue 沒有寫 R10/R11；在 `605978` 原target ID載入之前，兩個值分別保存到frame+60/+64，之後原map lookup才覆寫這兩個volatile。

Reject先還原這七個保存register，RSP回entry，再以R10D=1..10轉到提供的reject地址。RAX/R11/flags不承諾；其他nonvolatile與XMM未被改動。metadata正確指出56B scratch stack writes，沒有把guard描述為完全無寫入。reject handler／外層終止或恢復流程尚未提供。

入口guard在真正第一個可能的`605BC9 disconnected` callback之前完成；但並不提供或證明callback期間同步。原body仍重新查map，須依明示穩定性契約使其與guard看到相同狀態。

## 3. 六處 B 存取及 R11 liveness

各位點先 `MOVABS R11,constant`，再修改原SIB，使原R13位置由R11承接；R13本身保持原S。

| 原RVA | 新R11常數 | 原disp | 有效常數部分 |
| --- | --- | --- | --- |
| `605A0D / 605B96` | B−E8h | E8h | B，原ordinal*8保持 |
| `605A26 / 605A3A / 605A4E` | B−C8h | 108h | B+40h，原n*70h保持 |
| `605A5B` | B+1D8h | 3A8h | B+580h，原n*20h保持 |

兩處pointer是原R13作base；其餘四處原R13作SIB index，source分別改正確位元，未把兩種編碼混淆。六處均以實際解碼operand重核。

R11核對不限於「volatile所以可覆寫」：初始map的最後一次原R11讀是`605B84`；下一個`605B96`改接之後，原body不再用這個初始map值。後續manager map在`605B11`等處先重定義R11，再使用。每次array位點到後續原R11讀取之間均有新的原定義或重新進入獨立lookup。

三個完整primary helper第一次使用R11前，分別在`B0B075/B11C75/B0F875`從自身子系統載入R11；后續清零也是自身定義。`FD9C80`在`FD9CB1`先定義R11D。未以候選改接留下的R11當其輸入參數。其他外部callback的ABI仍按原明示呼叫契約處理；本輪不將其完整內部行為列為已驗。

原三次primary首DWORD仍各在原call之前重讀，RDX仍是原S、R8D仍是targetID，沒有將registration owner替换為B或刪掉resource calls。

## 4. Frame、出參與原回呼資料流

原frame80h改90h後call alignment仍相同。所有原RSP displacement>=60h加10h，outgoing20h..50h保留原offset；entry-RAX-based saves不改。獨立掃描原指令的RSP memory operands，恰與12處修改相符。

- XMM6 `60→70h`，完整16B範圍不碰新增locals。
- R15 `70→80h`兩處、R14 restore `78→88h`一處均升成disp32；沒有把80h當負disp8。
- out DWORD 的 LEA與兩次讀回`A0→B0h`同時改，保持pointer escape及後續consumer一致。
- RBP/RSI/R12對應`A8/B0/B8→B8/C0/C8h`，與原entry-based保存的物理位置相同。
- 原R15/R12條件save／restore的branch關係保留。

原`605D34→FD9D40`後的ECX→R8D及`[RAX+Ch]→R9D`原bytes未變；固定callee確實保持ECX，不能由任意volatile-clobber替身取代其此項契約。`13BFB40`的stack出參及outgoing arguments保留其ABI。

另外只核新增 `roster_departure_aux_evidence.json` 的兩個固定欄位，JSON SHA為 `43507a33e177e0a3f43bb0afe16dce99c59a059d57a5a15ec09a7c6d105793df`：`FD9D40..FD9DF2` 的178B與先前獨立核過的raw bytes／SHA `27627b0418666a4ce50917587d9dd779c3736a8af2272a3a3c955f94cb3701ed` 相同；literal `23C6D70` 為4B `0000803f`，SHA `e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c`。本次未重跑capture或新增callee範圍。

`605AC8 CALL RAX`與`605F28 JMP [R8+480h]`均保留。尾跳前恢復原NV、XMM6及entry RSP；沒有把原尾跳改成普通RET。

## 5. 新 count 與 getter 的實際界限

`605E95/605EF1`改讀入口預測remainingD；`605EA2/605EF8`兩個DEC改NOP。原`605F0D`仍讀held S當時的D，沒有把tail改成prediction或固定D0。這與metadata相符；只有狀態穩定時tail值等於entry D。

`6059EE`唯一callsite改向同bundle getter。其正常caller只消費EAX，然後重新載入RCX；原`606820`沒有全域替换。若callback破壞binding/map，getter可能走自己的拒絕入口，不能把這種晚拒絕稱為回復先前清理的機制。source已明列serialized lifetime與無callback rollback限制。

新remainingD處理pending包括D0=0，不再令這兩個源參數下溢；但這是候選政策，不能推論已證真實pending caller可達或原通知設計。原資源／manager支線與calls保留，真實resource contracts仍需成立。

## 6. 與十二函式及獨立 player_count 的共同建置

獨立載入全部固定來源，使用 `native_roster_departure_addresses_synthetic.json` 重建，完整dict與保存的 `native_roster_departure_bundle_synthetic.json` 相同。共同結果含既有十二函式＋departure，為十三個roster函式；另外產生獨立player_count的兩處原位patch及51Btrampoline，不把它算成第十四個roster函式。

共同binding傳給departure及shared getter，player_count使用相同game base。已知regions共53項，加入departure code/reject、原departure range、player_count code與兩個完整原source ranges。獨立驗證以下四種具體跨元件碰撞均拒絕：

1. departure code與producer code重疊。
2. player_count trampoline與departure code重疊。
3. player_count trampoline與dense legacy insert code重疊。
4. departure reject與player_count trampoline重疊。

Standalone departure另外以完整固定SizeOfImage=74727424排除其code/getter/reject/S/B与原image碰撞，檢查完整生成extent及rel32。共同region检查限列出的區域，不證明未知外部aliases、已配置／可執行或atomic publication。

## 停止條件與後續驗證

完整source轉譯、guard carrier、frame、B位址、所有local/external relocations、兩個間接控制點、count／tail區別、R11 liveness與共同已知區域均已有限核對。本輪沒有需要source修正的具體發現，停止額外靜態擴搜。

有限代表分段／ordinal與完整分支cases已由[指令測試](native_roster_departure_tests.json)核對，具體oracle及未涵蓋範圍見[測試審查](native_roster_departure_test_review.zh-TW.md)。7組／43次top-level執行中，只有7次原版與16次候選是完整departure；其餘為17次入口拒絕、1次remove及2次getter串接，沒有窮舉全部合法分段與八個ordinal。測試區分真實固定helper與contract stubs；其成功仍不能代替真實callback重入、版本載入／hook/unwind、資產與五至八帳號全任務驗收。
