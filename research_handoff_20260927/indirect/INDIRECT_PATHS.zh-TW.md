# 同版既有捕捉：間接生成與 options+0x1B 補充研究

日期：2026-09-27。此目錄是本機離線研究；未修改原 repo、preview.8、preview.9 或追蹤模組，未捕捉遊戲、未產生 Mod ZIP。

結論仍是 **UNBOUND**。新增一條保存原生生成 wrapper 指標的靜態證據，以及一條 `options+0x1B` 的具體消費鏈；兩者均沒有成為「本機武器在發射前可持久設定、四範圍共用」欄位。沒有擴張四範圍玩法、所有權、可還原性或性能結論。

## 來源、方法及可重播產物

- Steam build `25480438`，game DLL SHA-256 `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。
- 原始 framed capture 身份：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- 既有 `captured-data.bin` SHA-256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`；既有 `capture-report.json`：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。腳本先核對這兩個完整指紋，不能只換 build ID。
- Capstone `5.0.7`。`inspect_capture.py` 在捕捉 code RVA `[0x1000, 0x2110A93)` 中找 `E8/E9 rel32` 及帶／不帶 REX 的 RIP-relative `MOV/LEA` 候選，再從 captured unwind fragment 起點反組譯核對指令邊界。另對全部已捕捉範圍尋找完整絕對 VA 與四位元組 RVA 字面值。
- 捕捉標記的 unwind table 為 RVA `0x37D8000`、1,832,304 bytes、152,692 筆有序且位於 captured code 內的 fragment。保存的 PE header exception directory 卻是 RVA `0x3FD340C`、1,832,316 bytes，該區未捕捉；腳本明示採用前者，沒有拿未捕捉 header directory 當資料或補零。父函式入口按 `UNW_FLAG_CHAININFO` 逐層追到 root。
- `constructor-xrefs.json`、`caller-root-xrefs.json`、`caller-parent-roots.json`、`caller-parent-xrefs.json` 保存 1–3 層 xref；`settings-manager-refs.json` 提供 root 的私有設定研究使用的 88 個 `0x33266D8` MOV references 及 fragment/root。
- `indirect-findings.json` 保存 16 個新增關鍵指令的 bytes/SHA-256、wrapper pointer、來源指紋及明確未證狀態。此目錄反組譯 JSON 與原 capture 一樣只留本機。

## Constructor 的地址取得及兩層 caller 查核

對 `0x13A9830`，識別並邊界核對的直接生成呼叫仍為 13 個；沒有新增 `JMP rel32`，本次可辨識 RIP-relative `MOV/LEA` 地址取得為 0，所有已捕捉範圍中其完整絕對 VA occurrence 為 0。

三個 constructor RVA 字面值不應當成間接函式指標：`0x389F890` 是 captured unwind table 入口；`0x25112B4` 與 `0x2511368` 分別是 unwind records `0x25112A4`、`0x2511364` 的 CHAININFO，存放相同的 `{Begin=0x13A9830, End=0x13A986D, Unwind=0x251128C}`。已用 header flags、unwind-code 數量及 12-byte chained record 逐項核對。

13 個呼叫對應 11 個 root：`0x5F5670`、`0x615940`、`0x646030`、`0x6810D0`、`0x6CB140`、`0x852170`、`0x8A4410`、`0xB86F10`、`0x12A98D0`、`0x13A8F50`、`0x13C0D10`。這 11 個 root 在相同掃描方法內均未見 RIP 地址取得或 captured absolute VA；再往其 callers 上推 15 個 root 後找到下面的實際 pointer occurrence。

這是**有界枚舉結果**。它不能排除 runtime heap/vtable、未捕捉 writable-data、算術合成／轉換地址、從外部模組注入的函式值、無 unwind 的 leaf code，或其他 instruction encoding。它也不是所有 projectile/entity 執行路徑的完整呼叫圖。

## 新的 wrapper pointer：靜態保存已證，實際派發未知

`readonly RVA 0x214D040` 的 8 bytes 是 `50 99 5E 15 F8 7F 00 00`，正好等於此捕捉 base `0x7FF814A30000 + 0xBB9950`。它位於一段連續的 captured code pointers 中。此處只把 pointer 的實際存在當證據，尚未把整段表賦予遊戲語義。

若程式派發至 `0xBB9950`，該 wrapper 的已見原生鏈為：

`0xBB9950 → CALL@0xBB99F9 0xB86F10 → CALL@0xB871BE 0x13A9830`。

- `0xBB99F9` bytes `e812d5fcff`，wrapper 從輸入記錄 `RDX` 的多個指標讀取參數，再呼叫已知生成 root。
- `0xB8718E` bytes `4c8d442430`，將 `RSP+0x30` 作為 options。
- `0xB87102` bytes `c744244801000100`，寫 `dword [RSP+0x48]=0x00010001`；因此 `options+0x18` 的低 byte 固定為 `1`，和原有直接生成證據一致。
- 尚未找到 `0x214D040` 或其連續 pointer 區段的可驗證 consumer。`dispatch-pointer-xrefs.json`、`dispatch-table-xrefs.json` 及 `dispatch-range-refs.json` 保存精確點與附近區域掃描的負結果；不能把保存 pointer 當同次 P-11 的 runtime dispatch，亦未證任何武器使用此 wrapper。

此發現增加一個「可被間接呼叫的 wrapper 保存位置」，沒有新 constructor 選項來源，更没有本機獨占可寫欄位。

## 新的 options+0x1B 消費鏈與排除範圍

同一 `0xB86F10` 支線另有一個寬度 1 byte 的 options 欄位來源：

| 位置 | 指令及意義 |
|---|---|
| `0xB871A7` | `f6411401`，`test byte [RCX+0x14],1`；此處 RCX 來自外部記錄表，未證是本機武器私有設定。 |
| `0xB871B0 / 0xB871BA` | 條件選 0/1，`8844244b` 寫 `[RSP+0x4B]`，即 `options+0x1B`。 |
| `0x13A9DF0 / 0x13A9DFC` | `41385d1b` 讀 options byte，`4188843794300000` 寫 motion array 的 `[base + slot*0x70 + 0x3094]`，即 motion record `+0x54`。 |
| `0x13A8794` | `4380bc3c9430000000` 是本次辨識到的 direct-displacement reader；位於 cleanup root `0x13A8700`。 |

cleanup root 在 `0x13A8741` 已先將 auxiliary ID 寫成 `0xFFFFFFFF`。motion `+0x50` 經存在／有效檢查，`+0x54` 非零且 runtime flag `0x4000` 未設時，程式進入特殊清理支線：

1. `0x13A87B5` 呼叫 leaf `0x13B0B90`。該 helper 的 `0x13B0B9D` 對 runtime flags `OR 1`，可依 state `+0x8C` 的正值更新 motion `+0x34`，於 `0x13B0BC2` 返回。
2. `0x13A87BA` 對 flags `OR 0x4000`；`0x13A87C8` 寫 motion `+0x34=0x3E99999A`（0.3f）；`0x13A87D7` 對 flags `AND 0x7FFF`。
3. 呼叫一個 runtime vtable `+0x658` 入口，跳至清理函式尾端。vtable 的 heap target 未捕捉，完整语义保持未知。

已見三個 flags 算術操作合成 `((flags | 1 | 0x4000) & 0x7FFF)`，對所有 65,536 個輸入均**保留 `0x20` 原值**。這條已見資料流不能作清除首次来源 unit 排除的入口，且改變 lifetime-like motion `+0x34`。沒有證據顯示它繞過獨立的來源 entity 相等檢查。

時序界線必須精確：cleanup 也會因 constructor 回收旧槽位而被呼叫，因此不聲稱 cleanup 每一次都「晚於該彈第一次碰撞」。已證的是它消費清理階段的 per-projectile copied byte，沒有接到新彈首次來源排除的控制邊。這裡也沒有提供該 upstream 記錄的本機獨占、四種武器類別、持久寫入或安全還原證明。

`+0x3094` 全 code 字面 displacement 搜尋另找到 `0x138C858` 的無關結構 LEA 以及一個 conditional branch displacement coincidence。沒有依相同偏移合併結構。別名／不同 base 重寫的其他 consumer 仍可能存在；本報告只排除已追到的 cleanup 支線。

## 驗證與下一份必需資料

`verify_indirect.py` 有 7 個離線核對：完整來源指紋拒絕、16 pins 與 pointer/unwind edges、65,536 flags 運算、錯誤指令拒絕、錯 pointer 位置拒絕、錯 mask 拒絕、實際 constructor xref 重掃與非邊界位址拒絕。`run_verification.py` 在一般 Python 和 `python -O` 各跑一次成功測試，再把 options byte instruction pin 人為從 `+0x1B` 改成 `+0x18`，要求測試實際以非零狀態失敗。詳細 stdout/stderr 與 exit code 在 `verification-results.json`；這些是離線證據測試，不是 runtime 所有權／還原實測。

於原 repo 根目錄可執行下列命令，`--output` 必須使用尚不存在的路徑：

```powershell
python E:\File\Codes\0\26.10.1\HD2\research_handoff_20260927\indirect\inspect_capture.py --evidence build/existing-code-evidence-25480438 --target 0x13a9830 --output NEW-constructor-xrefs.json
python E:\File\Codes\0\26.10.1\HD2\research_handoff_20260927\indirect\trace_dispatch.py --evidence build/existing-code-evidence-25480438 --output NEW-dispatch-refs.json
python E:\File\Codes\0\26.10.1\HD2\research_handoff_20260927\indirect\reproduce_xrefs.py --evidence build/existing-code-evidence-25480438 --output NEW-xref-replay
python E:\File\Codes\0\26.10.1\HD2\research_handoff_20260927\indirect\run_verification.py --evidence build/existing-code-evidence-25480438 --output NEW-verification-results.json
```

下一個必要證據仍是：有具體原生 consumer 的本機武器實例欄位；同次設定／模式／元件 dispatch 到首次來源 unit 及 entity 排除的完整控制流；四範圍的共同性與安全生命週期。只有更多 pointer occurrence、同偏移欄位或清理時旗標算術，均不足以過門檻。此調查沒有要求重試 projectile slot 搜尋，也沒有產生未驗證的遊戲內 observer 或候選 Mod。
