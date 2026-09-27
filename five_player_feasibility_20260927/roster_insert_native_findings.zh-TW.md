# Roster 插入函式的有限原生證據

此輪只讀固定的 `existing-code-evidence-25480438` 擷取與先前的 roster consumer inventory；沒有讀取遊戲程序、安裝 hook 或執行原生候選。`roster_insert_native_replay.py` 核對 unwind fragment、完整 body SHA-256、每條指令邊界、可達 CFG、外部相對參照，以及四組陣列操作。`roster_insert_native_evidence.json` 的每個函式都有 `bytes_hex`、逐條 `instructions`（原 bytes、RVA、asm、REX/ModRM/SIB/位移與立即數位置）、`cfg`、`array_sites`、`external_relocations`；map helper 亦保存完整 body。

## 固定來源與覆蓋

| 項目 | 固定值 |
| --- | --- |
| `capture-report.json` SHA-256 | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| `captured-data.bin` SHA-256 | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| capture identity SHA-256 | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |
| 先前 consumer inventory SHA-256 | `0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2` |

| 入口與完整範圍（RVA，end exclusive） | bytes / instructions | body SHA-256 | unwind RVA |
| --- | ---: | --- | --- |
| `60CA80..60CB9F` | 287 / 57 | `974935cec813b3ce3f8d62cff1c7f46b17bb306f5bce020e8dde6fdccfc01e4f` | `2425774` |
| `60CBA0..60CC6B` | 203 / 36 | `57a8d7f5d1dbb83f3a9a80918f740ce2065dfc1ac09b10952189b3693a7132c8` | `2425780` |
| `540850..54091E` | 206 / 37 | `1264c1c0bf558d390f7dd2bdf075e3f6b3b2465fbfbac5575d6eea8a6ea6d6c0` | `2410A70` |
| `540920..540A3E` | 286 / 57 | `197e6d093ec081d304e0642ffee3e7fc3a71b2eadb36f3a0805d4927af7a5196` | `2410A78` |
| `172F790..172F7FE` map helper | 110 / 34 | `57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375` | `2567A18` |

這五個完整 body 的指令全可由各自入口走到；四個 insertion body 合計 187 條。覆蓋界限為上述四函式及其直接 map helper，不代表所有 caller、別名或其他插入路徑已枚舉。

## ABI、外部參照與共享陣列

| 入口 | 入口輸入、roster 來源 | 外部相對項 |
| --- | --- | --- |
| `60CA80` | `RDX=entity`、`R8=flag byte pointer`；從 global `[3326468]` 取 `S` | `CA8A` RIP→`3326468`；`CAC9` call→`60C410` mover；`CB9A` tail-jmp→`172F790` |
| `60CBA0` | `RDX=entity`；同 global | `CBA6` RIP→`3326468`；`CC5A` call→`172F790` |
| `540850` | `RCX=entity`，`540860` 複製到 `RDX`；同 global | `540856` RIP→`3326468`；`54090D` call→`172F790` |
| `540920` | `RCX=entity`、`RDX=flag byte pointer`；同 global | `54092A` RIP→`3326468`；`540968` call→`60C410` mover；`540A39` tail-jmp→`172F790` |

每個 insertion body 都有 pointer slot 1、`70h` primary store 7、`38h` aux store 6，沒有直接 property store。精確 56 個位址及每個 memory operand 的 base/index/scale/displacement 均在 evidence 的 `array_sites`；其中 aux 的 byte store 在 disp32 後還帶立即數 `01`，故重寫器不能假設位移是指令最後四 bytes。`S` 還承載 counts 與 map，不能整體偏移。若用現有 sidecar `B`：pointer `B+0`、primary `B+40h`、aux `B+3C0h`、property `B+580h`，可在各 store 前暫設 `R11=B−E8h`，僅將該 memory operand 的 `RBX` 改成 `R11` 並調整原位移：pointer `+0`、primary `+20h`、aux `+1E0h`。原四 body 沒有使用 `R11`，但 `RBX` 在同一 body 的 count/map 指令必須保持原 `S`。RBX 有時是 SIB base、有時是 index，重編碼要分別處理 REX.B/REX.X；不能只替換文字或位移。`60C410` 的獨立候選也須使用相同 `S/B` 綁定，且 flag 路徑的 call 需指向已整合的 mover；單靠原入口可能仍搬四槽。

## 原 guard、初始化與 count 順序

四個函式都先取 `S+80h` tracked count、加 1、與 4 比較；超限走明確的零位址寫入，分別在 `CAA1`、`CBC0`、`540873`、`540941`。在 `FFFFFFFFh` 時加一回繞成 0，所以單把比較立即數 4 改 8 不足以成為八槽 guard。可用的 pre-mutation 讀 count 指令為 `CA94` (`8b8380000000`)、`CBB0` (`448b8380000000`)、`540863` (`448b8380000000`)、`540934` (`8b8380000000`)；這些點都在原 assertion 與共享資料變更之前。若在已執行 prologue 後 splice，拒絕入口必須使用各自正確 frame unwind，不能以假 `ret`、正常 map tail-jump 或零位址 assertion 充當完整 reject continuation。

`60CBA0` / `540850` 是 simple 路徑：按七個 store 清 `70h`，按六個 store 初始化 `38h`（相對 `+14h` byte 設為 1），再寫 pointer；接著 **先** call map helper，**後** 增 `S+80h`。兩者不改 `S+84h` dense 或 `S+88h` prefix。首個 inline store 分別在 `CBDC`、`54088F`。

`60CA80` / `540920` 是 flag/dense 路徑：flag 非零時先看 `P=S+88h` 與 `D=S+84h`，若 `P<D` 可先 call `60C410` mover；然後增 prefix，在 `CAE9..CB19` / `540988..5409B8` 清 `70h`。flag 為零則選 dense ordinal，跳過這組 `70h` 清零。共同路徑初始化 `38h`（包含相對 `+14h` byte = 1），再增 dense `+84h`、增 tracked `+80h`、更新 high-water `+7Ch`、寫 pointer，最後 tail-jump map helper。首個 inline 狀態寫入為 `CADC` / `54097B`；若 mover 分支成立，mover 更早就可能改動資料。這個分支與 simple 路徑的 map/count 順序不同，不能合併成同一個初始化模板。

候選的八槽入口 guard 至少要核對 `S` 綁定與 tracked `<8`；flag/dense 路徑還需 `P<=D<=T`。在現有 caller/pending record 契約未證明前，`D<T` 可能覆寫 pending record，候選可保守拒絕並要求 `D==T`。這是新增的安全限制，並非來源已證的 caller 不變式。entity / flag pointers、各 sidecar 區、map 狀態及存活期仍須由整合層保證；「layout 放得下八格」本身不證明槽內容已原生初始化。

## Map helper 與失敗語義

完整 `172F790` helper 入口是 `RCX=&S+D0h` map header、`EDX=entity ID`、`R8D=ordinal`；`[RCX+0]` 是 bucket pointer、`+8` capacity、`+C` empty key marker、`+10` hash multiplier。它以 `hash+probe` 和 `capacity−1` mask 搜尋空 key 或相同 key，選中時 `172F7F2` 先寫 bucket `+4` ordinal，再於 `172F7FA` 寫 key，`RAX` 回傳 bucket pointer。capacity 0 或探遍未命中時 `172F7E3` 把 `RCX` 設 0，接著照樣寫 `[RCX+4]`。它不配置或擴容，也不預檢重複 entity；四個 caller 的 count 仍按原路徑增長。若要在首次 mutation 前拒絕所有無效狀態，必須另有穩定有效的 map/payload 前提或前置驗證；僅檢 `T<8` 無法保證 helper 成功。對 simple 路徑，map call 在 tracked increment 前，但已完成 record stores；對 flag 路徑，map tail-jump 在 counts、record 與 pointer stores 後。

## 可重跑與限制

在 workspace 執行同一腳本，以 `--evidence` 指向上述固定 capture 目錄，分別指定尚不存在的 `--output roster_insert_native_evidence.json` 與 `--output roster_insert_native_recheck.json`；兩份輸出位元組相同。此證據提供 emitter 的 source pin、rewrite 位點與 CFG/relocation 表，沒有證明 live hook、整體 unwind、allocator/binding 生命週期、map 完整性、所有 caller、多人同步或八人任務流程可用。
