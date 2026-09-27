# Roster classify 候選：有限獨立靜態審查

本檔已固定最終 source、evidence 與合成 sample。Evidence 的 allocator ABI 註記修正為 alloc 的 RCX=C[0]=A；原機器碼不變。最終 sample 與使用所列地址／evidence 的獨立重新 build 全欄位一致；此步只產生 Python 中的 bytes／metadata，沒有寫檔或執行模擬器。

| 最終檔案 | SHA-256 |
| --- | --- |
| `Native/roster_classify.py` | `bc4508fadf17726b773ed9c4237f7693405856ccc0b57ddcac4d06e073f46153` |
| `roster_classify_native_evidence.json`／`roster_classify_native_recheck.json` | `f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33` |
| `native_roster_classify_addresses_synthetic.json` | `cddb1d70549de49b3afa824153b9fb0429163fc5d6251f8e29c99b17902addad` |
| `native_roster_classify_bundle_synthetic.json` | `1630e6b0ca7e826be85ea2957c3b2dcfd87f3f63e67e9727e2b3fb6169927172` |

## 結論與實際範圍

在兩個固定原 body、88 個陣列位點、完整分支及必要 helper 邊界內，未找到阻止採納的具體 emitter 缺陷。候選以原語義改接八格 sidecar，沒有把移入 primary 清零誤作四組完整 swap，也沒有把 outer caller 的 flag／通知當成本 body 已處理。

本審查只讀固定 capture、source 與 evidence，使用 Capstone 5.0.7 做完整指令解碼、operand／bytes／branch 比對，並進行三個會拒絕的 bundle 碰撞試建。没有執行遊戲或 host native bytes，沒有重跑 Unicorn suites，没有修改 emitter。執行測試的最終 oracle 與報告由另一支線固定；本檔沒有測試通過次數宣稱。

## 固定範圍

- 移入 `60CF50..60D2F6`：934 B／197 instructions，SHA `09e5e20c35955b4f563f1e971646a8c32c67ff6afdc76e4c1aa796270a6ff33c`。
- 移出 `60D300..60D760`：1120 B／232 instructions，SHA `973e04a016a90f53ba131da1590d9e647b7c9ad8ebec35018ae173d72a22cf6a`。
- create `173B6F0..173B7F4`：SHA `16fa4b7d418012fa547368f3d69d580037d162bdebf2a09c3d0550fca0e8440c`。
- alloc `173B8D0..173BA52`：SHA `18eaaac8e2b019af7f29146be600edb4976a1ad1662546632cc319cbcd7943d9`。
- release `173BC20..173BC97`：SHA `9d66bb642a3255538db168c4cef89b8c3138e4b5036c264be0caee571a3e3150`。
- 有限前提詳見 `five_player_feasibility_20260927/roster_classify_native_prerequisites.zh-TW.md`，SHA `d01bde4b3b814b7278bec95cfe45b15b1f5e9c546d62c277e3ec06f6434d1216`。

## 1. Preflight、方向與兩種 sentinel

preflight 保存 RCX/RDX/R8/R9/RBX/RSI/RDI，共56 bytes；RSI 取入口 RDX entity。先驗 global S binding，再以 unsigned 比較要求 `1<=T<=8`、`P<=D<=T`，要求 map capacity=8。讀 entity ID 後，分別對比 map empty key `[S+DCh]` 與 global invalid ID `[game+3483C20]`，兩者都不是可移動 target。

dry lookup 使用 32-bit hash multiplication、`&7` 起點，最多八個 bucket；命中後要求 `n<D`。enter 用 unsigned `n<P` 拒絕、leave 用 `n>=P` 拒絕，從而 enter 隱含 `P<D`、leave 隱含 `P>0`，保護原本的邊界增加／`P−1`。再讀 sidecar pointer[n]，核其 entity ID 与 map key 一致、record bit0 已是1。

這個 flag 條件對應已知 caller 的過渡狀態：enter 前 target 已 set bit，leave 後才由 caller clear bit。沒有套用會錯拒 enter 的穩態 `bit==(n<P)`。guard 沒有驗證所有 partner／record／map entries；唯一 ID、probe chain、全 tracked bijection、正確 partner、有效指標及同步仍是外部前提。候選也沒有證明所有實際 caller 都會滿足 dense direction。

所有 accepted／reject 路徑都還原七個保存值，回到入口 RSP。reject 以 R10D 傳 reason；RAX/R10/R11/flags 可變，nonvolatile GPR/XMM 與四個入口參數保持。明列56 bytes scratch stack寫入；只保證本 body 尚未改 roster／sidecar／map／entity，也無 helper call。此承諾不能回復 outer caller 先前已改的 bit 或通知；metadata 已將這個限制寫明。

## 2. 88 個 RBP operand 的局部改接

直接從 capture 反解兩 body，列出 memory operand 使用 RBP 且 displacement 位於 `E8h..3B8h` 的完整集合，與 `SPECS.array_sites` 一致：enter 37 個、leave 51 個。逐條檢查 selected instructions 不寫 RBP，不讀寫 RSP，沒有把非陣列 count／map operand 混入。

每個 patch 是 `push RBP; movabs RBP,B−E8h; 原 instruction（只改 disp32）; pop RBP`。驗證修補後的 bytes 除 disp32 外與原指令完全相同；base/index/scale 也相同。pointer delta=0、primary=20h、aux=1E0h、property=2C0h，分別得到 B／B+40h／B+3C0h／B+580h。這同時涵蓋 RBP 被編碼為 base 或 index 的指令。

原 `lea RDX,[RBP+2C8h]` 也在集合內，其結果指向新的 aux base，後續透過 RDX 的拷貝維持原 bytes。其他 RAX／RDX temporary buffer 存取沒有被錯加 sidecar 位移。兩筆 map 更新前的 pointer[n]／pointer[boundary] 重讀亦已改接。

push／mov／pop 不改 flags，也不依賴 R11 在該位點是否 dead。每次 RBP 與 RSP 都在下一條原指令前恢復；沒有在暫時 RSP 改變時執行 call 或分支。原 count／map 操作與 helper 都繼續得到原 S。這些額外 push 的 Windows unwind 尚未建立，不能因正常路徑正確而宣稱异常路徑已可安裝。

## 3. 完整指令、branch 與 ABI

| 方向 | 原指令 | 原 bytes 保持 | 陣列 patch | local branch | helper call | RIP read | 輸出 bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| enter | 197 | 133 | 37 | 17 | 8 | 2 | 1921 |
| leave | 232 | 150 | 51 | 17 | 12 | 2 | 2275 |

全429條原指令都歸入上表且輸出完整解碼到末端；所有原 length 與 capture 解碼相同。所有 local branch 目的逐一比對原 target 所對應的新 instruction 起點，包含落在 array patch 時從第一個 push 開始；沒有跳進 core 或漏掉 restore。兩 global RIP 讀回原 sentinel/global S；20次 helper call 分別指向原 create／alloc／release，並保留原次序。

兩個原 prologue 均保存三個8-byte registers再減40h，內層 `RSP=entry−58h`；Windows x64入口RSP模16為8，因此原call前仍16-byte對齊。preflight已先恢復入口RSP，array wrapper在call前也已恢復，所以暫存 helper 的RCX、RDX、R8、shadow space與alignment不變。原 nonvolatile 保存與原return路徑逐條保留。

## 4. 原語義與資源限制

enter 的 `n=P` 路徑仍先 P++ 再清 primary[P]；`n>P` 路徑仍 pointer swap→zero primary[P]→aux temp swap→property temp swap→兩map更新→P++。primary[n] 原 bytes 留在原位，不能以每entity primary保存作成功標準。leave 的 `n=P−1` 只減P；其他路徑完整交换四組、修兩map、最後減P。

temp create／release 的RCX是24-byte scope C的地址；alloc 的RCX是`C[0]`所指arena entry A，並有size70h／38h／20h、R8=4。原兩次release均保留。原順序在第一個create／alloc前已交換pointer，enter亦已清primary，候選沒有新增rollback；helpers必須成功且無reentry／interleaving。外層flag／通知、不明primary有效性協定、間接allocator介面與實際ownership均未藉此局部source review閉合。

## 5. Bundle 的有限區域

十一函式bundle沿用先前九函式的shared S、B與game base。既有 property pair 對173B8D0只留1-byte `allocator entry`；新bundle精確移除該同名／同址／同大小占位，再加入完整386-byte body。另加入260-byte create及119-byte release、兩份classify code／reject entry／原body，共44個有限known regions。

三個具體試建都正確拒絕：producer code放進原allocator body的內部、enter code重疊receiver code、enter reject entry重疊remove code。沒有為通過檢查任意合併相交區域。

這仍是有限表：reject handler僅1-byte入口，動態arena／map backing／entities／完整外部配置不在表中；通過不代表空間已配置或全部aliases安全。candidate與bundle維持`installable=false`、`game_execution=false`、`multiplayer_verified=false`。

## 下一步與停止條件

本輪靜態範圍已核完，停止擴callee或掃描。下一步由另一支線完成合成Unicorn資料／ABI／暫存helper呼叫與原四格對照，針對enter的不對稱primary語義寫獨立oracle。到真實整合前，仍須建立outer rejection continuation、sidecar生命週期、暫存helper成功與同步契約及Windows unwind；合成八槽不能取代八名真人的任務驗收。
