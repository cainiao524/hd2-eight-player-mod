# Roster 移除：原生前提與完整分段候選

## 需求、決策與停止條件

成品需求是移除八格 roster 中指定 entity，保留所有其他 tracked entities、四組平行記錄、prefix／dense／pending 分段與 ID→ordinal map。本輪讀兩個完整移除 body、必要的完整 map deletion helper，沿用已核 `60C410` mover 及既有 callback lifecycle 證據；沒有全 capture 掃描、live 操作或修改候選。

**結論：原碼支援 prefix 成員的直接移除，不必一律先 demote；但有序 `P<=D<=T` 本身不保證原移除保留所有 tracked records。** Map miss／零 capacity 回傳 0，原 caller 會把它當 ordinal；dense 移除在 `D<T` 時亦沒有保留最後一筆 pending。前者必須 pre-delete 查核，後者可提出額外 pending-tail repair 的完整分段候選，不能以限制所有 dense 移除為 `D==T` 代替完整支援。

停止條件：固定來源與反例機制明確，候選在明示模型下可證保留，下一步可直接交 emitter／原指令及八格模擬驗證；實際 caller、同步、opaque ownership 與外部 aliases 保留為整合契約，不無限追查其他 callees。

## 1. 固定範圍與兩種 ABI

沿用 build `25480438` capture，data SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`、report SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。以下各為一個完整 unwind fragment，右端不含。

| Body | Bytes／instructions | Unwind RVA | SHA-256 |
|---|---:|---|---|
| `60CEA0..60CF4C` | 172／43 | `24257C0` | `0c6e7607bf93a1e9fba1b8eeba998053b316670295e7d8db432352b3ce49cc7d` |
| `540A40..540AE0` | 160／40 | `2410A84` | `35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8` |
| `172F8A0..172F9A3` | 259／78 | `2567A5C` | `d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f` |

- **Legacy `60CEA0`：** RDX=entity pointer；入口 RCX 不用來選 S。`60CEAA` 從 global `3326468` 取 S→RDI；`60CEB1` 保存 entity→RBX；`60CEB4` 讀 entity+8 key。Map helper 返回後，`60CECA` 讀原 entity+10 DWORD→EBX；最終 `60CF3F mov eax,ebx` 返回這個值。不能把返回值改成 ordinal 或 success boolean。
- **Registered `540A40`：** RCX=entity pointer；`540A46` 讀 entity+8 key，`540A49` 從同 global 取 S→RBX。沒有 legacy 的 entity+10 返回值協定；末段可能 tail-jump 到 mover。不能把它當成與 legacy 完全相同的返回 ABI。

兩者唯一直接陣列 operand 是 dense 分支讀 entity pointer：`60CEEB`／`540A81` 的 `S+E8+n*8`。所有 primary／aux／property 搬移透過 shared mover，故 emitter 仍須改接這個 pointer read，並讓所有 mover edges 指向同一四陣列 sidecar clone。

## 2. Map deletion 的準確結果與副作用

`172F8A0` 輸入 `RCX=&S.D0`、`EDX=entity key`；header 包含 bucket pointer、capacity、empty key 與 hash multiplier。以 `capacity-1` mask 逐格 probing；第一段不因讀到 empty key 就停止，而是比對 key，最多 capacity 次。

| RVA／bytes | 作用 |
|---|---|
| `172F8BF 4585db`；`172F8C2 7427` | Capacity=0 跳 miss |
| `172F8D9 443914d7`；`172F8E1 7416` | 比對 key，命中才進刪除 |
| `172F8EB 33c0` | Miss 回 EAX=0，沒有 bucket mutation |
| `172F8F9 8b410c`；`172F8FC 418901` | 命中後先把 bucket key 設為 empty marker |
| `172F90C 418b6904` | EBP 保存被刪 key 原 ordinal/value |
| `172F972 498904d3` | Backshift 搬整個 8-byte key/value pair 至 hole |
| `172F97C 42891403` | 把來源 bucket 的 key 設為 empty；value 不清零 |
| `172F990 8bc5` | 返回刪除前的 ordinal/value |

它沒有 allocator 或 callee。Backshift 會改變其他 keys 的 bucket 位置，但搬的是完整 pair，ordinal value 不因此改變。

**Miss 和合法 ordinal 0 返回完全相同的 EAX=0。** 兩個 remove caller 沒有檢查成功標誌，因此 missing ID／capacity 0 不是安全 no-op。原碼中較後的 `cmp edx,-1` 位於 unsigned `n<D` 分支；在有效 DWORD D 下，FFFFFFFF 不可能進入該分支，不能當作 miss guard。

也須拒絕 key==empty marker。否則 helper 可能把空 bucket 當命中，再以它的舊 value 做 ordinal。Empty marker 由實際 header 提供，不能猜固定 0 或 FFFFFFFF。

## 3. 原移除順序

定義 `T=[S+80]`、`D=[S+84]`、`P=[S+88]`、`n=deleted key 的原 ordinal`；`copy(dst,src)` 表示已核 `60C410`：搬四份記錄、修來源 entity 的 map value，來源 bytes 留在原槽，兩 ordinal 相同則早退。

原 body 先呼叫 deletion helper（`60CEBE`／`540A57`），然後分支：

### Pending target：`n>=D`

1. T--（`60CED4`／`540A6A`）。
2. 取新 T 作 source；若 `n!=Tnew`，`copy(n,Tnew)`。
3. D／P 不變。

這裡 `60CEE1`／`540A77` 的比較 flags 經無條件跳躍保留到末段 JE；JE 判斷的是 n 是否等於新 T，不是新 T 是否為零。有效 `D<=n<T` 輸入時，它保留其餘所有 tracked records。

### Dense target：`n<D`

1. 從 pointer[n] 讀 entity+14 bit 0。
2. 若 bit 0 為 1：P--；若 Pnew≠0，`copy(n,Pnew)`；隨後把 hole ordinal 改為 Pnew。兩處第一 mover call 是 `60CF0E`／`540AA4`。
3. T--，D--。
4. 若 Dnew≠0，`copy(hole,Dnew)`；否則略過。

bit 0 為 0 時不改 P，hole 仍為 n。注意 `60CF06`／`540A9C` 的 JE 使用 **P-- 的 ZF**：Pnew=0 才略過第一 copy，不是判斷 n==Pnew。後者由 mover 的相同 ordinal 早退處理。

最後 mover 在 legacy 是 `60CF3A call`，回來再返回 entity+10；registered 是 `540AD5 tail-jump`，在跳出前 `540AD0/AD4` 已釋放 frame／還原 RBX。

## 4. Prefix 契約及 dense／pending 保留問題

### 有效 prefix 可以直接 remove

在同步、有效唯一 records/map、`0<=P<=D<=T`，且 prefix membership 與 entity bit 對應的模型下：

- `n<P` 應具有 bit 0=1；P 必須大於 0。
- `P<=n<D` 應具有 bit 0=0。
- 對有效 prefix 成員，原 remove 自己減 P，用 prefix tail 填原洞，再由 dense tail 填 prefix 邊界洞；`P=1`、刪最後 prefix、`P=D` 都包含在這條流程內。

因此不能加入「所有 prefix 一律先 demote」的推論或限制。若外層確實先 demote，則它必須完整更新四組 records、map、P 與 entity bit，remove 應重新查新的 ordinal；不能只清 bit，也不能在 P 已減後仍以舊 bit 讓 remove 再減一次。

已存 lifecycle 證據把 `540B20→605950` 放在 registered 實際移除之前，之後才是 `FDCC53/63` 派發 `540A40`。另一條 demotion 有自己的 callback 與 bit-clear 順序。這些資料不能證明每次移除前一定已 demote；本地 remove 的 bit 分支也不能用來跳過既有 pre-removal 清理／通知。

### 原 dense 移除在 D<T 下缺少 pending 保留

原 dense 流程只讀寫 old `[0,D)`，卻同時將 T 減一。若 old `[D,T)` 內有有效不同 pending records，old `[T-1]` 會掉出新 tracked 範圍，且新 pending 起點 `D-1` 留下已移去 dense hole 的舊 dense-tail 副本。

最小例：`T=2,D=1,P=0`、records `[A,B]`，移除 dense A。Map A 被刪，T=1、D=0，因 Dnew=0 不搬移；tracked slot 0 仍 A，B 在 slot 1 範圍外，map B 仍指 1。有序 counts 並未阻止遺失。這是資料流推導，不能直接宣稱遊戲 caller 真能抵達該狀態。

## 5. 完整分段候選：新增 pending-tail repair

主線提出的候選保留原 prefix→hole、dense-tail→hole 與原 P--／T--／D--順序；在 dense 分支完成後新增：

```text
if Dnew < Tnew:
    copy(destination=Dnew, source=Tnew)
```

這是**新增候選語義，原指令沒有這一步**。對有效 unique tracked records/map、prefix flag 契約及同步模型，可證它保留全部 survivors：

1. 原 dense 移除只碰 old `[0,D)`，所以若 D<T，old lasttracked `T-1` 在前兩次搬移中未被動過。
2. `Dnew=D-1`、`Tnew=T-1`；第三 copy 用 old lasttracked 填新 pending 起點。
3. 原 pending `[D,T-2]` 保持原位；加上搬來的 old lasttracked，構成新 `[Dnew,Tnew)`，數目仍為 T-D。
4. 每次 copy 都透過同一 mover 修 map；刪除 key 不會由這個 repair 重新引入，因 source 是另一個有效 pending survivor。
5. D==T 時條件為假，不增加 record／map 寫入；既有 baseline 資料 bytes 行為可維持。Pending target 分支保持原 lasttracked→hole。

這也涵蓋 D=1、P=0／1，刪除後 Dnew=0 而 Tnew>0 的情況，不能因原碼略過最後 dense copy 而略過新 repair。

兩個本地 body、deletion helper 及 shared mover 在這個區段沒有資源 callback／allocator／析構，未見直接反證第三 copy 的指令。原 mover 已使用 copy 與保留舊 source bytes 的協定。但完整 resource ownership、其他 consumers 的 slot aliases、重入／同步及真實 caller 的預期順序尚未閉合；這是候選驗證的明示前提，不是已證遊戲等價性。

Registered 原末端是 tail-jump。需要 repair 的 dense-pending 分支必須改成可返回的 mover call，再執行 repair；不能先套用 `540AD0/AD4` 的 frame teardown，卻仍按原內部 call ABI 繼續呼叫。Legacy 必須保留原 entity+10 返回值。D==T baseline 的返回值與 nonvolatile／stack 狀態也須由實測 oracle 核對。

## 6. Pre-delete guard 與 ABI 要求

必要 guard 須早於 `172F8FC` 首次 bucket 寫入；只在 helper 返回後檢查會留下已刪的 key，不能稱為無副作用拒絕。

前置讀查至少建立：

1. Global S 等於候選綁定；S、sidecar、entity 與 map header／bucket span 有有效且穩定的存活期。
2. `1<=T<=8`、`P<=D<=T`；不是 insert 的 T<8，滿八筆仍應可移除。
3. Entity key 不等於實際 empty marker；map capacity／backing／mask 契約有效。此 helper 使用 capacity−1 mask，不能僅憑非零即宣稱任意 capacity 都有效，也不必猜 map capacity 等於 player capacity。
4. 以只讀 probing 找到**同 key 的 bucket**，讀出 n，要求 `n<T`；不能以 helper 回0辨別 miss。若採逐指令相符的 lookup，按 hash／mask 最多 capacity 次查找，需保留有效 map 契約及同步，避免 check/use 間變動。
5. Pointer[n] 的 entity ID 與 key 對應；dense 分支需有效 readable pointer 和 bit／prefix membership 一致。bit=1 且 P=0 是 underflow，必須拒絕；不能只看有序 counts。
6. 所有可能搬移的 source 與 map entries有效且屬於同一 S／sidecar；完整 tracked unique map／records 是保留證明前提。這些條件不可藉讀到目前 counts 就全部假定已成立。

可在原 prologue 前 guard，保留 registered RCX entity 或 legacy RDX entity，以及所有 nonvolatile；RAX／R10／R11 的入口值不是這兩個 body 的資料輸入。完整讀查若需 stack 暫存，拒絕契約須相應還原，不能仍宣稱完全沒有 stack writes。

也可選 helper 前的已建 frame 切點：legacy `60CEB7` 的 7-byte `lea rcx,[rdi+D0]`，registered `540A50` 的 7-byte `lea rcx,[rbx+D0]`。此時兩者 RSP 都是 entry−28h；legacy 保存 RBX 在 current RSP+30h、RDI 在 +20h，registered 保存 RBX 在 +20h。Interior 拒絕不能冒用 entry-frame rejection ABI。

## 下一步

由主線對各類 removal（pending、dense nonprefix、prefix，包括邊界 ordinal）實作並以固定原四格 baseline、八格獨立 survivor／map oracle、missing/empty key 與所有有序 counts 驗證。新增 repair 須明示與原碼不同的 D<T 語義；分類、pre-removal callback、其他讀者與真實八人 lifecycle 仍需後續整合。本輪沒有以較小接受域替代完整移除需求。
