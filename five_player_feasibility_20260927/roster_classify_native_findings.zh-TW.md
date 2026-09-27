# 60CF50／60D300 roster 分類完整機器碼證據

## 範圍與重跑

本輪只讀 Steam build `25480438` 的已保存 capture。`capture-report.json` SHA-256 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，`captured-data.bin` 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，capture identity 為 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。`roster_classify_native_replay.py` 對上述 SHA、完整 body、三段 chained unwind、全部指令解碼、CFG、外部 relocation 目的地和四陣列 operand 數量施加斷言。沒有操作遊戲程序或安裝 hook。

| 函式 | 完整範圍 | bytes／指令 | 完整 bytes SHA-256 | 陣列 sites／外部 relocations |
| --- | --- | ---: | --- | ---: |
| 移入 `60CF50` | `[60CF50,60D2F6)` | 934／197 | `09e5e20c35955b4f563f1e971646a8c32c67ff6afdc76e4c1aa796270a6ff33c` | 37／10 |
| 移出 `60D300` | `[60D300,60D760)` | 1120／232 | `973e04a016a90f53ba131da1590d9e647b7c9ad8ebec35018ae173d72a22cf6a` | 51／14 |

兩份 evidence 的 `bodies['0x60cf50']`、`bodies['0x60d300']` 均有 `bytes_hex`、每條 `instructions` 的 RVA／bytes／SHA／encoding、完整 `cfg`、`branches`、`external_relocations`、`array_sites` 與三個 fragment。每條 root 指令都從入口在靜態 CFG 中可達，所有 branch target 都是同一完整 body 的指令邊界；不存在外部 branch 或間接 call。`173B6F0`、`173B8D0`、`173BC20` 三個直接 helper 亦固定完整 body bytes、指令、CFG、間接 call 與 critical sites，但不繼續追其全域 callback。

在同一固定 capture 上執行以下 PowerShell 指令兩次，輸出至尚不存在的不同路徑即可重核；`recheck.json` 與 `evidence.json` 逐 byte 相同：

```powershell
$cap = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
$env:PYTHONPATH = 'eight_player_candidate_20260927/.native-test-deps'
py -3.12 -B five_player_feasibility_20260927/roster_classify_native_replay.py --evidence $cap --output NEW-roster-classify-native.json
```

replay SHA-256 為 `a3ec7cd1b764a5344b64f0edb5753cfb5598a913b297d01dbadc67815e59cbbe`；evidence 與 recheck 的 SHA-256 同為 `f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33`。

## ABI、查找與先後

兩 body 的 RDX 是 entity record，`60CF68`／`60D312` 讀其 `+8` ID。入口 RCX 不用來選 roster；RBP 由 RIP global `3326468` 載入 S，另一 RIP global `3483C20` 提供 invalid ID 比對。兩 body 使用 `S+D0` map pointer、`S+D8` capacity、`S+DC` empty sentinel、`S+E0` hash multiplier inline 線性探測；**沒有直接 map helper call**。查無 key 或零容量會設 ordinal 為 `FFFFFFFFh`，而非安全返回。交換後另外各探測兩個 entity ID 並把新 ordinal 寫入 bucket `+4`；若後置探測找不到可寫 bucket，原碼仍可能向 `[0+4]` 寫入。因此目標與邊界 partner 均需有正確、唯一、可探測的 map entry。

令 `P=[S+88]`、查得 ordinal 為 `n`。`60CF50` 在 `n==P` 時先於 `60CFEB` 寫 `P+1`，隨後 `60CFF5..60D025` 清零 `primary[P]` 的 70h bytes，直接返回。`n!=P` 時依序交換 pointer[n]／pointer[P]，清零 **primary[P]**（不交換、不清 primary[n]），用 38h 暫存交換 aux，用 20h 暫存交換 property，修正兩筆 map ordinal，最後在 `60D2D7` 增 P。完整 property bytes 包括其中 network index 隨 entity 移動。

`60D300` 先令 `q=P-1`。`n==q` 時在 `60D384` 寫 `P=q` 後返回，沒有四陣列或暫存操作；`n!=q` 時依序交換 pointer、用 70h 暫存完整交換 primary、38h 交換 aux、20h 交換 property，修正兩筆 map ordinal，最後在 `60D747` 減 P。兩 body 都不自行改 T、D 或 entity flag。不能把移入的 primary 清零與移出的完整四陣列交換合併成同一語義。

四陣列直接 operand 數量如下，皆以 RBP 作 S 的 memory base **或 index** 檢出，並固定 SIB／REX、displacement offset／size。`lea [RBP+2C8h]` 衍生的 aux alias 也計入。

| body | pointer `E8h` | primary `108h..168h` | aux `2C8h..2F8h` | property `3A8h/3B8h` |
| --- | ---: | ---: | ---: | ---: |
| `60CF50` | 6 | 14 | 9 | 8 |
| `60D300` | 6 | 28 | 9 | 8 |

sidecar 目標四基址為 B+0、B+40h、B+3C0h、B+580h；S 仍是 count／map base。不能對暫存 RAX／RDX 指標的拷貝操作盲目套 sidecar 位移。兩 body 的 external relocation 恰是兩個 RIP global 加各次對 `173B6F0`、`173B8D0`、`173BC20` 的 rel32 call，均為 disp32／imm32。沒有其他外部直接目標。

## 暫存 helper 的有限契約

兩方向的交換路徑，在 **pointer 已交換** 之後才建立暫存 context `C=&[RSP+20h]`；移入還先清零 primary[P]。`173B6F0` 接 RCX=&24-byte C，建立／保存 arena entry A 與目前 block／offset。`173B8D0` 接 RCX=`C[0]=A`（**不是** &C）、RDX=size（70h／38h／20h）、R8=4，返回 RAX 暫存 buffer；`173BC20` 接 RCX=&C，沿 block 鏈退回 C 的快照。每次配置之後原碼呼叫 release **兩次**，必須保留。三 helper 分別固定為：

- `173B6F0..173B7F4`：260 bytes；SHA `16fa4b7d418012fa547368f3d69d580037d162bdebf2a09c3d0550fca0e8440c`。
- `173B8D0..173BA52`：386 bytes；SHA `18eaaac8e2b019af7f29146be600edb4976a1ad1662546632cc319cbcd7943d9`。其 `173B9EB` NOP 從靜態入口不可達，但完整 body bytes 仍有固定。
- `173BC20..173BC97`：119 bytes；SHA `9d66bb642a3255538db168c4cef89b8c3138e4b5036c264be0caee571a3e3150`。

helper 內透過全域介面間接配置／釋放、原子更新，與並發及失敗路徑有關。本輪停在這三個直接 helper 的呼叫邊界，沒有展開 callback 目標。原 body 在第一次 allocation 前已有共享記錄 mutation，沒有 alloc-null 分支或 rollback；若後續 emitter 增前置 reject，必須在第一個 pointer/count/primary mutation 前，且正常完成暫存操作是外部前提。細部 caller flag／通知順序與 24-byte scope 核對見 `roster_classify_native_prerequisites.zh-TW.md`。

## 證據界限

此固定 body 能證明既有機器碼的讀寫、分支與 helper 先後，不能單獨證明實際 caller 永遠傳合法方向。安全的候選前提至少包括有效 S/binding、`P<=D<=T<=8`、移入 `P<=n<D`、移出 `n<P`、目標與 boundary partner 的四陣列／map 有效性，以及暫存 allocator 成功與生命週期同步。尤其移出 `P=0` 時 `P-1` 下溢；map miss 的 `n=FFFFFFFFh` 可命中此值並把 P 寫成 `FFFFFFFFh`。本證據檔不驗證 native emitter、安裝或多人執行。
