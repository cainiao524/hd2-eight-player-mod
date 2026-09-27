# 四個 roster 插入實作：有限原生前提審查

## 決策與停止條件

成品需求是把新 entity 放入八格儲存，同時保留 tracked／dense／prefix 分段、初始化順序及 ID→ordinal map。四個固定 body 可作離線原生候選；**不能只將比較值 4 改為 8，也不能把其中任一插入回呼稱為完整加入流程**。

本輪讀既有 player_roster／roster_lifecycle、已證 callback／property binding 來源與固定 capture，僅額外完整核對唯一必要的 map helper `172F790`。停止於四 body、直接 helper 與已存 caller 身分；未掃描新 callers、未擴展任意 callee 樹、未操作遊戲。

## 1. 固定範圍、ABI 與兩種插入

四個 body 各自為一個完整 unwind fragment，右端不含：

| Root／末端 | Bytes | Unwind RVA | 入口資料 ABI | 型別 |
|---|---:|---|---|---|
| `60CA80..60CB9F` | 287 | `2425774` | RDX=entity、R8=flags pointer；入口 RCX 未被消費 | A：插入 dense／prefix |
| `60CBA0..60CC6B` | 203 | `2425780` | RDX=entity；入口 RCX 未被消費 | B：tracked 尾端追加 |
| `540850..54091E` | 206 | `2410A70` | RCX=entity，`540860` 複製至 RDX | B 的另一個 ABI |
| `540920..540A3E` | 286 | `2410A78` | RCX=entity、RDX=flags pointer；entity 保存至 RDI | A 的另一個 ABI |

四者都從 global `3326468` 取得 S。RIP loads 分別在 `60CA8A、60CBA6、540856、54092A`。除這一個 global 引用外，各完整 body 沒有其他 RIP-relative memory operand。

定義 unsigned DWORD：`T=S+80`、`D=S+84`、`P=S+88`、`H=S+7C`。以下分段不變量是安全候選的前提，不能當作所有實際 callers 已經證明：

`0 <= P <= D <= T < 8`

另需有效 S／四陣列 sidecar、有效 entity pointer、可用 map、新 key 與同步／生命週期契約。Network index 與 ordinal 仍是不同欄位。

### B 型：`60CBA0／540850`

令 `n=T`，原順序為：

1. 在 n 清零完整 70h primary。
2. 初始化 38h auxiliary：清零，並將 relative `+14` byte 設為 1；relative `+18` qword 為 0。
3. `60CC48／5408FB` 寫 pointer[n]=entity。
4. 以 `RCX=&S.D0、EDX=entity.ID、R8D=n` 呼叫 `172F790`：`60CC5A／54090D`。
5. helper 正常返回後，`60CC5F／540912` 才令 T++；D、P、H 不變。

這留下 `[D,T)` 的 deferred／非 dense 項目；本 body 不使新增項立即成為 dense。没有 property 初始化或清零。

### A 型：`60CA80／540920`

- flags[0]=0：`n=D`；不呼叫 mover，也**跳過 primary 清零**。
- flags[0]≠0：`n=P`。若 P<D，以 `60CAC9／540968` 呼叫 mover `(RCX=S,EDX=D,R8D=P)`，把既有 prefix 邊界項目複製至 dense 尾端；然後 P++，並在原 P 清零 primary。若 P=D 則略過 move。

兩分支會接著初始化 n 的 auxiliary，依序 D++、T++、H=max(H,new D)，再寫 pointer[n]=entity，最後 tail-jump 至 `172F790`：`60CB9A／540A39`。Map 寫入發生在這些 counts／record 副作用之後。

**A 型安全候選應另要求 `D==T`，除非已取得更強的 caller 空洞契約。** 若 D<T，n=D 原本在 tracked pending 區間：flags=0 直接覆寫它；flags≠0 也可能先用 mover 把 P 項覆蓋至 D。這些 body 沒有把原 D pending record 搬至 T。`P<=D<=T` 只保證索引有界，不能避免這種邏輯遺失。

`D==T` 是本輪採用的保守拒絕條件，不證明遊戲實際 caller 都能滿足它，也不把被拒絕的 D<T 路徑宣稱為不會發生。完整目標仍需對應 caller／deferred 項目的契約。

## 2. 原 capacity 檢查有 DWORD 回繞

| Body | 原 compare | 原超限操作 |
|---|---|---|
| `60CA80` | `60CA9A inc eax`；`60CA9C 83f804 cmp eax,4` | `60CAA1` 寫 DWORD[0]=0 |
| `60CBA0` | `60CBB7 lea eax,[r8+1]`；`60CBBB 83f804` | `60CBC0` 寫 DWORD[0]=0 |
| `540850` | `54086A lea eax,[r8+1]`；`54086E 83f804` | `540873` 寫 DWORD[0]=0 |
| `540920` | `54093A inc eax`；`54093C 83f804` | `540941` 寫 DWORD[0]=0 |

之後均為 unsigned JBE。`T=FFFFFFFF` 時，T+1 回繞成 0，會通過該比較。因此新 guard 應直接驗 **T<8**，並檢查 P≤D≤T；在此 guard 支配所有路徑的前提下，才可保留原比較形狀並把 4 改成 8。

## 3. Map helper 的重複 key／滿表行為

`172F790..172F7FE`：110 bytes，unwind `2567A18`，沒有 callee／allocator／grow 路徑。輸入為 map descriptor、key、ordinal。它按 DWORD hash／probe 操作 `S+D0/D8/DC/E0`。

| RVA／bytes | 作用 |
|---|---|
| `172F7D3 3bd3`、`172F7D5 740e` | Bucket key 等於 empty-key 時選該 bucket |
| `172F7D7 413bd1`、`172F7DA 7409` | Bucket key 等於傳入 key 時也選該 bucket |
| `172F7E3 33c9` | Capacity=0 或遍歷完未命中：RCX=0 |
| `172F7F2 897104` | 先寫 bucket+4 = ordinal |
| `172F7FA 448909` | 再寫 bucket key |

因此：

- **重複 ID 不會被拒絕。** Helper 更新既有 map value，但四個 caller 仍按插入處理 counts／records，可能留下同 ID 的舊 record 或 count 不一致。
- Empty-key 自己不是有效新 ID；把 key 寫成 empty sentinel 不能建立正常 map membership。其值須取實際 map metadata，不能猜成固定 0 或 FFFFFFFF。
- Capacity 為零或 full-map 無匹配：先寫 `[4]`，若繼續才寫 `[0]`。A 型的 records／counts 已改，B 型的 records／pointer 已改而 T 尚未增加；沒有回滾。
- Helper 回傳所選 bucket pointer（RAX），不是一個已定義的成功 boolean。新 reject continuation 不應假裝原正常返回。

本輪候選若維持實際 `172F790`，有效 map、新 key、可用 bucket 與同步可明列為外部前提。若要額外做到 map 異常拒絕前無副作用，需把 lookup／duplicate／free-slot 檢查前移到任何 record、count 或 mover 寫入之前，並處理 check/use 之間的同步；單純加入 ordinal/binding guard 不會完成它。

## 4. Guard 與四陣列改接的原生實作前提

入口前 guard 使用 RAX／R10／R11 不與四 body 的活值衝突：

- 原四 body 沒有任何 R11 讀寫；map helper 自行定義 R11D，mover 自行管理 R11。
- 原入口 RAX 在 count load／offset 計算前被覆寫。
- B 型於 `60CBAD／54085D` 清 R10D，auxiliary 的 relative `+18=0` 依賴這個原指令；A 型不依賴入口 R10。
- 必須保留各自的 entity／flags pointer ABI，尤其 A 型 RDX 或 R8 的 flags pointer 在 guard 後仍需原樣使用。

可以在原 prologue 前核 global-loaded S binding、T<8、P≤D≤T，A 型再核 D==T。這樣拒絕可以保留 entry frame、無 prologue stack 寫入；仍需明列 global／S metadata 讀取的有效性前提。

若使用 interior splice，最早方便的原 count-load 分別為 `60CA94`（6B）、`60CBB0`（7B）、`540863`（7B）、`540934`（6B），均在 capacity fault／flags 解參考／data mutation 之前。此時已存在 prologue frame，不能套用 entry rejection ABI。

Direct array stores 每 body 都是 pointer 1 處、primary 7 處、auxiliary 6 處；沒有 direct property store。A 型 optional mover 會處理所有四組。因此完整八格改接仍須指向同一 mover clone，不能漏掉其 property copy。

將每條 array store 前的 R11 設成 `B-E8`，RBX 保留原 S，可配合 primary disp+20h、aux disp+1E0h、pointer 原 disp，落到 bundle 的 `0／40／3C0` 起點。SIB 裡 RBX 有時是 base、有時是 index，必須分別改 REX.B／REX.X。`MOV R11,imm64` 不改 flags，但指令長度變動需要完整重算內部分支與外部 references；不能逐 byte 覆蓋後仍沿用舊 branch offsets。

## 5. 不是已證「同一次加入的兩個插入階段」

既有静態註冊／ABI 證據只把 `540920` 明確接到 component 239 的第一張建立 callback 表。後續已接合的 property stage 是 **`540AE0→60C640`**，且由 creation flag 控制；不是 `540850`。`540850` 登錄在另一張 `F0B6F0` 系列表，但其完整執行期阶段尚未閉合；`60CA80/60CBA0` 自身派發亦未因此成立。

不能自行把 B→A 排成同一 entity 的一次加入：兩者各自 T++，沒有將 B 的 T 增量抵消。例如從全空狀態先 B 再 A，缺乏中間其他操作時會得到 T=2、D=1，並非單筆完整加入。這是本地效果推導，不排除尚未證明的外層轉換流程。

四個 insert 都没有完成 property、角色資源、後續通知或多人同步；A 的 flags=0 甚至保留 primary 舊 bytes，所有路徑均保留 property 舊 bytes。必須按照原建立／接收／分類生命周期接後續階段，不能把 standalone insert 成功視為完整 entity 加入。

## 固定來源與下一步

完整 body SHA-256：

- `60CA80`：`974935cec813b3ce3f8d62cff1c7f46b17bb306f5bce020e8dde6fdccfc01e4f`
- `60CBA0`：`57a8d7f5d1dbb83f3a9a80918f740ce2065dfc1ac09b10952189b3693a7132c8`
- `540850`：`1264c1c0bf558d390f7dd2bdf075e3f6b3b2465fbfbac5575d6eea8a6ea6d6c0`
- `540920`：`197e6d093ec081d304e0642ffee3e7fc3a71b2eadb36f3a0805d4927af7a5196`
- `172F790`：`57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375`

來源 capture data SHA `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。沿用 [lifecycle](roster_lifecycle_evidence.json)、[player roster](player_roster_evidence.json)、[callback 登錄](spawn_callback_registration_findings.zh-TW.md)及 [binding v3](roster_component_binding_evidence_v3.json) 身分前提，沒有改寫舊證據。

下一步是對原生 candidate 的四種 ABI、A 的真假旗標／P<D move、B 的 deferred append、有效新 key／足夠 map、guard 拒絕與原副作用順序做有限驗證。Map 完整失敗恢復、實際 caller 是否滿足 D==T、其他生命周期與同步依然是具體整合缺口。
