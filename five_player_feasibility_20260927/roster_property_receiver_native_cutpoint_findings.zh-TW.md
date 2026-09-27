# P3 最小原生修改切點：roster property receiver `60C890`

## 決策與範圍

P3 的 host、client、roster 三組資料中，**component 239 roster 的 property receiver `60C890` 是目前最適合作為第一個離線 native emitter 的局部實作**。它的同一物件身分、入口 ABI、完整 303-byte body、正常 CFG、entity ID→ordinal map、八個 DWORD store 與 cursor 更新均已由固定擷取及[獨立審查](roster_property_receive_review.zh-TW.md)核對。可製作一份具實際 x64 指令位元組的 clone/trampoline 候選，將此 receiver 的 property writes 導向八筆 sidecar。

**它不能單獨啟用為八人 roster 補丁。** 其他插入、producer、分類搬移、移除、讀者仍用原四筆內嵌陣列；sidecar 的配置、綁定、釋放、併發保護與 hook/unwind 安裝契約也未完成。這份文件只確定本局部 native 改接點及其整合前提，不產生可安裝程式或聲稱第五人可加入。

比較依據：host 內嵌於外層 `+159B0`，下一個 client 在 `+162C8`，距離 `918`，且 host 指標加入多張 registry，pending／peer／尾端資料相鄰，既有 100 個 relocation pins 仍只是子集；見[host 引用核對](host_relocation_review_notes.md)。client 內嵌於 `+162C8`，有四組相鄰四筆清單，confirmed peer 第五筆 `+150` 覆蓋已用欄位，owner 直接 index 讀者還需共同改接；見[client 布局](client_expansion_notes.md)及[索引讀者](client_index_consumers_findings.zh-TW.md)。roster 亦未整體閉合，但其**單一 receiver** 有較小、可逐指令測試的修改範圍。

## 已證資料契約

來源是 build `25480438` 的固定 capture：`capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`、`captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。[receiver evidence](roster_property_receive_evidence.json) SHA-256 `bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10`；原 body `[60C890,60C9BF)` SHA-256 `23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411`，303 bytes／72 指令／四個 chained unwind fragments，沒有 callee。

- `S=owner+EA0818` 是同一 roster；`5565F9→60C9C0` 初始化，`568ECF` 發布到 global `3326468`，tag `69` registry 亦保存 S。元件 239 的 callback table 已靜態登錄插入 `540920`，不是僅有未證 caller 的函式候選；見[登錄證據](spawn_callback_registration_findings.zh-TW.md)。
- 四組內嵌資料 `S+E8` 指標 `4×8`、`S+108` 狀態 `4×70`、`S+2C8` 輔助 `4×38`、`S+3A8` property `4×20`，恰到下一子物件 `S+428`。八份 property 記錄單獨需要 `8×20=100h` bytes；若四組全改成原順序的八筆，結尾至 `S+768`，會覆蓋下一成員。見[roster 生命週期](roster_lifecycle_findings.zh-TW.md)。
- `BD13A2..BD13B3` 的直接 caller 傳 `(RCX=S, EDX=entity ID, R8=payload, R9=&cursor)`。`60C890` 用 entity ID 查原 S 的 map `+D0/+D8/+DC/+E0`，取 **roster ordinal**，寫 property 八個 DWORD；第四欄 `S+3B4+ordinal*20` 才是接收的 **network index**。尾部使 cursor 增 `20h`。必要前提是有效 entity→ordinal 與足夠 payload；本 body 沒有安全的 map miss／長度拒絕。

## 精確切點：clone `+0xA2`，原 RVA `60C932`

相較於 `60C928` 起的 10-byte 切點，`60C932` 只需替換兩條完整指令，共 **6 bytes**：

| RVA | 原 bytes | 指令 |
|---|---|---|
| `60C928` | `418b0e` | `mov ecx,[r14]`，讀入口 cursor；保留原碼 |
| `60C92B` | `448bc0` | `mov r8d,eax`，複製 map ordinal；保留原碼 |
| `60C92E` | `49c1e005` | `shl r8,5`，得到 `ordinal*20h`；保留原碼 |
| **`60C932`** | `8b0429` | `mov eax,[rcx+rbp]`，第一個 payload DWORD；用 E9 的前 3 bytes 覆蓋，於 trampoline 重播 |
| **`60C935`** | `8d5104` | `lea edx,[rcx+4]`；用 E9 餘 2 bytes及 NOP 覆蓋，於 trampoline 重播 |
| `60C938` | `43898418a8030000` | 第一個 `[r8+r11+3A8]` store；成功後返回此處 |

現有 72 指令正常 CFG 中，`60C932` 的唯一前驅是 `60C92E`；沒有分支進入被取代的 `60C935`。`60C932` 支配 `60C938/946/954/962/970/97E/98C/9A2` 八個目的 store。R11 在 `60C8A3` 收到入口 S；此前於 `60C8DB/E2` 供 map 查找使用，`60C932` 後只出現在這八個目的 store，之後不再使用。R10 最後於 `60C8F2` 參與 map 計算，切點後沒有讀取，可作 volatile scratch。EAX 此時仍是 map ordinal；R8 是 ordinal×`20h`、RCX 是 cursor、RBP 是 payload base、R14 是 cursor pointer。切點沒有必要改動 map lookup、八次 payload copy 或正常 cursor/return 分支。

對**已核對且綁定的 S**，若 sidecar property base 為 `B`，令 R11=`B-3A8h`，原八條 store 便落在 `B+ordinal*20h+[0,4,...,1C]`。trampoline 應先檢查 EAX 在 `0..7`，再核 sidecar binding 的 S 身分、B 非空與有效生命週期；現有 emitter 成功路徑以 RAX 暫存預期 S 並改寫 R11，接著重播兩條原指令覆寫 RAX 並跳回 clone 的 `+0xA8`（原 RVA `60C938`），R10 在成功路徑保持原值。任何 call 形式會另需保存 live volatile registers、Win64 shadow space／stack alignment；優先使用不改 stack 的資料讀取序列。

**不提供「綁定不符就保留原 R11」的通用 fallback。** 若 ordinal 為 4–7，原 R11 會寫入 S 後方已使用物件；若 map miss，EAX 為 `FFFFFFFF`，原碼零延伸後左移產生巨大 offset。離線 emitter 應將 ordinal≥8、`FFFFFFFF`、無效／不匹配 binding 路由至**整合者必填的 reject continuation**，在第一個 property store 前終止本次 dispatch；不得跳回原儲存寫入，也不得假裝正常返回後讓後續 property 依錯誤 cursor 繼續解析。這個 continuation 的診斷、cursor、上游 transaction 停止及正確 frame unwind 仍需另訂契約，不能由單一 receiver 任意決定。

## Clone／測試的原生要求

複製 303 bytes 且保持每條指令相對位置時，所有**內部** rel branches 的 displacement 可保持不變。原 body 唯一外部 RIP-relative memory 引用是 `60C897: 3b158373e702`，`cmp edx,dword ptr [rip+disp32]`，指向 RVA `3483C20`；clone 必須重新計算 disp32 並驗目標可達。`E9` 至 trampoline、成功返回 clone `+0xA8`，以及將原入口接至 clone 的分支，也須檢查 rel32 範圍或提供已驗證的 veneer。不要把原 RVA 當作 clone 內的絕對執行位址。

原函式的四段 chained unwind metadata 也不能因複製指令而自動沿用。clone 及 trampoline 的例外展開、hook 安裝原子性、正在執行的 thread、可執行頁配置、版本指紋及卸載恢復尚需設計／驗證；本輪離線研究沒有做 hook 或遊戲程序操作。

建議離線 native emitter／模擬測試至少核：

1. 原 303 bytes SHA、72 指令邊界、6-byte 覆蓋及單一 RIP relocation；所有 branch target 仍落在 clone 指令邊界。
2. 有效 ordinal `0、3、4、7`：原 map lookup／八個 DWORD 的值與順序／cursor `+20h`／非 volatile 暫存器一致，且新目的恰為 sidecar property record；0、3 可與原碼的 inline 目的作對照。
3. `FFFFFFFF`、`8`、binding 空值／不符：第一個 store 前進入 reject continuation，不寫原 S 或 sidecar，不經正常 cursor/return 假路徑。
4. 重新發生的 owner/S 綁定與 sidecar 生命週期、併發讀寫在整合層有明確策略。Emulator 只能證明選定指令情境，不是 hook/unwind／多人驗證。

## 下一個整合關口

receiver 的原生位址改接可先離線產生與審查，**但 sidecar 尚不能宣稱可啟用**。要讓八筆 property 有一致讀寫，至少還需將 producer `60C77D`、接收 `60C890`、`60C410/60CC70/60CEA0/540A40` 搬移與移除、`60CF50/60D300` 分類交換、已證 tag `69` registry 消費者及 owner 直接別名的 property 存取接到同一 B；同時保留 count `+80/+84/+88`、map ID→ordinal、元素順序與原生資源所有權。這些是**已知必要位置**，不是所有存取的封閉清單。先針對固定 owner 與 registry 使用者核完整 property 陣列讀寫集合，再確定 sidecar 的建立、重建及釋放時點，才能將此局部 emitter 接入一份不覆蓋相鄰成員的八槽原生 patch plan。
