# `60CC70` 的完整離線壓實證據與實體保留反例

本輪只讀固定 `existing-code-evidence-25480438` 擷取、先前的 consumer inventory 與已固定的 `60C410` mover 證據；沒有操作遊戲程序、產生 native emitter 或安裝 hook。`roster_compact_native_replay.py` 核對完整 `60CC70..60CE76` 原 bytes、三段 unwind fragment、100 條指令邊界、全部可達 CFG、唯一外部 call、四組陣列的讀寫，以及 owner 直接 caller 的有限 slice。`roster_compact_native_evidence.json` 保存完整 `bytes_hex`、每條原指令及 REX/ModRM/SIB/位移編碼、CFG、array sites 和逐步資料流。

## 固定範圍與來源

| 項目 | 值 |
| --- | --- |
| `capture-report.json` SHA-256 | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| `captured-data.bin` SHA-256 | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| capture identity SHA-256 | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |
| 先前 consumer inventory SHA-256 | `0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2` |
| 先前完整 `60C410` mover evidence SHA-256 | `115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242` |

`60CC70..60CE76` 共 518 bytes／100 條指令；完整 body SHA-256 是 `37b79524a6ed1b43d8ce3244c66288a0b921e1ea5766ba64fd7e0b186c41e452`。三段 fragment 如下，end exclusive：

| 範圍 | unwind RVA | fragment SHA-256 |
| --- | --- | --- |
| `60CC70..60CC97` | `2425788` | `89c51f53a1a693eaf3048842da571fcfa57aac1d8e4f7724e0e5b21aad42fd6e` |
| `60CC97..60CE65` | `2425794` | `777d66667eb4e467d075f468781c021d636db7a7dd9a3f766a3d9d9634b68779` |
| `60CE65..60CE76` | `24257B0` | `08273783d17791c318b35b10a17fddaeb90ecbca1f49ac1aa538d033ce980143` |

完整 body 有七個內部條件分支、兩個 return，沒有 RIP-relative memory operand；唯一外部相對參照是 `60CE24 e8e7f5ffff` call `60C410`。這些數量、目標及所有指令邊界均由 replay 核對，不能以此推定其他 caller 或 runtime 命中。

直接 caller 的必要 slice `[57E00F,57E024)` 是 21 bytes，SHA-256 `303568302bce36265a4fc66df105def1da1ed2b73b764c6ed1c7826801491057`，屬於保存的 `[576CF0,58131E)` owner 函式。`57E00F` 以 `lea rcx,[rbx+EA0818h]` 傳入 roster `S`，`57E01C` 直接 call `60CC70`。中間 `57E016` 寫另一位址 `[rsi+8E8h]`；此有限 slice 沒有檢查 `S+80h/+84h/+88h`，所以不能由此證明下述 `P<D` 分支不可達。

## 四組陣列與 count/map 流程

入口 `RCX=S`。`60CC7A` 讀 `D=[S+84h]` dense count，`60CC83` 讀 `T=[S+80h]` tracked count；若 `D>=T`，`60CC8B` 跳 `CE65`，於 `CE6A` 把 `D` 設為 `T`，不搬陣列。若 `D<T`，`CC91` 讀 `P=[S+88h]` prefix count，之後依 `P<D` 選擇是否先執行 inline copy。每次迴圈 `CE29` 增 `[S+88h]`，`CE2F` 增本地 `EDI=D`，`CE3F` 在下一個 `D<T` 時跳回 `CCA6`；結束時 `CE54` 把 `[S+84h]` 設為原本的 `T`。`[S+80h]` 沒有在本 body 變更。

Inline copy 的精確讀寫集合是 pointer 2 讀／1 寫（`CCB5` P 讀、`CCC3` D 寫、`CDB2` 再讀 D），primary 7 讀／7 寫（`CCCA..CD3A`），aux 4 讀／4 寫（`CD46..CD87`），property 2 讀／2 寫（`CD90..CDAA`）。共 29 個 memory operands；每一個原 RVA、base/index/scale、位移及寬度都在 evidence 的 `array_sites`。這些 inline 操作**同向 P→D**，不是交換。`CDB2..CE14` 從新 D slot 讀 entity 指標與 ID，搜尋 `S+D0h` map，將該 ID 的 ordinal 設為 D。其 map capacity 為零或探遍未命中時 `CE11` 把 R8 設零，`CE14` 仍寫 `[R8+4]`；有效 map 是原流程和任何候選的前提。

`CE18` 重新取 `P` 到 `EDX`，`CE1E` 把 `D` 放入 `R8D`，`CE24` 呼叫已固定的 `60C410`。該 mover 的 ABI 為 `RCX=S`、`EDX=目的 ordinal`、`R8D=來源 ordinal`；其 `C423/C426` 保留目的與來源，`C438/C440` 首先把來源 pointer 複製到目的，隨後同向搬三組紀錄並修 map。因此這裡的 shared move 是 **D→P**。若 `P==D`，mover 由相等早返；若不相等，copy 在 inline copy 之後執行。

## 不能宣稱保留 `[0,T)` 所有互異實體

`P<D` 時，原本 D slot 的 pointer 和三組紀錄在 `CCC3` 及後續 stores 遭 P slot 覆寫。`CDB2` 讀的是**覆寫後**的 D；shared mover 隨後把這個新 D 複製回 P。原本 D slot 的實體未先被保存或移往別處。例：`P=1,D=2,T=3`，原 tracked slots `[A,B,C]` 三個實體互異、map `A→0,B→1,C→2`。該次迴圈 P→D 後是 `[A,B,B]`、map 暫設 `B→2`；D→P 後仍是 `[A,B,B]`、map `B→1`，但 `C→2` 指向已不含 C 的槽。最後 `P=2,D=3,T=3`。這是固定指令和已證 mover ABI 的靜態資料流反例，**不是**遊戲執行紀錄。

因 P、D 每輪同增，初始差值 `D−P>0` 持續；`P<D` 的 inline 分支會重複，不能期待後續迴圈恢復被覆寫的原 D 實體。原生實作若承諾保留 `[0,T)` 內每個有效且互異的實體，單憑 `P<=D<=T<=8` 不足以接受此流程。從本 body 可直接證成的 `D<T` 保守情況是 `P==D`：shared mover 相等早返，P 與 D 同增直到 T，陣列及 map 不動。`P>D` 會跳過 inline，直接將 D 複製至 P；若 P 槽亦屬有效實體則也可能覆寫，需另有空槽與容量契約。`D>=T` 走不搬資料的路徑。

此反例不證明 `P<D` 在有效遊戲狀態中真的會發生。若原生生命週期保證 D 或 pending tail 可覆寫、或者保證此分支不可達，必須另以 caller／狀態來源證據釘住；本輪直接 caller slice 沒有這項保證。因此暫不能把 `60CC70` 當成保留所有 unique entity 的八槽「壓實」候選直接編碼。

## 可重跑與界限

以固定 capture 目錄作 `--evidence`，對尚不存在的 output 路徑分別執行 `roster_compact_native_replay.py --output roster_compact_native_evidence.json` 與 `--output roster_compact_native_recheck.json`；兩份 JSON 應逐位元一致。驗證範圍是完整 `60CC70`、`57E00F..57E024` caller slice 和先前已固定的 `60C410` ABI；沒有擴大全域掃描或驗證 map backing、sidecar 初始化/生命週期、hook/unwind、同步或多人任務。
