# `60CC70`：有限原生語義與 caller 前提

## 成品需求、決策與停止條件

成品需求是讓 roster 的 tracked／dense／prefix 轉換保留每個有效 entity、四份平行記錄及 ID→ordinal 對應。這份有限審查決定 `60CC70` 是否可以直接改接八格 sidecar，及候選需要拒絕哪些尚未證明安全的狀態。

**結論：不能把保存的原流程稱為 swap。** 在 `P<D<T`、原 D 含不同有效記錄的前提下，它先覆寫原 D，再把覆寫後的資料複製回 P，會遺失原 D。這是固定程式碼的有條件資料流反例；本文件沒有證明真實遊戲會產生或抵達該輸入狀態，也沒有把它宣稱為已實測的遊戲缺陷。

本輪停止於完整 `60CC70`、已核過的 `60C410` ABI／copy 語義、已知 `57E01C` caller 局部及其完整 root 的有限直接位移檢查。沒有重做全 capture 掃描、擴查其他 callee、操作遊戲或產生 emitter。主線另負責原四格真實指令的離線反例驗證；本文件不冒稱已執行該驗證。

## 1. 固定來源、完整 body 與 ABI

沿用固定 build `25480438` capture：

- `capture-report.json` SHA-256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`
- `captured-data.bin` SHA-256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`

`60CC70..60CE76`（右端不含）是三個 chained unwind fragments 合成的完整 root，518 bytes／100 instructions，完整 body SHA-256：

`37b79524a6ed1b43d8ce3244c66288a0b921e1ea5766ba64fd7e0b186c41e452`

| Fragment（右端不含） | Bytes | Unwind RVA | SHA-256 |
|---|---:|---|---|
| `60CC70..60CC97` | 39 | `2425788` | `89c51f53a1a693eaf3048842da571fcfa57aac1d8e4f7724e0e5b21aad42fd6e` |
| `60CC97..60CE65` | 462 | `2425794` | `777d66667eb4e467d075f468781c021d636db7a7dd9a3f766a3d9d9634b68779` |
| `60CE65..60CE76` | 17 | `24257B0` | `08273783d17791c318b35b10a17fddaeb90ecbca1f49ac1aa538d033ce980143` |

入口 `RCX=S`；body 沒有另讀 global。`60CC80` 保存 `RBX=S`，`60CC7A` 以 EDI 保存初始 `D=[S+84]`，`60CC83` 讀 `T=[S+80]`，需要迴圈時 `60CC91` 讀 `P=[S+88]`。這些 counts 及 ordinal 是 unsigned DWORD；32-bit register writes 會清高 32 bits。原函式沒有四格或八格容量 guard。

唯一 callee 是 `60CE24→60C410`，沒有 allocator、釋放函式或析構函式。原 stack prologue 與 nonvolatile 暫存保存仍存在；不能把無 array copy 的分支說成完全沒有 memory writes。各正常出口的 EAX 是最後讀到的 T；不是已定義的成功 boolean。

## 2. 原始順序：兩次 copy 沒有保存目的舊值

定義 `Record[i]` 包含 pointer（8）、primary（70h）、aux（38h）、property（20h）。已核的 shared mover `60C410` ABI 是 `RCX=S, EDX=destination, R8D=source`，只做 copy；`60C410/413` 先比較 low DWORD ordinals，相同即跳至 `60C5BD ret`。

`60CC70` 在同步且 T 不變的前提下，相當於以下資料流；保留 map 修補的先後，沒有把它替換成抽象 swap：

```text
i = D
if i >= T:
    D = T
    return

while i < T:
    p = P
    if p < i:
        Record[i] = Record[p]              # 覆寫 i 的原記錄
        map[Record[i].entity_id].value = i
        p = P                              # 原碼重讀
    copy(destination=p, source=i)           # 此時 i 已可能是 p 的副本
    P += 1
    i += 1
    T = [S+80]                             # 原碼每輪重讀
D = T
```

關鍵原指令：

| RVA／bytes | 已證作用 |
|---|---|
| `60CC89 3bf8`；`60CC8B 0f83d4010000` | `D>=T` 跳早退分支 |
| `60CCA6 3bd7`；`60CCA8 0f8370010000` | `P>=i` 略過 inline copy |
| `60CCAE 448bc2` | `R8D=P`，供 inline source 使用 |
| `60CCB5 4a8b84c3e8000000` | 讀 pointer[P] |
| `60CCBD 8bd7`；`60CCBF 4c8d0cd3` | EDX=i，R9=S+i*8 |
| `60CCC3 498981e8000000` | 寫 pointer[i]；原 pointer[i] 在此前沒有保存 |
| `60CCCA..60CD3A` | 七組 16-byte load/store：primary P→i |
| `60CD46..60CD87` | 三組 16-byte 與一組 8-byte：aux P→i |
| `60CD90/99`、`60CDA1/AA` | 兩組 16-byte：property P→i |
| `60CDB2 498b81e8000000`；`60CDC6 8b7008` | 由已覆寫的 pointer[i] 讀 entity ID |
| `60CE14 41897804` | 所選 map bucket 的 value=i |
| `60CE18 8b9388000000` | 重讀 EDX=P |
| `60CE1E 448bc7`；`60CE21 488bcb`；`60CE24 e8e7f5ffff` | 呼叫 shared copy `(S, destination=P, source=i)` |
| `60CE29 ff8388000000`；`60CE2F ffc7` | P++、迴圈 i++ |
| `60CE31/37/3D/3F` | 重讀 T/P，若 i<T 回到比較 P/i |
| `60CE54 898384000000` | 迴圈結束才把 D 設成 T |
| `60CE6A 898184000000` | 早退亦寫 D=T |

Inline map lookup 接受 empty key 或相同 key；它只寫 bucket value，沒有寫新 key。零 capacity／查找耗盡會令 R8=0，接著寫 `[4]`。因此以下保留性分析仍以前置有效 map、有效 entity pointers、來源 key 存在及同步成立為條件；它不是 map 異常的恢復方案。

## 3. 三種有效 count 分段的結果

本表限定 `0<=P<=D<=T<=capacity`，並假定 tracked 範圍 `[0,T)` 的不同有效 entity 各有正確 map entry。它是用來檢查保留需求的明示模型，並非所有真實 caller 已證的不變式。

| 輸入 | 原指令結果 | 對 records／map 的含義 |
|---|---|---|
| `P<D<T` | 每圈 inline P→i，再 shared i→P；最後 `D'=T`、`P'=P+(T-D)` | 原 pending `[D,T)` 被覆寫；不同原 ID 的 map entries 未刪除／重指向，bijective 對應不保留 |
| `P==D<T` | 每圈略過 inline；shared mover 兩 ordinal 相同而早退；P 每圈加一，最後 P=D=T | 不改 records 或 map；仍有 stack writes、P increments、最後 D write |
| `D==T`（P 可小於 D） | 不進迴圈，寫 D=T 同值後返回 | 不改 records、map 或 P；仍有 prologue 與 D 同值寫入 |

### 最小有條件反例

使用原四格布局中合法的兩筆記錄：`T=2,D=1,P=0`，`Record[0]=A`、`Record[1]=B`，A／B 的 entity ID 不同，map 起始 `A→0,B→1`。

1. Inline `0→1` 使 records 成為 `[A,A]`，原 B 沒有暫存。
2. Inline map 修補使 `A→1`。
3. Shared `1→0` 複製的已是 A，並把 `A→0`。
4. 最後 `P=1,D=T=2`；records 仍 `[A,A]`，map 仍含 `B→1`，但 slot 1 的 ID 已是 A。

這不只是 records 重複：ID B 的 map entry 仍存在，卻無法由 slot 1 還原 B。對四組 parallel records 都成立，不靠 fifth slot 或越界才能出現。

一般 `gap=D-P>0`、`N=T-D>0` 時，P 與 i 每圈同增，gap 不變。若 N 大於 gap，後面的 source 還會讀到較早被覆寫的副本；目的區間 `[D,T)` 最終由原 `[P,D)` 的記錄週期性填入。沒有證据支持把舊 pending records 在這個 body 內視為已妥善搬走或釋放。

若原 D 本來不是有效記錄、與 P 有刻意允許的 alias、或外層已保存／取消該記錄，所需保留契約會不同。那些前提目前未證，不能由 counts 或函式名稱自行補上。相反地，已核 B 型 append 的局部效果確實會把新 entity 與 map 放到 `[D,T)`；這仍不等於已證 B 型 append→此 caller 的執行期連接。

## 4. `57E01C` 的有限 caller 證據

已知 caller root `576CF0..58131E` 是一個保存完整的 unwind fragment：42,542 bytes／11,787 instructions，unwind RVA `24139C0`，body SHA-256：

`d698b632ac6f51e7441873b27dd5baa6364ff3c41751dee8fe718755df26d931`

`576D0D 488bd9` 保存 `RBX=入口RCX`（owner）；既有 lifecycle 身分鏈與 caller 局部對 roster 使用：

```text
57DFB5 488db398fce900    lea rsi,[rbx+E9FC98]
...
57E00F 488d8b1808ea00    lea rcx,[rbx+EA0818]   # S
57E016 8986e8080000      mov [rsi+8E8],eax
57E01C e84fec0800        call 60CC70
57E021 0f57c0            xorps xmm0,xmm0
57E024 488dbb400cea00    lea rdi,[rbx+EA0C40]   # 下一物件
```

局部 `57DFB5..57E02B` 共 118 bytes／28 instructions，SHA-256：`1f6a320c5091b19eacdb04d209cdef181b67f1f773dfa9afb3f2bda664067ae3`。

前方的 count comparisons／兩次 `87B5D0` 呼叫属于 `RSI=owner+E9FC98` 的相鄰物件：`+8E4/+8E8/+8EC` 是 owner `+EA057C/+EA0580/+EA0584`，並非 S 的 `+80/+84/+88`（owner `+EA0898/+EA089C/+EA08A0`）。`57E016` 也只是把前一物件的 count 同步回去，沒有建立 roster 的 P/D/T 前提。

有限檢查完整 caller root 中所有明文 memory displacement 位於 `[EA0818,EA0C40)` 的指令，只得到 `57E00F` 這個取址；對 `60CC70` 的直接目標只得到 `57E01C`。這支持「已知直接 callsite 沒有直接 roster count guard」，**不支持**「所有上游狀態都未受約束」或「反例在真實遊戲可達」：以其他寄存器／衍生地址存取、跨 callee side effect、外部事件與同步契約並未被這次檢查閉合。

## 5. 對下一步候選的限制

1. 在 tracked records 保留契約下，不能只重定位陣列與 shared mover，然後把 `P<D<T` 路徑宣告安全。
2. 若先做有限候選，可在 prologue 前讀取 counts，要求 `P<=D<=T<=8`，並保守拒絕 `P<D<T`。`T==8` 對此處的正常化不應因 insert 的 `T<8` 規則而一律拒絕。這只是限制可接受輸入，不是完成真實 caller 支援。
3. `P==D<T` 與 `D==T` 的原語義可獨立保留，但不得把可通過的退化分支代替完整 compaction 功能。
4. 在理解外層所需順序之前，不能擅自把原兩次 copy 改成 swap／rotate；那會改變原語義，且可能涉及 opaque record 或其他 consumers 的契約。
5. 主線原四格執行反例通過後，下一個有價值的證據是實際 pending／prefix caller 契約：`P<D<T` 是否可達；若可達，誰保存原 D、預期哪筆 entity 進入 prefix。沒有這個來源時應保存反例與明確限制，停止延伸任意 helper 樹。

本輪沒有修改既有正式 evidence、候選 Lua、native source 或 manifest。八個真實帳號、同場任務及角色生命週期驗收均未因此完成。
