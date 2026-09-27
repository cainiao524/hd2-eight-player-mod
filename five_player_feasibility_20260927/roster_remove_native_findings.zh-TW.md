# Roster 兩個 remove body 與 map-delete helper 的有限原生證據

本輪只讀固定 `existing-code-evidence-25480438` 擷取及先前已固定的 `60C410` mover 證據，沒有操作遊戲程序、產生 emitter、安裝 hook 或擴大全域 caller 掃描。`roster_remove_native_replay.py` 核對三個完整 body 的 bytes、unwind、全部指令邊界、可達 CFG、外部 RIP/call/tail 參照與關鍵 count/map 指令。`roster_remove_native_evidence.json` 的每個 `bodies[entry]` 包含 `bytes_hex`、逐條原 bytes/asm/編碼位移資訊、CFG、分支、外部 relocation；recheck 逐位元一致。

## 固定 body、ABI 與外部參照

來源 `capture-report.json` SHA-256 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`；`captured-data.bin` 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。三個函式各是完整、單一 unwind fragment，全部指令可由各自入口到達。

| 入口與範圍（end exclusive） | bytes / 指令 | unwind RVA | body SHA-256 |
| --- | ---: | --- | --- |
| `60CEA0..60CF4C` | 172 / 43 | `24257C0` | `0c6e7607bf93a1e9fba1b8eeba998053b316670295e7d8db432352b3ce49cc7d` |
| `540A40..540AE0` | 160 / 40 | `2410A84` | `35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8` |
| `172F8A0..172F9A3` map delete | 259 / 78 | `2567A5C` | `d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f` |

`60CEA0` 的移除紀錄由 `RDX` 傳入；讀 `[RDX+8]` entity ID，保存 `[RDX+10h]` 並於正常尾端放到 `EAX`。`540A40` 由 `RCX` 傳入移除紀錄，讀 `[RCX+8]` ID；其返回值依後續 map/mover 分支而定，不能由這段證據統一命名。兩者分別在 `60CEAA`、`540A49` 以 RIP-relative load 讀全域 roster 指標 RVA `3326468`。外部相對項：

| Body | call / tail 目標 |
| --- | --- |
| `60CEA0` | `60CEBE → 172F8A0`；`60CF0E → 60C410`；`60CF3A → 60C410`，均為 call |
| `540A40` | `540A57 → 172F8A0`、`540AA4 → 60C410` 為 call；`540AD5 → 60C410` 是先恢復 frame 後的 tail-jump |
| `172F8A0` | 無外部 call、tail 或 RIP-relative memory operand |

兩個 remove body 都沒有 inline primary／aux／property copy；只有 `60CEEB`／`540A81` 直接讀 pointer array `[S+E8h+r×8]`，檢查其指向紀錄的 `+14h` bit 0。實際四組資料的搬移取決於既有 `60C410`；若 clone 改接八格 sidecar，所有 mover 邊都需指到同一套已整合的 mover，包含 `540AD5` tail-jump。

## Map 刪除發生在 count guard 之前

直接 helper `172F8A0` 的 ABI 是 `RCX=&S+D0h` map header、`EDX=entity ID`。它按容量／hash 探測 key。命中時 `172F8F9/F8FC` 用 map header `+Ch` 的空 key 覆蓋 bucket key，`172F90C` 取得原 bucket `+4` ordinal；`172F930..172F980` 後移探測鏈中需要保留的 entries，`172F990` 將原 ordinal 回傳於 `EAX`。它不呼叫 allocator。**若 capacity 為 0 或探遍沒有該 key，`172F8EB xor eax,eax` 回傳 0**；這與合法 key 對應 ordinal 0 不可由返回值區分。兩個 remove caller 都先執行這個 helper，之後才改 count，沒有自行區分 miss。

因此一個聲稱可拒絕無效 ID 且不破壞狀態的候選，必須在 helper 造成刪除前以受證 map 查找／所有權前提確認 key 存在、值在 `[0,T)`、key 唯一且 map backing 穩定；不能在 helper 回傳 0 後才猜測是否 miss。`T>0`、`P<=D<=T`、指標有效與分類一致也屬必要前提，不能把 source 的後續 `r==-1` 比較當作安全 not-found 處理：該比較位於先前**無號** `r<D` 分支內，`FFFFFFFFh` 永遠不會由此進入。

## 原始分支的精確 count／搬移次序

令 `T=[S+80h]`（tracked）、`D=[S+84h]`（dense）、`P=[S+88h]`（prefix）、`r` 為 map-delete 回傳的 ordinal，並沿用已證的 `60C410` ABI `RCX=S, EDX=目的, R8D=來源`。

| 條件 | `60CEA0`／`540A40` 原流程 |
| --- | --- |
| `r>=D`（pending 範圍或錯誤值） | `CED4`／`A6A` 先 `T--`；若 `r` 不等於新 `T`，最後以 mover 將舊 tracked 尾槽（來源新 `T`）搬到 `r`。`D/P` 不變。此路徑沒有另檢新 `T` 是否為 0。 |
| `r<D`、slot `r` 的 entity `+14h` bit 0 為 0 | 不改 P；`CF22`／`540AB8` 做 `T--`，`CF28/2B`／`540ABE/C1` 做 `D--`；若新 D 非 0，將舊 dense 尾槽（來源新 `D`）搬到 `r`。 |
| `r<D`、bit 0 為 1 | `CEF9/A8F` 先 `P--`；新 P 非 0 時，將舊 prefix 尾槽（來源新 `P`）搬到 `r`，再以新 `P` 當第二次目的；接著 `T--`、`D--`，最後視新 D 是否為 0，把舊 dense 尾槽搬到該目的。 |

上表的 pending 分支在有效 map、`D<=r<T`、各槽為唯一有效實體等前提下，等同以尾端填洞。它沒有檢查 record bit 0；分類契約須由上層保證。Dense 分支用**實際 entity record bit 0** 決定 P 是否遞減，而非以 `r<P` 直接推斷。因此若要求 prefix `[0,P)` 都是 bit0=1、其他 dense／pending 槽 bit0=0，這項對應關係應在刪除前確定；函式自身沒有建立它。

## 原流程的靜態反例與未證前提

1. **Dense 移除會遺失 pending tail。** 令 `P=0,D=1,T=2`，tracked slots `[A（dense、bit0=0）,B（pending）]` 互異且 map `A→0,B→1`。移除 A：helper 刪 A 回傳 `r=0`；原函式 `T→1,D→0`，因新 D 為 0 不搬任何槽。B 仍在 ordinal 1，但已位於新 `[0,T)` 外，map `B→1` 留下過期值。若 `D<T` 且仍承諾保留全部 tracked unique entity，原兩個 remove body 均不足；需要證明此狀態不可達、pending 可丟棄，或明確補上 pending tail 的資料／map 修復。root 正評估的新增搬移應在**原 dense 路徑完成後、返回前**處理 `Dnew<Tnew`；`60CF35` 有跳過 `CF3A` 的路徑，`540AD5` 則是恢復 frame 後 tail-jump，不能假設能在原 mover 返回後自然執行第三次 call。本檔只固定必要控制流位置，未認證新算法。
2. **缺失 key 與 ordinal 0 混淆。** 令 `P=0,D=T=1`，slot0 是 A，但要求刪除不存在的 X。map helper回傳 0 且不刪 bucket；caller 把 0 當 A 的 ordinal，`T/D` 都減至 0，A 的 map entry 仍在。這個反例要求前置存在性驗證；`r==-1` 分支不能修復。
3. **Prefix bit 不一致可使 P 回繞。** 令 `P=0,D=T=1`，map 命中 slot0，但其 entity `+14h` bit0=1。原碼先 `P--` 成 `FFFFFFFFh`，可能在 `T/D` 更新前就將它作 mover source。這例違反合理的 partition 對應，正說明該對應需要證據或 guard。

反例只證明固定指令在所列狀態的靜態資料流；**沒有證明這些狀態在遊戲執行時可達**，也沒有證明 caller 沒有後續修復。現有 body 亦不證明外部 map、owner 或 sidecar 存活期、同步、Windows unwind、第五至八人實際加入或完整任務流程。

## 重跑

用同一固定 capture 目錄作 `--evidence`，以尚不存在的路徑分別執行 `roster_remove_native_replay.py --output roster_remove_native_evidence.json` 與 `_recheck.json`。兩份 JSON 應逐位元一致；來源改變、任何 body／fragment、關鍵分支、helper 或 relocation 改變時 replay 會拒絕。此輪只展開兩個 remove body 與它們直接需要的 map-delete helper；mover ABI 使用先前固定完整 body 的 SHA。
