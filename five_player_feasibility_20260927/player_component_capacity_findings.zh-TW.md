# 參考 player 清單的九個元件：七個加入入口限制四筆

> 後續更新：本頁記錄第一次從加入入口推導的容量結果。[生命週期與布局續查](PLAYER_COMPONENT_RELOCATION_PLAN.zh-TW.md)已補上其他陣列及實際外層邊界；尤其元件 33 的 `+0x90` 已證明有逐 ordinal byte，原先「槽位 4 落在未知區域」的疑問已解。元件 250 另有 `+0x160/+0x164` 兩組 bytes。應與續查合併閱讀。

> 容量續查也已補上[元件 3](component3_capacity_findings.zh-TW.md)與[元件 260](component260_capacity_findings.zh-TW.md)：初始資料容量分別512／64，均採指標資料陣列及動態增長。本頁原先對這兩個 helper 的未知範圍，請以後續的限定容量結論補充。[八項 map 模型](component_map_capacity_findings.zh-TW.md)另驗證了共用 insertion／deletion 的滿表與刪除行為。

## 結論與適用範圍

固定 FileDiver 參考資產中的 `content/entities/player` 列出九個元件。沿已證明的 callback 初始化表逐項追查，**七個元件的第一階段加入入口都先檢查 `count+1<=4`；超限分支包含寫入零位址的指令**。其中 226 與 239 分別對應先前的 tag `0x73` 數值儲存及 roster；本次新增確認 **33、41、43、238、250**。

具有 creation params 首 byte 分類的入口，其檢查位於分類條件之前；元件 43 的此入口沒有依該 byte 分支。即使之後走不同分類分支，也不會因此略過四筆護欄。八人實作需要處理這些元件的容量、儲存及生命週期，不能只增加房間名額或 roster count。

**清單來自參考資產；目前安裝的加密資產、實際載入清單與 callback 執行仍未直接驗證。** 本文確認靜態登錄及程式內容，沒有宣稱已觀察七個元件在此次遊戲執行或第五人加入。

## 證據鏈

1. [資源 metadata 證據](spawn_resource_metadata_evidence.json)：參考檔 SHA-256 固定為 `21377252b81fdbc670eba1e59a8ab64b170323df208f175e708992e4c1fb515e`。`player` 的 record 在檔案 `0x1505c`，九個 `uint16` 元件索引在 `0x28b72`。
2. [Callback 登錄證據 v2](spawn_callback_registration_evidence_v2.json)：`0x556d90..0x55e1e3` 完整 leaf initializer，2,127 組 RIP-relative LEA／RCX store，caller `0x568239` 證明入口。建構與資源派發都使用原 context `+0x40` 的 callback owner。
3. 每個元件的第一階段 slot 為 `callback_owner+0xf0c110+index*8`。本次重新核對完整 initializer 位元組與所有寫表目的地，然後從各已登錄入口按其 unwind 邊界解碼。
4. [本次重播](player_component_capacity_replay.py)從原始 capture 重建[證據 JSON](player_component_capacity_evidence.json)：**九個 callback、428 條指令**，每段有完整 SHA、指令位元組、全域來源、登錄 slot 及護欄。

## 全部九個入口

以下名稱是參考資產的 data type 名称，不能直接當成已確認的 native manager 正式名稱。全部位址均為 `game.dll` RVA；欄位位移相對各 callback 載入的物件。

| 元件索引 | 參考 data type | Callback | Global RVA | 本入口的容量行為 |
|---|---|---|---|---|
| 3 | `TagComponentData` | `0x516540` | `0x3326430` | count 與物件內欄位比較，不足時呼叫 helper；未證明八人安全。 |
| 33 | `ShipCustomizationComponentData` | `0x51ac70` | `0x33267b8` | `+0x8` 計數加一與 4 比較。 |
| 41 | `ShipModulesSyncComponentData` | `0x51bb50` | `0x3326998` | `+0x4` 計數加一與 4 比較。 |
| 43 | `KillStreakComponentData` | `0x51c110` | `0x3326af0` | `+0x4` 計數加一與 4 比較。 |
| 226 | 無 data-bearing 名稱對應 | `0x53e1b0` | `0x3326ae0` | `+0x37d08` 計數加一與 4 比較；先前 tag `0x73`。 |
| 238 | 無 data-bearing 名稱對應 | `0x540660` | `0x33264f8` | `+0x8e4` 計數加一與 4 比較。 |
| 239 | 無 data-bearing 名稱對應 | `0x540920` | `0x3326468` | `+0x80` 計數加一與 4 比較；roster。 |
| 250 | `ShipInventoryComponentData` | `0x5432b0` | `0x33266d0` | `+0xc` 計數加一與 4 比較。 |
| 260 | `WeatheringComponentData` | `0x544fd0` | `0x3326a50` | count 與物件內欄位比較，不足時呼叫 helper；未證明八人安全。 |

3 與 260 的兩組比較及 helper 分別是 `0x6b5a90/0x6b5c90`、`0x799ca0/0x799ea0`。本次没有完整分析這些 helper，僅能分類為「入口以欄位容量比較」，不能稱為無上限或已相容八人。

### 七個護欄的精確位置

| 元件 | `cmp eax,4` | `jbe` 的通過目標 | 未通過時的 `mov DWORD[0],0` |
|---|---|---|---|
| 33 | `0x51ac89` | `0x51ac99` | `0x51ac8e` |
| 41 | `0x51bb6e` | `0x51bb7e` | `0x51bb73` |
| 43 | `0x51c133` | `0x51c143` | `0x51c138` |
| 226 | `0x53e1cc` | `0x53e1dc` | `0x53e1d1` |
| 238 | `0x54067c` | `0x54068c` | `0x540681` |
| 239 | `0x54093c` | `0x54094c` | `0x540941` |
| 250 | `0x5432c9` | `0x5432d9` | `0x5432ce` |

實際運算為低 32 bits 的加一及 unsigned 比較；上述 count 解釋限定正常小計數域。沒有藉由 overflow 或例外處理推論可加入額外玩家。

## 新增五個元件的布局衝突

`i` 是各元件的**零起算儲存槽位**，不假定等於 network index。索引 4 表示第 5 筆。分類插入可能先搬移既有資料，所以不能直接把「第五次加入呼叫」等同於「此次呼叫寫槽位 4」。下表是在擴容後仍沿用原位移時，槽位 4–7 的確切位址後果。

| 元件 | 指標陣列 | 輔助記錄 | 原布局的衝突 |
|---|---|---|---|
| 33 | `+0x70+8*i` | `+0x98+0x50*i` | 指標槽位 4 是 `[+0x90,+0x98)`，其用途尚未查明；槽位 **5** 起點 `+0x98` 會覆蓋記錄 0。不能聲稱槽位 4 已碰該記錄。 |
| 41 | `+0x68+8*i` | 大記錄 `+0x88+0x9928*i`；另有 `+0x26528+0x58*i` | 指標槽位 **4** 起點 `+0x88` 覆蓋大記錄 0；大記錄槽位 **4** 起點恰是 `+0x26528`，覆蓋另一組記錄。 |
| 43 | `+0x68+8*i` | `+0x88+0x108*i` | 指標槽位 **4** 起點 `+0x88` 覆蓋記錄 0。 |
| 238 | `+0x948+8*i` | `+0x96c+0x44*i` | 指標槽位 **4** 佔 `[+0x968,+0x970)`，與記錄 0 的前 **4 bytes** 重疊。不能因起點還差四個 bytes 就認為安全。 |
| 250 | `+0x70+8*i` | `+0x90+0x34*i` | 指標槽位 **4** 起點 `+0x90` 覆蓋記錄 0。 |

### 初始化與分類的差異

- 33 的 `0x50` 記錄及 238 的 `0x44` 記錄，在已解析加入入口的兩類成功路徑都會清零；43 的 `0x108` 記錄則在共用路徑清零，沒有上述分類分支。
- 41 的大 `0x9928` 記錄及 250 的 `0x34` 記錄，清零只在 creation params 首 byte 非零的分支執行。41 的第二組 `0x58` 記錄兩類路徑均初始化。
- 有分類分支者的指標寫入位於合流後；43 直接經共用後段寫入。五者的重疊判斷皆不依賴是否清零輔助記錄。
- 33、41、238、250 的前段分類插入會分別呼叫 `0x665fe0`、`0x7af210`、`0x87b5d0`、`0x671610` 搬移 helper。完整搬移、移除、其他 callback 及外層物件邊界仍需後續分析。

## 對實作方案的影響

已知的 tag `0x73` 現在也由 **元件 226 的靜態 callback slot** 接上參考 player 清單，不再只是獨立找到的相似四槽系統；仍沒有直接觀察 runtime 派發。新增五個元件則擴大了需要同步處理的原生布局範圍。

目前證據支持「需共同擴容／重新配置多個玩家元件」，尚不足以選出安全完整的 native hook 或搬移方案。直接把七個 `4` 改成 `8`，会讓原布局上的指標或記錄寫到既有資料。本文不提供可套用補丁，也沒有安裝或執行 Mod。

重播（輸出須使用新路徑）：

```powershell
python -B five_player_feasibility_20260927/player_component_capacity_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-player-component-capacity.json
```
