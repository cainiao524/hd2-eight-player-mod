# 共用 entity → ordinal map：八格滿載與刪除的離線語義驗證

## 結論

**對固定 capture 的 `172F790` 插入與 `172F8A0` 刪除演算法，八個 buckets 足以保存八個不同、有效的 entity key。這次模型驗證沒有找到「八名成員必須改成十六個 buckets」的要求。** 滿載時查找、更新既有 key 的 ordinal、刪除後的 backshift，以及重新插入，都通過下述有限範圍的驗證。

但必須維持 **不超過八個不同有效 key**。滿表再插入第九個不同 key，`172F7E3` 將 `ECX` 清零，隨後 `172F7F2` 先向 **位址 `0x4` 寫四個 bytes**；它沒有安全的「容量已滿」返回。本地 Python 指令直譯器在這個位置回報模擬記憶體錯誤；未執行原生遊戲碼，也沒有觀察遊戲崩潰。

此結論只關於 map 演算法與指定測試狀態。八槽所需的 payload 陣列搬移、owner alias、生命週期，以及實際連線人數，仍需各自的證據。

## 1. 正式產物與來源

正式重播及證據：

- `component_map_capacity_replay.py`
- **`component_map_capacity_evidence_v4.json`**：本報告採用的正式證據，包含旗標來源、指令覆蓋檢查，以及兩個不同 sentinel 來源的指令與模型前提。
- 未帶版本後綴的 evidence、`v2` 與 `v3` 是本次過程產物，保留原名與原內容。前两版未包含最後加入的全部靜態旗標檢查；`v3` 尚未加入完整的 sentinel metadata。

SHA-256：

| 檔案 | SHA-256 |
|---|---|
| replay | `6f6eba90fde65944a2f9c1a05de35febc23814c501066235b05c7d86c6a955f3` |
| evidence v4 | `f8918247d729a1bde957739ffa7d724ffceba831416e8d526aacc5f70e53e61b` |
| capture-report.json | `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5` |
| captured-data.bin | `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d` |

capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

固定輸入目錄：

```text
C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438
```

腳本只讀上述保存檔案、既有 `inspect_capture.py` 及本身，輸出新的 JSON；使用已安裝 Capstone 解碼，沒有安裝套件。

### 完整函式邊界

| 用途 | 固定範圍，尾端不含 | bytes／指令 | 完整 bytes SHA-256 |
|---|---|---:|---|
| 插入／更新 | `[172F790,172F7FE)` | 110／34 | `57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375` |
| 刪除／backshift | `[172F8A0,172F9A3)` | 259／78 | `d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f` |
| 代表性 lookup consumer | `[60C890,60C9BF)`，4 個 unwind fragments | 303／72 | `23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411` |

邊界來自固定 capture 的 unwind 表。所有 fragments 完整解碼、逐指令 bytes／SHA、一般 CFG 都寫入 evidence；分支必須落在同 root 的已驗證指令邊界。`60C890` 完整 body 被 pin，但指令直譯只執行查找部分，到 `60C928` 前停止，**沒有以模擬結果寫入 roster record**。

## 2. 實際資料格式與算術

兩個共用 helper 的 `RCX` 指向 map header：

| header offset | 型態 | 用途 |
|---|---|---|
| `+0` | pointer | bucket 陣列 |
| `+8` | uint32 | capacity |
| `+C` | uint32 | empty／invalid key |
| `+10` | uint32 | hash multiplier |

每個 bucket 是 8 bytes：`uint32 key` 與 `uint32 value`。在元件的 entity map 中，value 用作 dense record ordinal；**它不是 network index，也不是 bucket ordinal**。

component41 constructor 已重新 pin：

- `55270A` 取 owner `+4158`，即 `S+10`，作為內嵌 bucket 起點。
- `55271E` 保存至 owner `+4198`，即 `S+50` header pointer。
- `552728` 寫 capacity `8`；`552738` 寫 multiplier `2`。
- `552732` 保存從 global 取得的 invalid key，未假定其執行期值。

令 `u32(x) = x & FFFFFFFF`：

```text
hash = u32(key * multiplier)
mask = u32(capacity - 1)
probe_bucket = u32(hash + probe_number) & mask
```

`IMUL`、`LEA EDX` 等運算都按 32-bit 截斷；寫入 32-bit 暫存器後，64-bit 暫存器高半部清零。模型沒有用無限精度整數的乘法結果直接算 bucket。

這是 `AND(capacity-1)` 的探測，不是任意容量的 `% capacity`。使用者若改容量，仍需 **非零、2 的整數次冪容量** 的前提。本次另示範 capacity=6、multiplier=2：插入第五個不同 key 已失敗，實體陣列仍有兩個空格；不可把容量隨意改成 6 或其他不是 2 的整數次冪的數。

## 3. 插入與查找：全表仍然可用，但沒有第九筆保護

### 插入 `172F790`

`172F7D3` 先判斷 bucket key 是否等於 invalid，`172F7D7` 再判斷是否等於欲插入的 key；任一命中都接受該 bucket。最多檢查 `capacity` 個 bucket。

- 空 bucket：增加一個有效 key。
- 既有 key：覆寫同一 bucket 的 32-bit value，不增加 occupancy。
- 第八筆：只要當前有七個有效 key，線性探測可以找到唯一空 bucket。
- 滿表更新既有 key：仍能在八次以內命中。
- 滿表新增不同 key：探測八次後走空指標寫入；沒有 rehash、擴容或負載因子檢查。

失敗路徑的精確次序：

```text
172F7E3 xor ecx,ecx
172F7EA mov rax,rcx
172F7F2 mov dword ptr [rcx+4],esi  ; 首次無效 store = 0x4
172F7FA mov dword ptr [rcx],r9d   ; 正常零頁不可寫時尚未到此
```

### 查找 `60C890`

這個已保存 consumer 的查找迴圈同樣最多探測 capacity 次；有效 key 的一般查找在 empty bucket 提前結束，或命中後返回 value。滿表沒有 empty bucket，找不到的 key 仍會在八次探測後結束，不會無限迴圈。

**Sentinel 邊界：** `60C897` 的 entry invalid-ID global 為 `3483C20`；component41 constructor `552711` 讀取的 map-invalid global 為 `3483C34`。兩者地址不同，固定 capture 沒有證明它們當時的值相等。本次模型為代表性 lookup 將兩者設成相同測試值（分別測 `0`、`FFFFFFFF`），這是明列的模型前提。八個有效 key 的容量結論需排除所有相關 invalid/sentinel 值；不因本模型而認定上述 globals 的執行期內容。

直接把 map invalid key 傳給插入 helper，會寫入 value，但 key 仍等於 empty 標記，不會形成可區分的有效 entity。模型也演示了這一點。不可把「invalid sentinel 也佔一個真實成員」計入八槽。

## 4. 刪除：capacity−1 上限足以處理滿表

`172F8A0` 先最多探測 capacity 個 buckets 尋找 key。**這一段沒有在遇到 empty key 時提前結束。** 若找到：

1. `172F8FC` 只將被刪 bucket 的 key 寫成 invalid；舊 value 仍留在原位。
2. 保存被刪 value，最後作為 `EAX` 返回。
3. 從被刪 bucket 的後方往前掃，最多 `capacity−1` 次；遇到 empty key 可提前停止。
4. 對每個仍有效的 bucket 計算它是否需要搬入目前的洞。

精確條件：

```text
j    = u32(original_hashed_position + scan_number) & mask
home = u32(current_key * multiplier) & mask
dh   = u32(u32(capacity - hole) + j) & mask
dk   = u32(u32(capacity - home) + j) & mask
若 dh <= dk，將 bucket[j] 的整個 qword 搬到 bucket[hole]；
然後 hole = j，僅把原 bucket[j].key 設為 invalid。
```

`172F965 CMP`、`172F967 JA` 使用無號比較。`172F969`／`172F972` 搬的是完整 qword，所以 **key 與 ordinal 一起搬**。洞的位置會改變，但 `r14d` 保留原始被刪位置，掃描仍按原位置依序前進。

全表一開始沒有空格；刪除先造出一個洞，後续最多掃過其餘七格。驗證顯示不需要為了讓此 backshift 結束而額外保留第九格。

回傳值有一個容易混淆的地方：**刪除 key 的 value=0 時返回 0，找不到 key 時也返回 0**。這不是可直接判斷成功與否的 bool。合法 ordinal 0 必須保留。

## 5. 驗證層次與結果

### A. 高階模型與實際指令直譯的對照

Python 限定指令直譯器直接讀已 pin 的 Capstone 指令，使用人工建立的 header、buckets、stack 與 sentinel global。它不是原生執行或 JIT，也不存取遊戲程序。

測試 **60 組配置**：

- capacity：`1、2、4、8、16`。
- multiplier：`0、1、2、3、80000000、FFFFFFFF`。
- invalid sentinel：`0、FFFFFFFF`。
- keys 包含 `7FFFFFFF、80000000、FFFFFFFE、FFFFFFFF` 等高位元與乘法溢位案例；排除當組 invalid key 作為有效成員。
- 另有 capacity=0 的失敗／查找／刪除案例、直接插入 invalid key 的示範。
- 固定亂數 seed：`0x172F790172F8A0`，混合插入、更新、刪除、查找。

結果：

| 項目 | 次數 |
|---|---:|
| 插入／更新對照 | 1,983 |
| 刪除對照 | 1,259 |
| 查找對照 | 1,264 |
| 總操作對照 | 4,506 |
| 指令直譯步數 | 394,110 |
| 預期模擬錯誤，包含滿表／零容量 | 370 |

每次比較完整 bucket 陣列（包括 empty bucket 殘留 value）、回傳值或首個無效 store 的位址與 RVA。插入／刪除兩個 helper 的 **112 條指令全部被執行過；11 個 conditional 的 taken／not-taken 都覆蓋**。這是有限測試覆蓋，不是所有機器狀態的證明。

### B. 旗標來源核對

直譯器省略部分 `ADD/SUB/INC/IMUL` 的旗標計算，故另從完整 CFG 對每個 conditional 反查它所消耗的 `CF/ZF` 最近來源。判斷 instruction 是否改寫／清除／設定／使旗標未定義，使用 Capstone flag-effect metadata；不只檢查組語相鄰指令。

結果為 **19 個 flag consumption 檢查全部通過**（涵蓋兩個 helper 及代表性 lookup）：每個 consumed flag 的所有最近 writer 都是本直譯器已正確處理的 `CMP` 或 `TEST`。沒有 conditional 讀取被省略的算術旗標。完整 producer RVA 已保存於 `conditional_flag_producers`。

### C. 八格、multiplier=2 的 home 分布窮舉

此設定下，`home = 2 * (key mod 4)`，home 可為 `0、2、4、6`。窮舉 `4^8 = 65,536` 種依插入次序排列的 home 類別序列；第 i 個 key 使用 `4*i+class`，確保不同 key 不因碰撞而被當成更新。

這窮舉的是演算法相關的 home 類別與插入次序，不是列舉所有 32-bit 整數組合。高位元及溢位另由 A 的案例核對。

| 檢查 | 通過數 |
|---|---:|
| 八筆 home 類別序列 | 65,536 |
| 各序列 1 至 8 筆的前綴狀態 | 524,288 |
| 從滿表逐項刪除一個 key | 524,288 |
| 刪後重新插入該 key | 524,288 |
| 滿表更新既有 key 的 32-bit value | 524,288 |
| 第九個不同 key 產生預期 `0x4` store 錯誤 | 65,536 |

每次確認所有剩餘 key 可查到正確 value、有效 key 不重複、occupancy 正確，以及缺席 key 查不到。重插與更新使用高位元 value 驗證 32-bit 搬移；**這不表示這些測試 value 是有效的元件陣列 ordinal**。

所有滿表 bucket 結果的固定 digest：`1a8474c2fd78dbacb64c1d781842b49de61defb7176369f68e84ca20ae953c3b`。

### D. 連續刪除的排列

對兩個固定 full-table 配置，各枚舉全部 `8! = 40,320` 種刪除順序：

1. 所有 key 的 home 都是 bucket 6，探測跨過 7 → 0 邊界。
2. 不同 home 與環繞碰撞混合。

合共 **80,640 種完整刪除順序、645,120 次刪除**。每刪一筆都驗證剩餘 key/value，最後八格皆為 empty。詳細的跨邊界搬移 trace 已保存於 evidence 的 `examples`。

## 6. 對八槽實作的具體影響

1. **目前不需因滿載／backshift 的疑慮而強制把八格 map 改成十六格。** 這裡沒有「只能用一半 buckets」的條件，也沒有在 occupancy=8 時無法完成刪除的模型反例。
2. 保留八格必須保證該 map 的同時有效 key 數最多八個。真人玩家數、元件實例數、生成／移除過渡期的 key 數是否一致，是外層生命週期問題；本驗證沒有證明所有 caller 都維持該上限。
3. 第九筆需要在進入 `172F790` 前被阻止或由實作提供實際額外容量。只靠既有 helper 自己拒絕會走無效 store。
4. ordinal 是任意 32-bit 搬移資料；對八槽陣列而言仍需在外層維持有效 ordinal 範圍 `0..7`。header capacity=8 不會替 payload 陣列檢查 ordinal。
5. 若為實際的額外 entity 或過渡期需求選擇十六格，必須同步處理 bucket backing storage、header pointer 和相關內嵌布局；不能只改 capacity 常量。這次沒有把額外餘裕當成必要證據。

## 7. 重播

從工作區根目錄執行，輸出路徑必須尚不存在：

```powershell
& C:/Users/OvO/AppData/Local/Programs/Python/Python314/python.exe `
  five_player_feasibility_20260927/component_map_capacity_replay.py `
  --evidence 'C:/Users/OvO/Documents/Codex/2026-09-26/referenced-chatgpt-conversation-this-is-an/outputs/healing-pistol-enhanced/build/existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/component_map_capacity_recheck.json
```

本報告沒有讀取或查詢活程序、沒有新擷取、沒有 patch／安裝 mod、沒有連線試驗，也沒有修改總報告。
