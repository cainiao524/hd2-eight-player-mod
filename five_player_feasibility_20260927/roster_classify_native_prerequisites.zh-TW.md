# Roster 分類移入／移出的原生前提

## 本輪範圍與實作決策

本輪支援八格 roster 的分類生命週期：entity ID 對應的 ordinal 改變時，pointer、狀態及 property 必須落在同一份 sidecar，map 與 prefix count 必須一致。本檔只核固定 `60CF50..60D2F6`、`60D300..60D760`，三個直接暫存 helper，以及已固定 caller 中的 flag／通知順序。沒有 live 操作、全 capture 搜尋或任意 callee 擴張；未修改候選 source 或既有正式證據。

**實作決策：保留两個方向不同的原語義，加入合法分類方向的前置 guard，改接四陣列直接與衍生地址。** `60CF50` 只交換 pointer／aux／property，並清零 primary 的 prefix 目的；`60D300` 才交換四組記錄。不能用一個對稱 swap helper 取代兩者，也不能把移入宣稱為每個 entity 的完整 primary 狀態保存。

停止條件是完整 body、必要 map／count／copy 順序、直接暫存資源契約及已知 caller 邊界核完。下一步是 source-faithful emitter 與合成 x64 比對：邊界相同／不同兩路、所有合法分區、非零 ordinal 與完整 byte oracle；真實 caller 可達性、外部資源 ownership、失敗回復及同步仍需後續整合。

## 固定來源與重核

capture report SHA-256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。

captured data SHA-256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。

capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

使用 `research_handoff_20260927/indirect/inspect_capture.py` 的 `Image` 驗證來源後，從固定範圍完整解碼，並逐條核對兩份既有 disasm 文字的 RVA／mnemonic／operands，197 與 232 條全部相符。不是只由文字註解推導。所有範圍下限含、上限不含，地址為 game.dll RVA。

| Body | bytes／指令 | 完整 bytes SHA-256 |
| --- | ---: | --- |
| `60CF50..60D2F6` | 934／197 | `09e5e20c35955b4f563f1e971646a8c32c67ff6afdc76e4c1aa796270a6ff33c` |
| `60D300..60D760` | 1120／232 | `973e04a016a90f53ba131da1590d9e647b7c9ad8ebec35018ae173d72a22cf6a` |
| `173B6F0..173B7F4` | 260／58 | `16fa4b7d418012fa547368f3d69d580037d162bdebf2a09c3d0550fca0e8440c` |
| `173B8D0..173BA52` | 386／106 | `18eaaac8e2b019af7f29146be600edb4976a1ad1662546632cc319cbcd7943d9` |
| `173BC20..173BC97` | 119／32 | `9d66bb642a3255538db168c4cef89b8c3138e4b5036c264be0caee571a3e3150` |

移入的 chained fragments 為 `60CF50..60D044`／unwind `24257CC`、`60D044..60D296`／`24257E4`、`60D296..60D2F6`／`24257F8`。移出為 `60D300..60D39A`／`2425808`、`60D39A..60D70B`／`242581C`、`60D70B..60D760`／`2425834`。三個 helper 也各有三個 chained fragments，以上 SHA 蓋完整合併 bytes。

caller 順序沿用 `roster_property_apply_evidence_v3.json`，SHA `d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22`，並重讀下列關鍵 RVA 的 capture 指令。完整可重播機器證據由本輪 `roster_classify_native_*` evidence／replay 支線提供。

## 入口 ABI、查找及有效前提

兩個 body 的 entity 都由 **RDX** 傳入；`60CF68`／`60D312` 讀 `[RDX+8]` ID。RBP 從 global `[game+3326468]` 載入 S；入口 RCX 不是選取 roster 的來源。已登錄 leaf `540B30` bytes `488bd1e918c40c00` 與 `540B40` bytes `488bd1e9b8c70c00` 均先 `mov RDX,RCX`，再 tail-jump 到相應 body。

初次查找先比對 global `[game+3483C20]` 的 invalid ID，再用 S 的 map header `+D0/+D8/+DC/+E0`。map empty key 與這個 global sentinel 是兩個來源。初次查找 miss／零容量會令 EBX=`FFFFFFFFh`；沒有無副作用的 not-found return。兩 body **不讀 T=[S+80] 或 D=[S+84]，不檢查 target flag，也不寫 entity flag**。

令 `n` 為 map ordinal、`P=[S+88]`。要把它當作 ordered `[0,P)` prefix、`[P,D)` 其他 dense、`[D,T)` pending 的分類轉移，下列是候選應建立的前提，並非原 body 自己證明的事實：

| 方向 | 必要 count／ordinal 範圍 | 已知 caller 的 flag 狀態 |
| --- | --- | --- |
| 移入 prefix | `0<=P<=n<D<=T<=8`，因而 `P<D` | target 已設 bit0=1，但仍在舊 prefix 之外；若 `n>P`，舊 P 的 partner 是未分類 dense member |
| 移出 prefix | `0<=n<P<=D<=T<=8`，因而 `P>0` | target 在 body 期間仍 bit0=1；交換後才由上層清除 |

map backing、唯一 ID、所有 active records 的 bijection、正確 probe chain、target 與 boundary partner 都是有效記錄且 map ordinal 正確，及 S／sidecar 生存期、同步均是前提。僅找到 target 不足以保證後面兩筆 map update 安全。這個有限分析沒有證明每個實際 caller 都滿足上述 direction；特別是 pending target 的分類協定仍不能從 body 讀出的資料推定。

重複移入 `n<P` 會錯增 P；重複移出 `n>=P` 會錯縮 P。移出 `P=0` 時 `P−1` 下溢；若同時 map miss，`n==FFFFFFFFh` 與下溢值相等，原相等路徑可直接把 P 寫成 `FFFFFFFFh`。無效 ID 必須在變更前拒絕。

## 60CF50：移入前段，不是四陣列 swap

初次查找得到 `n`（EBX／R15），舊 P 載入 R14D。

### `n==P`

`60CFEB`（`898588000000`）先寫 P+1，然後 `60CFF5..60D025` 七次 MOVUPS 清零 `primary[P]` 的完整 70h bytes。pointer、aux、property、map 不變；沒有暫存 helper call。

### `n!=P`

1. `60D049/059` 讀 pointer[n]／pointer[P]；`60D064/06C` 交換兩 pointer。
2. `60D07D..60D0AD` 清零 **primary[P]**，完整 70h bytes。**primary[n] 不搬、不清、仍保留原 bytes。** 舊 primary[P] 丟棄；移到 n 的舊 P entity 不會收到其原 primary[P]。如主張每個 entity 都擁有必須保存的有效 primary，這段原指令不能支持該主張；需要證明非 prefix primary 的有效性／初始化協定。
3. 用 size38h 暫存交換 aux[P]／aux[n]，釋放該 scope；再用 size20h 暫存交換 property[P]／property[n]，釋放 scope。property 內 network index 隨整筆 bytes 移動，沒有覆寫成新 ordinal。
4. `60D200` 從已交換的 pointer[n] 讀舊 P entity ID；`60D264`（`41895804`）寫其 map value=n。
5. `60D26A` 從 pointer[P] 讀 target ID；`60D2D3`（`45897004`）寫其 map value=舊 P。
6. `60D2D7`（`ff8588000000`）最後 P++。T、D 不變。

兩筆後置 map lookup 都把「遇到 empty bucket」當作取得寫入位置，零容量／遍歷失敗則令 R8=0，接著仍寫 `[R8+4]`。沒有建立遺漏 key；只能在前述 map 完整性及同步前提下保留原行為。

## 60D300：移出前段，四組完整交換

初次查找 n 在 EBX；`60D375/37C` 令 R15D=舊 P−1，記為 q。

- `n==q`：`60D384`（`4489bd88000000`）只寫 P=q，直接返回；四陣列、map 與暫存 allocator 都不碰。
- `n!=q`：`60D3A7/3C1` 讀 pointer[q]／pointer[n]，`60D3C9/3D1` 交換。接著依序用 70h、38h、20h 暫存完整交換 primary、aux、property；沒有清零替代 swap。
- `60D677` 讀 pointer[n] 的舊 q entity，`60D6DB`（`41895804`）寫其 map value=n。
- `60D6DF` 讀 pointer[q] 的 target，`60D743`（`45897804`）寫其 map value=q。
- `60D747`（`ff8d88000000`）最後 P--。T、D 不變。target 在新 prefix 外，但其 bit0 仍是 1，直到外層 caller 完成清除。

後置 map lookup 的 miss 風險與移入相同。原 body 沒有通知、entity bit 清除或獨立 cleanup；不能因為移出 prefix 就提前釋放四陣列 record。

## 暫存資源協定與先後

每一組完整 swap 都使用 stack 中 `C=RSP+20h` 的 **24-byte scope**，且循序使用同一 C：

| 方向／資料 | create `173B6F0` | alloc `173B8D0` | release `173BC20` 兩次 |
| --- | --- | --- | --- |
| 移入 aux38h | `60D0B5` | `60D0C8` | `60D166`、`60D170` |
| 移入 property20h | `60D17A` | `60D18D` | `60D1F1`、`60D1FB` |
| 移出 primary70h | `60D3DE` | `60D3F1` | `60D51C`、`60D526` |
| 移出 aux38h | `60D530` | `60D543` | `60D5E1`、`60D5EB` |
| 移出 property20h | `60D5F5` | `60D608` | `60D668`、`60D672` |

create／release 的 RCX=&C。alloc 的 RCX=`[C]`、RDX=size、R8=4；R8 是由 `lea r8d,[rdx−34h/1Ch/6Ch]` 得出，五次皆為 4。RAX 返回獨立暫存 buffer。拷貝順序為 boundary→temporary、target→boundary、temporary→target；不是把暫存指標當成 S／sidecar 別名。

三個 helper 的有限內部契約：

1. **173B6F0**：先清 C 的三個 QWORD，透過全域介面 `+D8` 的返回索引選擇一個 24-byte arena entry A。未建立時可透過間接 allocator `+58` 配 100000h backing bytes 與 20h block header，alignment 8。最後 `C[0]=A`、`C[8]=A.current_block`、`C[10h]=block.used_offset`。此處只證索引用途，沒有對未知介面返回值強行命名 thread ID。
2. **173B8D0**：RCX=A、RDX=size、R8=alignment。對非零 size 做 alignment rounding，原子增加 current block 使用量；容量不足時可能配置新 block／backing 並接入前一 block，返回 aligned data pointer。此路徑有間接介面呼叫、原子操作及重試；不是可以無條件 stub 成無副作用的 malloc。size=0 的獨立路徑返回 0，但本次五個 size 均非零。
3. **173BC20**：直到 A.current_block 回到 C 保存的 block 前，逐個退鏈，經間接 `+60` 分別釋放 backing／block；最後把保存的 used_offset 寫回舊 block。第二次 release 在沒有交錯／重入更改時只是再次恢复同一 offset；本候選應保留原兩次呼叫，不能因猜測重複而省略。

**兩 body 在第一個 create／alloc 前已交換 pointer；移入還清零 primary[P]。** 原碼沒有 alloc-null branch、rollback 或異常恢復。因此 guard 必須早於首次共享修改，並把暫存 helpers 正常成功返回、資源同步與外部 callback 契約明列為前提。離線 source-faithful 候選不能宣稱 allocation failure 原子性。本輪已到必要 helper 邊界，沒有展开 `+D8/+58/+60` 的實際執行期目標。

## Caller flag／通知邊界

已知移入 caller `FDBB40`：`FDBCE6` 的 `834e1401` 先 `or [entity+14h],1`；`FDBDD3` 載 owner 的 `+F0F3B0` callback，`FDBDE7/DEA` 以 RCX=entity 派發，component239 經 `540B30` 進 body。後續 `FDBE33/4A` 才派發 `+F0FDD0`（239 為空 leaf）。因此 target 尚在 n>=P 時 bit 已是1，分類 guard 不能套用 remove 的穩態 `flag == (n<P)` 條件。

已知移出 caller `FDBEA0`：`FDBF58` 測 bit0；`FDBF80` 呼叫 `581E10`。該函式先在 `581F53/66` 派發 `+F11210` 通知表，再在 `581F83/96` 派發 `+F107F0` 移出表。component239 前者為 `540B60` 的條件式通知，後者經 `540B40` 進 `60D300`。返回後 `FDBF85` 的 `836614fe` 才 `and [entity+14h],FFFFFFFEh`。

因此移出 body 返回的暫態也不满足穩態 flag／prefix 等價關係。只在 body 內拒絕，不能回復 caller 已完成的 bit 設定或通知；reject continuation 必須終止／恢復整個外層操作，不能自行正常 `ret` 讓 caller 繼續當作成功。本輪證明的是這些既有 caller 的順序，沒有宣稱所有 dispatch path 已閉合。

## 八格 emitter 的必要修改與驗證切點

- 入口 guard 是最清楚的無共享寫入切點；若用 body 內 guard，至少早於移入相等路徑 `60CFEB`／交換路徑 `60D064`，以及移出相等路徑 `60D384`／交換路徑 `60D3C9`。不能只在第一個 allocator call 前檢查。
- 保留原 S 作 map／count base，不能永久 bias RBP；原 RBP 同時被編碼為 memory base 或 index。按實際 operand 改接 pointer B、primary B+40h、aux B+3C0h、property B+580h。
- `lea RDX,[RBP+2C8h]` 的衍生 aux 地址也必須改接。RAX／RDX 之後可能代表獨立 temporary buffer，不能對所有相同寄存器訪問盲目加 delta。兩筆 map 更新前重新讀 pointer 的 operands 亦屬必要改接點。
- 所有內部分支與跨 fragment 回跳保持同一原 instruction 邊界；直接三個 helper call 與兩個 global RIP 目標需完整重定位。保留非揮發保存、stack shadow／alignment 與原返回行為；Windows unwind 需另建。
- 測試應分清 source-faithful bytes 與新的分類前提：移入 `n=P`／`n>P`、移出 `n=P−1`／`n<P−1`，合法 P/D/T 邊界，原四格與八格四陣列 byte oracle、兩map更新、temporary call次序／參數、同ordinal無額外配置，以及先拒絕invalid方向／sentinel／missing ID。primary[n] 原位保留的事實應進 oracle，不能把預期錯寫成完整swap。

完整成品仍缺 actual caller 對 direction／primary 有效性／暫存資源的保證、外層拒絕協定、sidecar 配置與同步、其他讀者整合，以及真人同場任務驗證。本檔不將本局部候選當成已可安裝或已完成八人功能。
