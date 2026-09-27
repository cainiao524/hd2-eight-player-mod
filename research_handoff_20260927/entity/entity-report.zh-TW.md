# Entity 派發及首次來源排除：既有捕捉延伸證據

日期：2026-09-27。研究對象為 Steam build 25480438 的既有捕捉；未開啟遊戲程序、未新增捕捉、未修改來源倉庫或任何 Mod。結論仍是 `field_binding=null / UNBOUND`；沒有找到可交付為四範圍共同方案的本機武器持久欄位。

本次新增兩段可重放的靜態證據：component 196 的兩階段 callback 註冊與派發，以及碰撞結果旗標 `0x800000` 的查詢佇列來源。它們縮小了未知範圍；沒有證明 P-11 在一次射擊中實際執行這些 callback。

## 固定來源與重放

已先讀原專案 AGENTS.md、docs/AGENT_GUIDE.md、docs/GENERATION_RESEARCH.md、research/GENERATION_MOD_SPEC.zh-TW.md，以及既有 capture、spawn、collision 分析與 schema 3 研究結果。

| 項目 | 指紋／身份 |
|---|---|
| 遊戲 build | 25480438 |
| game.dll SHA-256 | `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e` |
| 原始 framed capture SHA-256 | `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8` |
| extracted captured-data.bin SHA-256 | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |
| 本次 entity-evidence.json SHA-256 | `7c95007ca9ca024e46d4c886f50e14de46d64a1e17912cb43c88a616e67b1e44` |

`replay_entity.py` 先以原工具 `load_code_evidence` 驗四份固定來源、chunk 指紋及既有證據，再核對本次 81 條精確指令。大部分指令從捕捉 unwind fragment 起點線性解碼驗證邊界；無 unwind 的兩處 leaf 分別以 `0x556D90`（緊接 INT3 padding 的 callback 表初始化入口）和 `0x537C70` 為起點。逐條 RVA、bytes、SHA-256、指令及 decode start 保存在 JSON；這些是本機私人研究輸出。

```powershell
python replay_entity.py --output entity-evidence.json
python -m unittest -v test_replay_entity
python -O -m unittest -v test_replay_entity
```

兩種 Python 模式均通過 6 個測試，內含 3 個來源錯誤、9 個指令破壞、錯誤 component index、錯誤 hit-result offset 及改變捕捉缺口的故障案例。此外把 verifier 的 `require` 故意替換成 no-op 後，來源拒絕測試在普通和 `python -O` 模式均產生 3 個 failures、exit 1；確認測試能抓到驗證失效。此處只驗離線證據工具；因沒有候選欄位，並未宣稱通過 Mod 所有權、生命週期、還原或玩法驗收。

## 1. 舊 RVA 校正與來源 entity 的精確鏈

較早交接的 `0x13AC5FF` 不應繼續稱為來源 entity gate。同一份已驗捕捉在該位置是 bytes `f30f114018`，即 `movss [rax+0x18],xmm0`，位於距離計算分支。schema 3 使用的 `0x13AC68F` 才是實際相等比較。

普通武器的 `0x616565` 讀 weapon object `+8` 的 32-bit 值，`0x616570` 存入生成描述 `+0x18`。constructor 在 `0x13AA4EA` 讀該 32-bit descriptor 欄位，`0x13AA4EE` 存入 `projectileSystem + 0x3B04C + slot*0x24`。該值與來源 unit 欄位（鄰接 `+0x3B048`）分開。

首次處理 query hit 時，普通分支先把 hit record `+0x1C` 的 unit 值交給 `0xFD9980`；該函式查 system 的 unit→entity 映射。`0x13AC68F`（`433b9c874cb00300`）把得到的 entity 與保存的 descriptor entity 比較；相等時 `0x13AC697`（`0f84c1070000`）跳到 `0x13ACE5E`。該目標在 `0x13ACE69/76` 推進 hit index 並回到下一個 hit，構成忽略此 hit 的具體證據。後方 `0x13AC6A1` 才測 runtime `0x20` 並進入來源 unit 檢查。

已見普通生成描述的 entity 來自武器物件身份，未見武器設定旗標選擇是否執行 `0x13AC68F`。修改該身份不符合本任務。

## 2. 新追查：hit-result `0x800000` 是另一種碰撞結果分支

在 entity 比較之前，`0x13AC65A` 的 bytes 是 `42f78425e006000000008000`，即 `test dword [rbp+r12+0x6E0],0x800000`。本函式 hit buffer 起點為 `[rbp+0x6C0]`，每筆長 `0x2C`，故此欄位是 **hit result +0x20，32-bit**。它不是武器設定，也不是 16-bit projectile runtime flags。

該 bit 非零時，`0x13AC66E` 跳到 `0x13AC718`，避開此段普通 entity 與 unit 相等比較；隨後進入另一組 API 呼叫和類型判斷，部分情況仍跳到忽略 hit 的目標。因此「bit 非零」本身不等於接受自己的碰撞。

更早的普通 query 在 `0x13ABD6D..7F` 已依 runtime `0x20` 選擇來源 unit 或 0，`0x13ABE02` 把該值寫入呼叫參數（既有解析的查詢排除參數）。這裡追到的是 query 後回傳結果；沒有證據證明結果的 `0x800000` 能撤銷較早的來源排除。此輪尚未取得 API 實作，亦未重新證明該 API 的所有語義。

hit buffer 有兩個來源：

| buffer 來源 | 原生資料流 | 已知邊界 |
|---|---|---|
| 第一 query | `0x13ABE24 → 0x175CA60` 排入 0x40-byte request；handle 存在 projectile pending entry `+0xE7048`。消費端 `0x13AC4BD` 讀 `system+0x793A608+(handle-1)*0x40` 的結果指標，`0x13AC4D3` 複製 `min(count,32)*0x2C` bytes。 | 排入時結果 buffer 會配置／清零；query worker 之後填內容，不能把初始 zero 當碰撞時的 flag。 |
| 第二 query | `0x13AC197 → 0x175BB40` 排入 0x80-byte request；handle 由 pending entry `+0xE704C` 取得。消費端從 `system+0x799AB58+(handle-1)*0x80` 讀指標和 `+0x76` 的 16-bit count；`0x13AC542/55D` 複製 `min(count,32)*0x2C` bytes。 | 部分路徑先改 result 的位置三浮點；已見這個 copy 前處理未改 result+0x20。 |

第一 query 的 worker `0x175C5C0` 取得結果指標，並在 `0x175C63C` 呼叫 `[[game.dll+0x3326328]+0x68]`。其 request mode 在 `0x175CBAC` 被設為 0，故所見普通排入函式選擇該 worker 分支。另一 request mode 可在 `0x175C659` 呼叫 `[[game.dll+0x3326338]+0x128]`，但不能當作本次普通 query 的實際派發。

第二 query 的 worker `0x175B800` 在 `0x175B8E9/EC` 把結果 buffer 放到呼叫參數，在 `0x175B902` 呼叫 `[[game.dll+0x3326328]+0x80]`，再以回傳數量及容量求 `min`，在 `0x175B920` 存入 count `+0x76`。

API pointer 的來源也有靜態證據：`0x4EDBCF` 載入 provider ID `0x4C26B82B`，EDX 為 0；`0x4EDBD4` 透過 provider 的 `+8` 回呼取得 API table，`0x4EDBD6` 存到 `0x3326328`。`0x3326338` 由相同 provider 介面、ID `0xF3957699` 取得（`0x4EDC0B/10/12`）。沒有足夠來源可以替這些 hash 或 API slots 命名。

**精確缺口：** 既有 capture 只有 headers、code、readonly、unwind 及三個小 readonly 段；`0x3326328/0x3326338` 的 8-byte pointer slots 不在任何 captured DATA chunk。provider table、兩個 API table 的 pointer 值、上述 slot 的實際 target 所在 module/bytes、query 結果 heap 都未捕捉。因此可以定位出填入結果的 API 邊界，仍不能追到 `hit result+0x20` 中 `0x800000` 的實際 producer，更不能證明本機武器欄位能持久設定它。

這排除了把 `0x800000` 直接當成已找到的武器 self-hit switch。沒有排除所有尚未取得實作的查詢語義。

## 3. Component 196 有兩個獨立派發階段

`0x6164D4 → 0xFDC140` 接收 effective entity resource GUID；`0xFDC1C3` 把該 64-bit 值存入新 entity record `+0`。`0xFDC25A` 呼叫 `0x581320`；其 `0x581377` 讀 entity record `+0`，以 GUID 低 12 bits 和最多 4096 筆線性探查尋找 0x20-byte metadata，取得 16-bit component index 陣列與 count。

本次核對了下列 **靜態 callback 註冊與 slot 選擇**：

| 階段 | 註冊指令 | 派發指令 | component 196 對應 |
|---|---|---|---|
| 第一次 | `0x55AE6C` 載入 `0x537AD0`；`0x55AE73` 存到 system `+0xF0C730` | `0x58140E` 讀 system `+0xF0C110+component*8`，`0x581421` 間接呼叫 | `0xF0C110+196*8=0xF0C730`，因此此階段選中 196 時會調用 `0x537AD0`。 |
| 第二次 | `0x55AE96` 載入 `0x537C70`；`0x55AE9D` 存到 system `+0xF0DB70` | `0xFDC2B1 → 0x581780`；`0x581A3B` 讀 system `+0xF0D550+component*8`，`0x581A4E` 間接呼叫 | `0xF0D550+196*8=0xF0DB70`，因此此階段選中 196 時會調用 `0x537C70`。 |

所以 `0x581421` 與 `0x537C70` 不應直接當成同一個 callback 階段。已見 `0x537AD0` 初始化 component manager 的 0xC0-byte state 及 entity→index 映射；第二階段 wrapper `0x537C70 → 0x641050` 才包含後續可達原生 constructor 的支線。

該支線的另一個明確 guard 是 `0x641D7A`：讀 byte `[resource+0xAD]`，零時 `0x641D81` 跳過這段 native spawn。resource pointer 由 `0x641143 → 0x504720` 取得並於 `0x641157` 暫存。這個 guard 只證明分支條件，沒有證明 resource 屬於本機武器私有記錄，也沒有證明改它保留原彈丸行為，因此沒有提出為候選。

可達支線 `0x641DFD → 0x646030 → 0x64625C → 0x13A9830` 仍在 `0x6461B8` 以 `mov word [options+0x18],1` 固定來源排除選項。component entity header `+0x14` 的 bit 0 在 `0x64624C/57/59` 傳到 **options+0x1B**，不是 options+0x18；不能混成同一開關。

**精確缺口：** 沒有同次 P-11 effective GUID、metadata 命中 record、16-bit component list、第二階段有效 callback table、component state/resource identity 和首次碰撞／治療。靜態註冊使 component 196 這段假說可以更準確地描述，但不證明 P-11 GUID 的 metadata 實際包含 196。更沒有四類武器共用這段支線的資料。

## 4. 對候選準入的影響

來源 entity gate、query result layout、API 呼叫邊界及 component callback 階段已增加可核對的 code 證據。以下必需條件仍未通過：本機武器獨占記錄、可持久且可還原的欄位、該欄位在生成／首次碰撞前的原生消費、四範圍一致性及原行為等價。

因此仍不進入遊戲內候選核對或建置；沒有 ZIP、部署、發布或 FPS/幀時間結論。本次沒有重搜投射物槽位，也未修改來源身份、共享定義、物理結果或逐彈資料。
