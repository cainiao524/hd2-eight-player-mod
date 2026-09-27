# 八格 roster mover：有限原生前提審查

## 決策與本輪停止條件

成品需求是讓 roster ordinal 搬移同時保留 entity pointer、70h state、38h auxiliary、20h property 及 entity ID→ordinal map 的一致性。實作決策：可按下列固定 ABI／順序製作離線八格 mover；`680h` sidecar 的布局算術成立，**但現有證據不足以把整塊清零稱為原生可用的空八格 roster**。

本輪只核保存的 `60C410`、`60C9C0` 與已知初始化分支，沒有擴展 callee／全 capture 掃描。固定 ABI、map 異常行為、布局、初始化界限後停止。此文件不提供配置、綁定、卸載、hook 或多人完成證明。

## 1. Mover 的 ABI、相同 ordinal 與高 32 位

`60C410..60C5BE` 為 430 bytes、78 指令、3 個 chained unwind fragments，body SHA-256：`b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b`。完整原指令與 CFG 已保存在 [consumer inventory](roster_property_consumers_native_inventory.json) 的 `next_cutpoint`。

入口：`RCX=S、EDX=目的 ordinal、R8D=來源 ordinal`。

| RVA | 原 bytes | 原指令／作用 |
|---|---|---|
| `60C410` | `443bc2` | `cmp r8d,edx`，只比較低 32 位 |
| `60C413` | `0f84a4010000` | 相等直接跳 `60C5BD ret` |
| `60C423` | `448bf2` | `mov r14d,edx`，目的零延伸至 R14 |
| `60C426` | `458bd0` | `mov r10d,r8d`，來源零延伸至 R10 |
| `60C429` | `458bce` | `mov r9d,r14d`，目的再次零延伸至 R9 |

相等路徑没有讀 S、map 或任何 record，沒有 prologue stack 寫入。**RET 本身仍讀取 stack 返回位址並增加 RSP**，因此「完全沒有任何記憶體 touch」不是精確敘述。相等時不會執行上述零延伸指令；輸入暫存器高位保留，只有比較旗標與正常 return 產生變化。包括兩個低 DWORD 都為 FFFFFFFF 的情況，原碼亦直接返回。

不同 ordinal 路徑使用零延伸後的來源／目的生成所有 byte offsets；不能讓呼叫者 RDX／R8 的高 32 位污染位址。後續 map 的 EAX、ESI、EDI、EBP、ECX、EDX、R10D／R11D 運算也有原本的 32-bit 截斷／零延伸語義，重寫不得任意換成全 64-bit hash 算術。

## 2. 原副作用順序與 map 異常

不同 ordinal 時的順序是：

1. `60C438` 讀來源 pointer；`60C440` 寫目的 pointer。
2. `60C44B..60C4C9` 逐對複製 70h，七組 16-byte load/store。
3. `60C4D9..60C516` 複製 38h，三組 16-byte 加一組 8-byte。
4. `60C51F..60C53A` 複製 property，兩組 16-byte。
5. `60C543` 重讀目的 pointer，`60C557` 讀 entity+8 的 ID，才開始原 map probe。
6. `60C5B7` 將目的 ordinal 寫至所選 map bucket+4。

原 mover 沒有 call，不增減 counts，不清除來源、不作雙向 swap。它是依序 copy 並修 map；沒有失敗回滾。如果來源仍有 bytes，不代表來源另獲一次 ownership，也不能因此額外释放其 handles。

Map 使用 S 的 `+D0/+D8/+DC/+E0`。`60C590/60C593` 先比較 bucket key 與 empty-key sentinel，命中也直接走最後的 ordinal store；`60C595/60C597` 再判 entity key。**Empty bucket 命中不等於已找到 entity**，原碼未在這條路徑寫入 key。

- Capacity 為零，或 probe 達原 bound 仍無 key／empty-key：`60C5A0 xor r8d,r8d`，之後 `60C5B7` 寫 `[4]`。正常程序會出錯，且四組資料此前已複製。
- 無效 entity pointer：`60C557` 的 entity+8 讀取可能在 copies 後失敗。
- 此 body 沒有獨立拒絕「entity ID 等於 sentinel」；不能把其他函式的 sentinel guard 移植為原碼已存在的事實。

新的 fail-closed emitter 可以前移驗證，但須明列這是新增行為。Binding、source／destination 範圍及 map/key 前提若要保證拒絕時不改 roster，必須在第一個平行資料寫入 `60C440` 前完成；只在 property 段或原 map 尾端拒絕會留下部分更新。前移 map lookup 後仍需併發／重入契約，防止檢查後原 map 被改動。

## 3. 單一 `680h` sidecar 布局

以下位移、大小皆為十六進位，區間右端不含：

| 陣列 | 起點 | 八筆大小 | 區間 |
|---|---:|---:|---|
| Entity pointers | `0` | `8×8=40` | `[0,40)` |
| Primary state | `40` | `8×70=380` | `[40,3C0)` |
| Auxiliary | `3C0` | `8×38=1C0` | `[3C0,580)` |
| Property | `580` | `8×20=100` | `[580,680)` |

四區間相接、沒有重疊，總大小 `680h=1664` bytes。若 B 為 8-byte aligned，pointer／qword 位置符合所列存取對齊；16-byte aligned allocation 也可，原 vector copy 使用 `MOVUPS`，不能憑此要求每一個 38h-stride record 皆 16-byte aligned。

這四組相對原 inline 起點的位移不同，不能對整個 S 只施加單一固定 bias：原 `E8／108／2C8／3A8` 分別需對應新 `0／40／3C0／580`。原 S 必須仍供 map／counts／其他 metadata 使用。布局驗證只證明地址關係，沒有證明 B 已配置、其餘記憶體範圍可用或生命周期安全。

## 4. 初始化證據不能支持「全零即原生空八格」

已證直接 caller `5565F9` 建立 leaf 入口 `60C9C0`。完整 `[60C9C0,60CA65)` 165 bytes 的 SHA-256 為 `f85771a66bb6dd324b869026c86fc8ff5315c71556fcb763ec683bc494e40b06`。

| 原指令／區段 | 能證明的初始化 |
|---|---|
| `60C9CA mov qword[S+80],0` | 清零 tracked/dense `+80/+84` |
| `60C9E8/60C9EF/60C9F9` | Map backing 指向 S+8C；capacity=8；hash multiplier=2 |
| `60CA03..60CA2C` | 每個 map bucket qword 先為零，再寫其 key sentinel |
| `60CA39..60CA60` | 部分 metadata pointers、flags 的設定 |

此 leaf **沒有初始化四組 records，也沒有寫 `S+88` 或 `S+7C`**。這只說明此 body 的界限，不宣稱外層從未清零它們；外層整體契約本輪未追查。Map 的八個 buckets 也不是八名玩家容量的證據。

已知 record 初始化還有分支差異：

- `60CBA0`：`60CBCF xorps xmm0,xmm0`，`60CBDC..60CC0C` 清零 70h；`60CC18..60CC30` 清零 38h，但 `60CC38` 將 auxiliary relative `+14` byte 設為 1。因此 native initialized auxiliary 不是全部零。
- 已登錄的 `540920`：`54094C/540955` 按傳入旗標分支。True 路徑 `540988..5409B8` 清零 70h；false 直接至 `5409C2`，跳過該 clear。隨後 `5409D1..5409E9` 初始化 38h，`5409F9` 同樣設 relative `+14=1`。
- `60CF50` 的移入分類亦有目的 70h 清零；它不是建立整個空 sidecar 的 constructor。
- Property 由獨立 producer／receiver 寫八個 fields；producer 第一 DWORD 是 `7FFF`、第四 DWORD 來自 network-index helper，不能以全零替代。

**目前可支持的搬移策略**：對現有活 roster，在已驗證且同步的切換點，按原 ordinal 逐組複製完整 pointer／70h／38h／20h records，保存所有 opaque bytes 與原 pointer 值，保持 S 的 map／counts 身分。不能只複製目前已命名欄位或重新清零活記錄。原 sidecar 外部 aliases、資源 ownership 與原記憶體何時可停用仍需契約；單純 copy bytes 本身不會完成它們。

新增 4–7 槽可先配置成尚未發布的 raw storage，但不得在各路徑的 native-equivalent 初始化完成前當成有效 entity records。現有資料尚不足以實作並宣稱一個可直接啟用的「fresh empty eight-slot roster constructor」。真正缺的是建立／重建切點、count／prefix 起始不變量、每種插入／分類的初始化次序，以及所有 consumer 改接與釋放時點；本輪不為此擴搜。

## 證據界限與下一步

原 mover 與來源指紋已沿 [固定 consumer inventory](roster_property_consumers_native_inventory.json)、[player roster](player_roster_evidence.json)、[lifecycle](roster_lifecycle_evidence.json) 核對，新增查看僅上述保存 constructor／初始化區段。只讀 saved capture，沒有遊戲程序操作。

下一步可用不相等／相等 ordinal、高 32 位污染、正常 map 命中與明列拒絕條件，驗證整體八格 mover 的實際輸出指令。測試須比對四組完整 bytes、原來源保留、map key 不變／value 更新，以及拒絕前無 roster mutation；這仍只是離線原生局部驗證。
