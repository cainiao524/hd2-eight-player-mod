# `6054F0` 狀態更新／palette 路徑：完整原指令證據

## 範圍與可重跑來源

`arrival` 是本輪檔名用的工作名稱。完整 `6054F0..605947` **1111 bytes／241 指令**實際以 entry entity ID 查 roster map，更新四組記錄中的若干欄位、讀 network index 選 palette，最後呼叫玩家數通知；它本身沒有 append、map 插入或 `T/D/P` count 遞增。因此不能由名稱推論為完整加入路徑。[獨立前提分析](roster_arrival_native_prerequisites.zh-TW.md)另列 ABI、原動作次序及 emitter 限制。

[有界 replay](roster_arrival_native_replay.py)只讀固定 Steam build `25480438` 的既存 capture，先核 `capture-report.json` SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`、`captured-data.bin` SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`、capture identity `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`，並核[既有 consumer 清單](roster_property_consumers_native_inventory.json) SHA-256 `0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2`。主體只有一個 unwind fragment `2424950`，整段 SHA-256 `6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a`。

[evidence](roster_arrival_native_evidence.json)與獨立輸出的[recheck](roster_arrival_native_recheck.json)逐 byte 相同，兩者 SHA-256 `c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64`；replay SHA-256 `923a68c988f5c6f1fc729dd23539da41a1a650637ea79a462b7d2ba9538e5ebe`。`bodies['0x6054f0']` 保存完整 body bytes、每條原 encoding、CFG、41 個 local branch、23 個 RIP 參照、4 個 direct call、4 個 indirect call、唯一 return `605946` 與全部 19 個陣列 base 位點。`bodies['0xfd9af0']` 是不變 direct callee 的 **test-only** 完整 174 bytes／44 指令，SHA-256 `7fa3870d13305c77997147167ccca1f07b199c5011883b9d8442f31e831393fc`，無 roster 陣列讀取或 call；不需 sidecar clone。兩份 body 的所有 local CFG 邊均落在已解碼指令邊界，entry 可達全部指令。

在 workspace 根目錄重跑時，輸出路徑須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -B five_player_feasibility_20260927/roster_arrival_native_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output NEW-roster-arrival-recheck.json
```

## 入口、map 與保留的 S

入口 RDX 是 entity pointer，R8 是 caller state object；`605521` 從 `[RDX+8]` 取 ID，`605524` 暫存 R8 到 RBP，`605530` 從 global `3326468` 取 `RDI=S`。入口 RCX/R9 在首度覆寫前沒有業務讀取。S 的 `D0/D8/DC/E0` map header/backing 用來查 entity ID，結果 EAX 為 ordinal 或 `FFFFFFFFh`。`60560E` 讀 held `S+84h` 作 dense 遍歷界限；`60587F/60588D` 又從 global S 讀 D 給後段 API，而 `6058ED` 與 `605906` 讀 held RDI 的 D。候選必須保留 map/header/count 的 S 角色，並由外部保證回呼間身分與狀態一致。

原 map miss 並非安全空操作：`605594` 設 EAX=`FFFFFFFFh`，`6055A7` 及 `6056B2` 以 32-bit 寄存器**零延伸**後乘 stride，導致巨大的 unsigned offset；即使 R8 首 byte 為 0，`6056B8` 仍可能寫 aux。empty-key 命中亦可能取得 stale bucket value。完整候選應在 `605599` 前、首次 payload 讀寫前核 member/key、八格 map、`P≤D≤T≤8`、`ordinal<T` 與 sidecar pointer 身分，然後才進原分支；這是候選政策，不是原函式已有的 guard。更早或更晚的動態回呼不能視為自動維持此 snapshot。R8 指向的參數物件，及首 byte 非零時 `[R8+48h]` 所指物件 `+624h`，另需有效記憶體契約。

## 四組陣列：19 個位點

共同 B 布局為 pointer `B+0`／stride8、primary `B+40h`／stride70h、aux `B+3C0h`／stride38h、property `B+580h`／stride20h。下表的 `n` 是 map ordinal；dense loop 的迭代索引另計。原 operand encoding、寬度、base/index/SIB/位移可在 evidence 的 `array_sites` 逐條核對。

| 類別 | 原位點（共同前綴 `605`） | 原用途與 B 目的 |
| --- | --- | --- |
| pointer | `5BB` | 讀 `S+E8h+n×8` → `B+n×8`，再查 entity bit 0 |
| pointer | `626` | LEA 原 `S+E8h` 作 dense loop base → `B`；`605630/658` 沿該指標讀／前進 |
| primary | `665/684/691` | 在 `S+140h+n×70h` 擇一寫狀態 5／8／1 → `B+78h+n×70h` |
| primary | `6A6` | 清 `S+168h+n×70h` 的 QWORD → `B+A0h+n×70h` |
| aux | `6B8` | `+8` DWORD 設 `7FFFh` → `B+3C8h+n×38h` |
| aux | `6C8/6F3` | `+14h` BYTE 寫 1 或 property bit 0 的反向值 → `B+3D4h+n×38h` |
| aux | `6D6/700` | `+20h` DWORD 寫 global `3483C34` → `B+3E0h+n×38h` |
| aux | `709/83C` | `+18h` DWORD 先寫 3、條件成立再覆寫 1 → `B+3D8h+n×38h` |
| aux | `758/801` | `+0` QWORD 存／重讀關聯物件返回值 → `B+3C0h+n×38h` |
| property | `5CD` | `S+3ACh+n×20h` DWORD 條件 OR `800h` → `B+584h+n×20h` |
| property | `61F` | LEA 原 `S+3ACh` 作 dense loop base → `B+584h`；`60563E/65C` 沿該指標讀／前進 |
| property | `6E6` | 讀 property `+4` 低 byte → `B+584h+n×20h` |
| property | `760` | 讀 property `+Ch` 完整 network index DWORD → `B+58Ch+n×20h` |

表列 **pointer 2、primary 4、aux 9、property 4，共 19**。兩個 LEA 衍生 base 也必須改，不能只換有 memory operand 的直接讀寫；RDI 應保留指向 S 供 header/map/count 使用。原 `6056F0 AND CL,1` 的 ZF 穿過數條 MOV／aux 改接點直到 `605707 JNE`；`60579D CMP mode,1` 的 ZF 穿過浮點與 stack 指令直到 `6057CA JNE`。任何 trampoline 或指令插入都須保旗標。原 ordinal EAX 也跨可選 primary 支線存活至 `6056B2`，不能當 scratch。

## Palette、呼叫與 count 順序

`605760` 的 network index 是原完整 DWORD；`605767/76A` unsigned `<4` 才讀 `213F4E0+index×10h` 的四列 16-byte palette。index `4–7`（以及其他 unsigned `≥4`）不讀表，三個分量各用原 `1.0f`，之後共同乘 `255.0f`；結果為 `(255,255,255)`。這裡沒有第五人拒絕，也不能直接把比較常數改成 8，否則會讀原四列表以外。[四段 RO literal](roster_arrival_native_evidence.json) 固定 palette `213F4E0` 64B SHA `100fab4b4513b242012b69af448eab3a532fcbb49865c74bdaed4b4ee9b287a8`、`23C6D70` 的 1.0f SHA `e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c`、`23C79AC` 的 255.0f SHA `270696d298cc689d8e5bd75897918aa617a25a5030ccae98017053dddd974995`、`22473C8` 的 `player_count\0` SHA `2d1f7bb5ed667b71641e114124b84958b97b41db1140c1f721dba595fff5edc4`。

原 body 的 direct calls 為 `605718→FD9AF0`、`6058D3→94C9C0`、`6058F3→60C2A0`、`60591F→2088770`；indirect calls 為 `605741`、`60574A`、`6057E6`、`605910`。`FD9AF0` 的完整固定 body 是可用的 unchanged test leaf，屬另一個 context forward map，仍需其 backing/key 有效；`94C9C0` 與 `60C2A0` 的玩家數契約已有[固定 count 分析](roster_player_count_native_prerequisites.zh-TW.md)和[callee 證據](roster_departure_callee_evidence.json)。其他介面、resource、cookie helper `2088770` 在本輪只記錄呼叫 ABI 邊界，不展 callee tree。

當 mode==4 且後段 registry tag==`3Eh` 時，`6058D3` 可多次呼 `94C9C0`，其 stack+28 count 來自**重新載入的 global S**。之後 `6058F3` 將 held S 的 D 給 `60C2A0`；`605910` 以 literal `player_count` 與 held S 的 D 呼 indirect 通知，再執行 cookie check 與 epilogue。這條路沒有 `D±1` 政策，也未寫 S counts；可沿用既有 v0.11 player-count patch plan，但不能把三次 count 讀取當原子 snapshot。palette 與玩家數通知的實際資源、回呼副作用、重入及同步仍待整合者提供。

## 研究停止界限

完整 source body、四組陣列位點、全部 control-flow／重定位、固定 RO bytes 與 test-only `FD9AF0` 已足以實作此局部 clone 並做有界原／候選機器碼比對。沒有新增必須改接 roster 的直接 callee；既有 `94C9C0`／`60C2A0` 依賴沿前述固定證據處理。此處不證明所有 caller 真正進入這條路，也不補 B 配置／初始化／發布／清理、Windows hook/unwind/reject continuation、外部 context 或五至八帳號同場任務驗收。
