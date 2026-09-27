# Component 239 剩餘回呼：名冊分段搬移與移除前清理

## 結論

本次追完 `0x540B20/0x540B30/0x540B40/0x540B50/0x540B60` 的實際函式資料流。這五個回呼分別涉及移除前清理、名冊前段移入、名冊前段移出、空回呼及具名 `disconnected=true` 通知；**尚未由它們找到傳入 `index` 屬性的反序列化／套用函式**。

新增的八槽擴容必要條件很具體：`0x60CF50` 和 `0x60D300` 在改變 **roster ordinal（名冊位置）** 時，會交換整筆 `0x20` bytes 屬性記錄，包括記錄內 `+0xC` 的 **network index**，並修正 entity ID→ordinal 雜湊表。它們沒有把搬移後的 ordinal 寫成 network index。若重新配置 roster 的四組陣列，這兩條路徑以及透過別名暫存器進行的拷貝都必須同步適配。

本頁全部來自既有固定 game.dll 捕捉；沒有讀取活程序、新擷取、安裝或修改遊戲，也沒有多人連線驗證。沒有修改總報告。

## 1. 來源與入口證明

- `capture-report.json` SHA256：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。
- `captured-data.bin` SHA256：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- capture identity：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- 所有位址為該 game.dll 的 RVA。
- 沿用 `spawn_callback_registration_evidence_v2.json`（SHA256 `142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109`）中已證明的 component 239 指標登錄；本次重核整段 initializer 的 bytes 雜湊及各入口 LEA/store bytes，沒有把重做 initializer 掃描當作新進展。
- 無 unwind 的短 leaf 由上述指標登錄證明入口：`0x540B20/30/40` 各為完整 8 bytes，`0x540B50` 為完整 3 bytes `ret 0`。其餘本次分析的八個函式根據 unwind root 收集全部 fragment，逐段完整解碼並保留 SHA256。

表位移一律相對 **component owner = 原 context+0x40**。使用原 context 的呼叫點在下文明列其多出的 `0x40`，避免混用基底。

## 2. 五個回呼的用途

| owner 相對表基底 | index 239 入口 | 本次確認用途 |
| --- | --- | --- |
| `+0xF0DF70` | `0x540B20 → 0x605950` | 移除前清理與通知，早於另一張表的實際 roster 移除。 |
| `+0xF0F3B0` | `0x540B30 → 0x60CF50` | 將該 entity 移至 `roster+0x88` 所計數的前段末尾，再增加前段數量。 |
| `+0xF107F0` | `0x540B40 → 0x60D300` | 與前段最後一筆交換，減少 `roster+0x88` 的前段數量。 |
| `+0xF0FDD0` | `0x540B50` | 完整函式僅 `ret 0`，空回呼。 |
| `+0xF11210` | `0x540B60` | 條件成立時對 entity 發出具名 `disconnected=true` 通知。 |

### 2.1 移入前段：先設定 entity+0x14 bit 0

`0xFDBB40` 的實際 inline 派發路徑提供順序證據：

1. `0xFDBCE6`：`or dword ptr [rsi+0x14],1`。
2. `0xFDBCEA`：`r15 = 原 context+0x40`。
3. `0xFDBDD3`：以 component index 讀 `[r15+index*8+0xF0F3B0]`；`0xFDBDE7` 把 entity 記錄 RSI 放入 RCX，`0xFDBDEA` 間接呼叫。Index 239 對應 `0x540B30`。
4. 後續流程在 `0xFDBE33/0xFDBE4A` 使用 `+0xF0FDD0` 表；index 239 是空回呼 `0x540B50`。

`0x60CF50` 於 `0x60CF68` 取得 entity ID，`0x60CF71` 從同一全域 `0x3326468` 取 roster 到 RBP；經 `+0xD0/+0xD8/+0xDC/+0xE0` 雜湊表在 `0x60D036` 取出 ordinal EBX。`0x60CFD5` 取前段邊界 `p = roster+0x88`。

- 若 ordinal 已是 p，直接增加邊界，並清零該位置的 `0x70` bytes 狀態。
- 否則交換原 ordinal 與 p 的 entity 指標、`0x38` bytes 記錄、`0x20` bytes 記錄；目的 p 的 `0x70` bytes 狀態清零。
- `0x60D264` 與 `0x60D2D3` 修正兩筆 entity ID→ordinal 映射；`0x60D2D7` 增加 `roster+0x88`。

**`0x70` bytes 狀態在這條方向是初始化目的位置，不是雙向交換。** 對應清零範圍為 `0x60CFF5..0x60D025` 或 `0x60D07D..0x60D0AD`，共七次 16 bytes 寫入。不能把移入與移出抽象成完全相同的 swap helper。

### 2.2 移出前段：通知與交換完成後才清 bit 0

`0xFDBEA0` 提供另一方向的直接 caller：

1. `0xFDBF58` 測試 entity+0x14 bit 0。
2. `0xFDBF76` 形成 `RCX = context+0x40`；`0xFDBF7D` 設 `RDX = entity`；`0xFDBF80 call 0x581E10`。
3. `0x581E10` 先在 `0x581F53/0x581F66` 派發 `+0xF11210` 表，即 `0x540B60`。
4. 再在 `0x581F83/0x581F96` 派發 `+0xF107F0` 表，即 `0x540B40 → 0x60D300`。
5. 返回後 `0xFDBF85` 才執行 `and dword ptr [rsi+0x14],0xFFFFFFFE` 清除 bit 0。

`0x60D300` 同樣以 entity ID 查出 ordinal，取 `q = roster+0x88-1`。若原 ordinal 等於 q，只更新前段數量；否則交換 ordinal 與 q 的四組平行資料，修正兩筆雜湊映射（`0x60D6DB`、`0x60D743`），最後 `0x60D747` 減少 `roster+0x88`。

本頁以可觀察的「bit 0 設定／清除、前段移入／移出」命名。這段證據沒有為 bit 0 建立適用全部 entity 的「本機玩家」或「authority」語義。

## 3. Network index 如何隨 ordinal 搬移

同一 roster 內的平行儲存：

| 起點與每筆步幅 | 移入 `0x60CF50` | 移出 `0x60D300` |
| --- | --- | --- |
| `+0xE8 + ordinal*8` | `0x60D049..0x60D06C` 交換 entity 指標 | `0x60D3A7..0x60D3D1` 交換 entity 指標 |
| `+0x108 + ordinal*0x70` | 清零目的前段位置 | `0x60D3F6..0x60D514` 交換完整 `0x70` bytes（112 bytes） |
| `+0x2C8 + ordinal*0x38` | `0x60D0CD..0x60D158` 交換完整 `0x38` bytes（56 bytes） | `0x60D548..0x60D5D3` 同樣完整交換 |
| `+0x3A8 + ordinal*0x20` | `0x60D192..0x60D1E8` 交換完整 `0x20` bytes（32 bytes） | `0x60D60D..0x60D660` 同樣完整交換 |

最後一組的 network index 地址是：

```text
roster + 0x3A8 + ordinal*0x20 + 0xC
       = roster + 0x3B4 + ordinal*0x20
```

例如移入方向把兩個 ordinal 左移 5，先把目的記錄的前／後 16 bytes 存到暫存區，再把來源的兩個 16 bytes 寫入目的，最後將暫存的兩半寫回來源。`+0xC` 屬於第一個 16 bytes，必然與整筆記錄同時搬移；這條資料流沒有另行把它覆寫為新 ordinal。

因此有三個不同的量必須保持區分：

- `entity ID`：雜湊表的 key，来自 entity+8。
- `roster ordinal`：雜湊表 entry+4 的 value，可因前段移入／移出而改變。
- `network index`：32 bytes 屬性記錄內的 DWORD，跟隨 entity 記錄搬移；不是上述雜湊 value。

### 對八槽重新配置的具體要求

四槽原排列恰好相鄰：`0xE8 + 4*8 = 0x108`、`0x108 + 4*0x70 = 0x2C8`、`0x2C8 + 4*0x38 = 0x3A8`。因此擴到八筆時需要處理這些平行陣列的布局，不能只擴大插入數量檢查。

本次記錄兩函式直接包含 roster RBP 的陣列記憶體運算元，移入 **37** 個、移出 **51** 個，含 RBP 被編碼為 x86 memory index 的情形。這是可重播的具體存取清單，不是全部擴容修改清單：

- `lea rdx,[rbp+0x2C8]` 後由 RDX 存取的記錄，以及暫存區 RAX/RDX 的拷貝，也必須依資料流追蹤。
- 修正平行資料位置時須保留 ID→ordinal 的兩筆更新。
- `+0x88` 是前段數量；不能假設它等於總 roster 數量或 network index。
- 移入的狀態初始化和移出的完整交換不同，新的布局須保留這個差異。

## 4. 斷線通知與移除前清理

### `0x540B60` 的精確作用

它以 entity ID 查 roster ordinal，`0x540BEF` 讀 `[roster+ordinal*8+0xE8]` 取得 entity 指標，接著測試 entity+0x14 bit 0（`0x540BF7`）及全域 `0x347CE18` 所指物件的 `+0x31276` 模式旗標。

條件成立時 `0x540C10` 取字串 RVA `0x22473B8`，原始 bytes 是 `disconnected\0`；`R8B=1`、`R9D=0`，於 `0x540C1A call 0x13462C0`，RCX 為該 entity 指標。這證明具名布林通知，尚不能把它等同實際傳輸層斷線或封包解碼。此回呼在上節派發順序中仍看到尚未清除的 bit 0。

### `0x540B20 → 0x605950` 的階段順序

`0xFDC820` 刪除流程先在 `0xFDC943` 使用 **原 context** 的 `+0xF0DFB0`（等於 owner+0xF0DF70），於 `0xFDC953` 呼叫 index 239 的清理回呼。

其後 `0xFDCC53/0xFDCC63` 才使用原 context 的 `+0xF0E9D0`（owner+0xF0E990），選到先前已確認的實際 roster 移除 `0x540A40`。再往後有引擎刪除呼叫與 entity 欄位失效化。

`0x605950` 的新增資料流包括：

- `0x605962` 從 `0x3326468` 取得同一 roster；以 ID 查 ordinal。
- `0x605A0D/0x605A15` 讀 entity 指標並測 bit 0；`0x605A22..0x605A56` 使用對應 `0x70` bytes 狀態。
- `0x605A5B` 讀 `roster+ordinal*0x20+0x3A8` 的第一個 DWORD，透過 `0xFD9C80` 解析關聯 entity。這不是 `+0x3B4` 的 network index。
- 部分路徑發出同名 `disconnected` 通知；關聯 entity 的 bit 0 條件成立時，`0x605DBF/0x605DC6` 從 context 全域 `0x346BF98` 呼叫 `0xFDC310`。
- 尾部使用字串 `player_count` 與 `roster+0x84` 派發通知。

所以 `0x605950` 可具體定性為先於實際 roster 移除的清理階段。本頁不以通知數量計算倒推它本身已經刪除名冊記錄。

## 5. 重播與界限

正式證據為 `roster_property_apply_evidence_v3.json`，SHA256：

```text
d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22
```

`roster_property_apply_replay.py` 成功重播：**364 筆選定指令記錄、7 條短 leaf 指令、兩函式 37／51 個直接陣列運算元**。選定區間可重疊，364 不是去重後的指令數。舊 `_evidence.json` 的直接運算元掃描漏掉 RBP 作 memory index 的编码；應使用 v3。v2 修正該項，v3 另補上兩組狀態記錄交換／初始化的選定指令。

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  five_player_feasibility_20260927/roster_property_apply_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output five_player_feasibility_20260927/roster_property_apply_replay_new.json
```

輸出檔必須尚不存在。來源 bytes、登錄證據或選定指令邊界不符時會中止。

這批剩餘回呼的界限：它們沒有提供 `index` 屬性接收／套用入口。**後續已從另一條 property 分派定位 `60C890`，見[接收端續查](roster_property_receive_findings.zh-TW.md)及[分派續查](property_dispatch_findings.zh-TW.md)。** 指標靜態登錄不證明某次執行真的經過該路徑；固定捕捉不含可寫 callback table，不能排除之後覆寫；八槽的其他 consumers、建立／移除、傳輸與執行期相容性仍須各自驗證。
