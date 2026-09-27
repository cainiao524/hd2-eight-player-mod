# 玩家網路索引到裝備畫面槽位：身分、四筆布局與生命週期

## 結論

先前 `0xB90040` 的 tag `0xE5` 物件已確認是 **`MenuScreenLoadout`（裝備選擇畫面）物件**。`+0x27D8` 是「network index → 畫面槽位」表，`+0x27E8` 是反向表。兩表各四個 DWORD，並且相鄰；本地玩家被固定放進畫面槽位 0，其餘玩家從槽位 1–3 分配。因此映射值不應再稱為未知角色槽位，也不能等同 gameplay roster ordinal。

同一物件還有依 network index 尋址的四筆 `0x9F0` 資料，以及四個步幅 `0x1EE18` 的大型 UI 元件。已定位它們的初始化、填表、清除、使用者和物件配置大小。這些證據將八人 Mod 的修改範圍具體增加到裝備選擇畫面：單獨放寬已加入名單仍會在此遭遇四筆限制或布局覆蓋。

全部結果来自已固定的 game.dll 保存資料，沒有讀取遊戲程序、增加擷取或修改遊戲。沒有證明八人畫面、任務或生成成功。

## 1. tag E5 與畫面身分已直接連起來

`0x1465840` 將傳入 RCX 保存為 RDI；`0x1465894/0x146589B` 分別引用已保存字串：

```text
on_enter (hotjoin=%s, rejoin=%s)
MenuScreenLoadout
```

`0x1465AE1–0x1465AE4` 將同一 RDI 傳給初始化函式 `0x1466170`。之後 `0x1465FD4/0x1465FD9` 把 **同一 RDI 指標及 tag E5** 組成 16-byte 記錄，直接加入全域 `0x3326E68` 的多個登錄清單。

其中 `0x1466040–0x146605F` 寫入的清單 count 在 `+0x62E8`、記錄起點在 `+0x62F0`。這正是 `0xB90054–0xB90089` 遍歷且檢查 tag E5 的清單。此身分關聯不只依靠相同位移或函式鄰近。

`0xB90040` 依 peer ID 找到網路索引，再以表值選到 `screen+0x620E8+slot*0x1EE18`。`0x14719F0` 有相同直接畫面方法；`0x1893D40` 更新該子元件的 `+0x3C4` 欄位、搜尋 21 筆表，再將其 `+0x110` 子物件交給 UI 操作函式。具體代表哪一種裝備選擇尚未命名，但它不構成角色實體分配的證據。

## 2. 已確認的配置與相鄰資料

`0x1498AE8–0x1498AFE` 把 `0x2739D0` 作為大小參數傳入 allocator-like 間接呼叫；回傳記憶體接著被清零同樣長度，傳給 `0x14A17E0` 建構，回傳物件存入 screen manager 的 `+0xB0`。`0x1495A47–0x1495A54` 從畫面管理物件 `+0xB0` 取指標呼叫上述 `on_enter`。間接配置函式的具名身分仍未解析。

| screen 相對區間 | 已確認用途及容量 |
| --- | --- |
| `+0x10 .. +0x27CF` | 四筆 network-index 記錄，每筆 `0x9F0`。`0x10+4*0x9F0=0x27D0`。 |
| `+0x27D0` / `+0x27D4` | 索引狀態欄位；`+0x27D4` 存本地玩家 network index。 |
| `+0x27D8 .. +0x27E7` | forward[4]：network index → UI slot。 |
| `+0x27E8 .. +0x27F7` | inverse[4]：UI slot → network index。 |
| `+0x27F8` 起 | 畫面旗標及其他欄位，確實有讀寫。 |
| `+0x53A78 .. +0xCF2D7` | 四個大型 UI 元件，每筆 `0x1EE18`。 |
| `+0xCF2D8` | 下一個獨立 UI 物件，初始化中傳給 `0x187A640`，並加入畫面。 |

`0x14A17E0` 明確以計數 4，在 `+0x53A78` 起每次加 `0x1EE18` 呼叫子元件建構函式 `0x14AA5C0`。起點加四個步幅恰好等於 `0xCF2D8`，其後不是備用空間。

先前的 `+0x620E8` 是第一個大型 UI 元件內 **`+0xE670` 的子物件**，不宜把它當成整個元素的配置起點。

### 第五筆的具體衝突

- `forward[4]` 的位址就是 `inverse[0]`；`forward[4..7]` 會覆盖整張既有反向表。
- 若只把反向表搜尋改成八筆，`inverse[4]` 的位置就是 `+0x27F8`，會碰到畫面旗標。
- 若只把 UI 元件迴圈改成八次，元素 4 會從 `+0xCF2D8` 起使用下一個 UI 物件的記憶體。
- network-index 記錄 4 會從 `+0x27D0` 起覆蓋索引狀態與兩張映射表。

這些是依已確認布局作出的地址算術，不是八人補丁配置方案。

## 3. 建表、分配與釋放

### 初始化與本地槽位

`0x1466F26/0x1466F3C` 將 forward 的兩個 QWORD 清成全 1；`0x1466F31/0x1466F47` 對 inverse 做相同操作，等於各四個 DWORD sentinel `0xFFFFFFFF`。

初始化接著從全域 owner `0x347CEF0` 的 confirmed-peer 清單查本地 peer ID。`0x14670B0` 讀取已存 network index；`0x14670C7` 寫 `forward[index]=0`；`0x14670CF` 寫 `inverse[0]=index`。此序列只檢查 sentinel，沒有 `<4` 邊界檢查，因此把上游索引放寬至 4–7 後，這裡本身仍會發生前述重疊。

### 其他玩家槽位

`0x146C2F0` 的更新流程有兩條填表路徑。其中一條先從 gameplay roster 的 `+0xE8` 指標陣列取得角色記錄，取得對應 peer 身分，再查 owner 的 confirmed-peer 清單，讀取 network index。這是不同索引之間的轉換，沒有直接假定 roster ordinal 等於 network index。

`0x146C4A0–0x146C4BE` 搜尋 inverse[1..3] 的 sentinel；找到後 `0x146C4C9/0x146C4D1` 寫入兩張表。另一條路徑的成對寫入在 `0x146CC49/0x146CC51`。

tag E5 的另一個事件讀者 `0xB90190` 也有填表實作：先讀 `screen+0x27D4` 並明確要求 network index `<4`，再搜尋 UI slot 1–3，寫回雙向表。這不只是消費端 `<4`；配置槽位的生產端也是四槽位。

### 清除與畫面切換

`0x146CFD7` 取得 inverse 起點；迴圈依佔用／狀態判斷處理 UI 元件。`0x146D28E–0x146D2A6` 讀出 inverse[slot]，以該 network index 清 forward，並清 inverse 本身。`0x146D2C0` 明確將迴圈限制為四筆。

`0x1470A40` 的另一個畫面切換流程也只對四個 UI 元件呼叫 `0x189E080` 和 `0x1451100`。目前沒有聲稱完成整個畫面的 destructor、解除登錄或全部間接存取審查。

## 4. 額外兩個與八人直接相關的邊界

1. **Loadout 更新本身檢查 roster ordinal。** `0x146C3B1` 從 roster 指標清單取記錄；`0x146C3D1` 比較目前 ordinal 與 4，`jae` 到 `0x146D30B` 呼叫 `0x2088C0C`，後面是 `int3`。此路徑包含四個 byte 的堆疊狀態區；它不是能直接忽略的普通畫面選項。底層錯誤函式仍未具名。

2. **同畫面還有獨立的四笔資料記錄。** `0x146FC40` 從 roster peer 查到 network index，`0x146FDE6` 再要求 index `<4`。它在 `0x146FE31–0x146FE4A` 與 `0x146FF65–0x146FF9F` 依 **network index** 複製 `0x9F0` bytes 到 `screen+0x10+index*0x9F0`。同一函式另從 forward 表取得 UI slot，兩者有不同步幅，進一步證明 network index 與畫面槽位不能混用。

## 重播與下一步

最新主證據是 **`index_slot_mapping_evidence_v2.json`**：9 群、227 條記錄、226 個唯一指令位置；每筆由保存的 unwind fragment 起點解碼以驗證邊界，並固定原始 bytes、SHA、root 與 RIP 目標。初版 `index_slot_mapping_evidence.json` 少了最後一組 `0x9F0` 記錄證據，保留作歷史。

重播工具：

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  .\five_player_feasibility_20260927\index_slot_mapping_replay.py `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output .\five_player_feasibility_20260927\index_slot_mapping_replayed_new.json
```

`index_slot_mapping_fields.json`、`index_slot_mapping_storage_fields.json` 提供位移候選；`index_slot_mapping_xrefs.json`、`index_slot_mapping_ctor_xrefs.json` 固定直接呼叫來源；`index_slot_mapping_tag_candidates.json` 保存 tag E5 即值候選。候選集合仍包含其他物件，不能全部歸為此畫面。

此分支接下來需要整理**整個 loadout 物件的移位／間接引用清單**，包含雙向表、`0x9F0` 資料、UI 元件與四筆堆疊暫存；再選擇具體的八人畫面配置和生命週期修改點。單純擴容一張映射表不足以形成有效 Mod。這些 UI 路徑的證據也不能替代網路加入、角色生成與同步的八人驗證。
