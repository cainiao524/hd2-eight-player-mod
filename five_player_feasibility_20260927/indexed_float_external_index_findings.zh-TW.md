# `142EE70` 外部索引 q：confirmed-peer 來源與 host key

## 結論

先前未命名的外部 q 已接上既有物件：**它是同一 network owner 的 confirmed-peer record 中儲存的 32-bit network/player index，先用 `owner+B3A8` 的 64-bit peer ID 找到記錄，再讀 `record+14`。** 它不是另一套獨立槽位，也不是搜尋得到的 record ordinal。

這裡的 key 與本地 getter 的 `owner+B398` 不同。保存的 host migration 路徑會把 `B398` 本地 peer ID 寫入 `B3A8`，並傳送具名 `is_host` 設定；confirmed-peer receiver 也用 `B3A8` 檢查通知來源。因此本稿稱它為 **host-selection peer key**。未觀察目前 live 值，不能把每次使用都直接等同本地 peer，也不能假設 q 永遠為 0。

`142EE70` 在 q=-1 時跳過兩個 float 讀取，但在已匹配且 q 非 sentinel 的路徑，**沒有 q<4、`&3` 或縮窄**。因此八槽改接需涵蓋此函式的 confirmed-peer 表 inline 存取及 D record 讀取；不用另找一個其實不存在的 `<4` 常數來改大。

## 固定來源及產物

- 前置 `indexed_float_consumers_evidence.json` SHA-256：`503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578`。
- 本次 `indexed_float_external_index_evidence.json` SHA-256：**`c83db6d2e7c5033b3127d95227f29d24e11605415b55616d9854c2245ed4bf5d`**。
- Replay：`indexed_float_external_index_replay.py`。保存 **3,296 instruction rows**，含 12 個選定 roots 的完整正常程式範圍及 12 個補充 pins；每個 root 的正常 CFG 均可達全部已保存 instructions。兩份被實際 dispatch 使用的尾端 table 另作資料保存，沒有解碼成指令。
- Capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。Replay 驗證固定 report/data SHA、前置 JSON SHA、相同 capture、原始 bytes、指令／unwind 邊界、RIP global、語義 pins 及正常 CFG。
- 本次只有保存 capture 與工作區檔案的離線讀取；無活程序查詢／擷取、probe、遊戲執行、patch 或多人測試。

## 1. 身分證據：不是因 offset 相同而合併

`142EED8` 的 RIP-relative load 經位址計算，精確指向 **global RVA `347CEF0`**。`134D754` 的 owner constructor 讀取的是同一個 global。

令 `O=qword[global347CEF0]`。完整 constructor 中，RSI 在 `134DD07` 之前的 CFG reaching definition 只有 `134D754`，故可得：

```text
134DC9E  H = O+159B0
134DCA8  [H] = O
134DD07  C = O+162C8
134DD28  [C] = O
```

因此 q reader 的欄位與既有 client record 能精確換算：

| 意義 | Client C 相對位址 | Owner O 相對位址 |
|---|---|---|
| confirmed-peer count | `+C8` | `+16390` |
| 第 p 筆 peer ID | `+D0+p*20` | `+16398+p*20` |
| 該筆 network index | `+E4+p*20` | `+163AC+p*20` |

`p` 是表內 ordinal；`q` 是那筆 record 保存的欄位值。`q=p` 沒有被假設。

### 接上實際 confirmed-peer writer

Constructor 於 `134DD11` 把 C 傳入 `B2ABD0`。該 helper 在 global `3326E68` 的 registry 寫入 `{pointer=C, tag=EB}`，本稿相關的是 count `+6438`／array `+6440`。

`B90B20` 在 `B90B37` 讀同一 registry global；`B90B6C` 檢查相同 tag EB，`B90B7B` 取出 pointer，才用該 client 的 `+C8/+D0` 追加 record。這使 writer 和 q reader 具有 constructor／registry／owner 的身分鏈，不是以字面 offset 猜測。

Constructor 在 helper 返回後還使用 volatile R8。Replay 另核對 `B2ABD0` 完整 186 條指令：没有改寫 R8、也沒有內部 call，因而此處不依賴「呼叫必然保存 R8」的錯誤 ABI 假設。

## 2. q reader 的完整條件

`142EE70` 的 entry D 已由上一輪 `142D8B9` 的直接 call 與 D 來源證明；本輪再保存完整 374 條指令及 CFG。

```text
R9 = O
count = [O+16390]
key = qword[O+B3A8]

從 p=0 開始，每筆比較 qword[O+16398+p*20] 與 key
沒有記錄／沒有匹配：跳到142F0F8
匹配：q = DWORD[O+163AC+p*20]
q == FFFFFFFF：跳到142F0F8
其餘：讀兩個float，D+80E24+q*298、D+80E28+q*298
```

關鍵位置：

- `142EF10` count、`142EF17` key、`142EF26` array base。
- `142EF30/33` peer ID 比對；`142EF37` 以 `20` stride 前進；`142EF3B/3D` 依 count 遍歷。
- `142EF48` 寫 ECX，因 x64 32-bit register 寫入規則而零擴展成 RCX。
- `142EF50/53` 只排除 `FFFFFFFF`。
- `142EF78` 執行 64-bit `RCX*=298`，`142EF8E/9E` 讀取兩個 float。

Replay 的 reaching-definition 證明：q load 時 R9 只來自 `142EED8`；乘 `298` 時 RCX 只來自 `142EF48`；float reader 的 RDI 只來自 `142EEE8 entryRCX=D`。

另外分別切掉「peer 比對命中」邊 `142EF33→142EF44` 及「q 非 sentinel」邊 `142EF53→142EF59`，兩個 selected float reader 都不再可達。這確認前述查找／sentinel 是實際必要條件；沒有把兩個不相連的片段拼成資料流。

### 容量與數值範圍是兩件事

表的 count 控制 `p` 的搜尋範圍，並不限制 record 內的 q。即使 record ordinal p<4，raw receiver 仍可把 q=4 或 q=7 存在該 record。若這筆正好匹配 host key，`142EE70` 便以該值取 D record。

既有 D 四筆布局中，q=4 的兩次 float reads 合計 `[D+81884,D+8188C)`；q=7 合計 `[D+8204C,D+82054)`。它們讀到前置證據已確認的相鄰資料。**此函式是讀者，不是該區域的覆寫者**；前置 writer 的 collision 與這裡的錯誤讀取位址須分開描述。沒有聲稱上述執行在現有遊戲中已發生。

## 3. q 的 producer 保留完整 32 bits

### 新 host 的已保存初始化

`1088A30` 有精確字串 `HostSynchronizer`／`start_hosting`。其已保存路徑將 H+34 設為 0，令 confirmed count=1，第一筆 peer ID 取自 O+B398，再把 H+34 寫入 O+163AC。因此這一條新 host 初始化建立的第一筆 index 是 0。

這是特定初始化路徑的結論，不是所有後續 q 必為 0 的不變條件。另存的 `13500F0` 有相同 owner 形狀的 `B398→B3A8` setter、`is_host` 呼叫及尾呼叫 `1088A30`；其自身 caller 本輪沒有新增閉合，所以不拿它單獨當成「所有入口都來自 global O」的證據。

### Confirmed-peer 追加

`B90B20` 的相關順序：

```text
B90BE3     讀 C+C8 count
B90BF2..FD record = C+D0+count*20
B90C03     count++
B90C0B     EAX = 第五個 call argument 的DWORD
B90C12     record+14 = EAX
```

本函式建立 0x80-byte frame 並保存五個 registers，使第五參數從 entry RSP+28 對應至這裡的 `[RSP+D0]`。在 load→store 之間沒有 q clamp／mask／縮窄。

此 handler 實際有六個參數：前四個位於 RCX/RDX/R8/R9；**index 是第五個**，上述 `[RSP+D0]`；flag 是**第六個**，`B90C15` 從 `[RSP+D8]` 讀 byte 並寫 record+19。本文的「五個資料欄位」指 sender/receiver payload，不把額外的來源／路由參數漏算成五參數函式。

已保存的兩個真正 caller：

- `108C960`：host 通知迴圈的本地分支，直接把 host member index DWORD 放入第五參數。
- `BABAAF`：wrapper `BABA80` 讀 decoded field pointer `+38` 指向的 DWORD，原值放第五參數。

同一 host 迴圈的遠端分支 `108C97B` 改呼叫 `BE4910`；完整 sender 仍使用第四個資料欄位的 4-byte descriptor。這保持先前的證據界線：有程式碼級的本地／遠端相同值與 wrapper 對照，但未閉合 event hash 到 receive wrapper 的執行期註冊，也未觀察實際 wire frame。

### 原 allocator 的範圍

完整 `108BC70` 顯示 index flag scan 從 0 開始，只檢查 0..3；`108C3FB` 把找到的 DWORD index 或原 `FFFFFFFF` sentinel 放入 host record+14。Replay 另外核對迴圈零值来源 R14D 的 reaching definition 為 `108BD0B xor R14D,R14D`。

因此「原本選定合法 allocation 路徑配置 0..3」與「receiver／q reader 原樣接受其他非 sentinel DWORD」同時成立。提高 host 上限之後，不會自動替 client、D 或其他下游擴容。

## 4. Host migration 不把既有 index 強制重編成 0

已確認 global 來源的 caller：`B91581` 從 `347CEF0` 取 O，`B91596` 加 `159B0`，`B9159D` 呼叫 `1089720`。因此此 migration 的 H 是同一 owner 的內嵌 host。

`1089720` 有精確 `start_host_migration`／`HostSynchronizer` 字串。`1089BF5` 從 `[H]` 取得的 O 讀 `B398` 本地 peer ID；`1089C44` 把相同值寫到 O+B3A8，接著使用 `is_host` 字串。

這裡的 R13 中途會被重用。正常 CFG 在 owner 讀取處的 reaching definitions 是 entry `108973D` 或 `1089B2C` 的保存值還原。入口先於 `[entryRSP+8]` 保存 H；正常 frame 可換算成 `[RBP+67]=[currentRSP+E0]`。Replay 檢查還原前所有直接 RBP/RSP fixed-offset 寫入（含寬度），沒有覆寫該槽。

隨後 migration 從同一 confirmed-peer 表查到 index：

```text
1089E97 EAX = [O+p*20+163AC]
1089E9F [host-record+14] = EAX
1089EA2/EA5 只檢查FFFFFFFF
1089EAB H+100+index 的flag置1
```

因此存在保留既有 network index 的實際路徑；不能把新的 host key 等同「network index 永遠歸零」。若 coordinated eight-player 設計讓新的 host 持有 index 4..7，此 q reader 需要讀到對應的 relocated D record。既有 migration 仍包含四筆 host storage／index flags 等限制，本稿沒有宣稱原碼已能遷移八人。

## 5. 已證初始化容量與八槽必要改接

Constructor 把 C+C8 歸零，並將 C+150 初始化成另一個已用欄位。既有 reset 的兩條固定起迄 store pins 再核對到 C+D0..C+14F，共 80h bytes／四筆 record。第五筆 confirmed-peer append 的起點 `C+D0+4*20=C+150` 已碰既有資料。

| 項目 | 本次能確定的八槽影響 |
|---|---|
| confirmed-peer 新空間 | 若搬移其 count／records，需改 `142EF10`、`142EF26`、`142EF48` 這組 owner-relative inline 存取；只改 client 方法的相對地址不夠。 |
| D records 新空間 | 需共同改接 `142EF8E`、`142EF9E` 的 q-indexed float reads；此處沒有額外 `<4` 比較需要改大。 |
| q 的數值 | 32-bit width 和 64-bit `*298` 已能表達 4..7；應建立 0..7 的上游不變條件或加明確 bounds，並保留查無 peer／FFFFFFFF 的 skip 行為。 |
| host allocator／migration | 與既有八槽清單共同處理 flag、records 及初始化／搬移；不能將 q 固定為 0 來避開尚未擴容的 D。 |
| O+B3A8 | 單一 64-bit peer-ID key，沒有四元素容量；維持其角色即可，沒有本次證據要求把它擴成八格。 |

## 6. 本次關閉與仍未關閉的邊界

**已關閉：** q 的 global 物件、client record 身分、field 的 32-bit network/player index 語義、host-selection key 與 local key 的差異、主要初始化／原值追加／遷移保留路徑，以及這個 reader 自己的查找與 sentinel gates。

**尚未關閉：** 所有 host-key setters、完整 protocol decoder、event-hash→receive-wrapper 的執行期 mapping、所有 client relocation aliases、D 的其他 helper／精確 UI 名稱，以及任何實際八人加入與遊戲執行結果。Registry/owner 身分是保存版本的程式碼關係，不代表觀察到現在的 writable global／heap 值。

本稿沒有修改 REPORT 或設計稿，也沒有將這份有限 trace 擴張為全部 producer／consumer 的完整 inventory。
