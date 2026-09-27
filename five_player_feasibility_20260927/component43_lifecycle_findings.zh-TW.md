# 元件 43：外層邊界、壓實與直接 owner 存取

## 本輪結論

元件 43 的固定物件位於 **`owner+0x2a988`**，下一個已初始化並發布的物件從 **`owner+0x2ae30`** 開始，兩者相差 **`0x4a8` bytes**。現有四筆 `0x108` 記錄恰好填到這個邊界，無法原地往後延伸成八筆。

除了修正指標與記錄陣列，八人配置還必須處理：

- 外層 owner 的直接更新及 count 複製，這些路徑不經元件 global。
- 移除後的壓實 helper：整筆 `0x108` 資料跟 entity 指標一起搬，並修正 ID→ordinal。
- 物件內指向自身 bucket 儲存的 hash pointer；搬移整個物件時不能保留指向舊物件的指標。
- RCX 傳 entity 的 callback 與 RDX 傳 entity 的另一組 helper，其 ABI 不同。

證據為 [component43_lifecycle_evidence.json](component43_lifecycle_evidence.json)，由[離線 replay](component43_lifecycle_replay.py)讀取已固定的 game.dll capture。共 11 個函式的完整 unwind fragments，以及外層 owner 選定片段；不計 initializer 登錄指令，共 **614 個不同指令位置**。沒有讀取活程序、修改遊戲或五／八人實測。

## 1. 三個靜態 callback 登錄

| 表基底，相對 callback owner | slot = 表基底 + 43×8 | 已登錄入口 |
|---|---|---|
| `+0xf0b6f0` | `+0xf0b848` | `0x51c080` |
| `+0xf0c110` | `+0xf0c268` | `0x51c110` |
| `+0xf0e990` | `+0xf0eae8` | `0x51c1a0` |

其餘七張表在已證明的 2,127 組 initializer 寫入中沒有此索引的 assignment。這不代表那些 slot 在執行期為 null，也不代表不存在其他初始化或派發。

前兩個入口都有 count+1 與 4 的比較及超限零位址寫入。`51c080` 用當前 `+4` 計數作插入 ordinal；`51c110` 用 `+8` 並更新兩個 count 及 `+0` 的最高值。兩者都把 entity pointer 與清零的 `0x108` 記錄放入相應槽位。

另外 `9baad0/9bab60` 含同型加入程式，但 entity 來自 entry RDX；已登錄的 `51c110/51c080` 則來自 entry RCX。這些入口不能未經參數轉換便共用一個 hook。

## 2. 物件身份與真實邊界

令外部 context 為 M、callback owner 為 O、元件物件為 S：

```text
FDA352: RCX = M + 0x40
FDA360: global[346BFC8] = RCX
FDA375: call 551B60
551B7A: RSI = entry RCX = O
551B7D: call 568230
568236: RBX = entry RCX = O
568242: global[3326540] = O
568464/56846B: global[3326AF0] = O + 0x2A988 = S
568472/568479: 下一個 global = O + 0x2AE30
```

同一建構程式的 `5528ca/5528d4` 將 `O+0x2ae30` 傳給另一個 constructor `9b9b90`，因此下一位置是實際初始化的相鄰物件。

| S 相對位置 | 已確認內容 |
|---|---|
| `+0` | 加入流程更新的最高 ordinal count；診斷讀者輸出此值 |
| `+4`、`+8` | 兩個加入／移除計數；owner 後續有 `+8 = +4` 的直接複製 |
| `+0xc` | 八筆 hash buckets 的內嵌儲存，每筆 8 bytes |
| `+0x50` | 指向上述 buckets 的指標 |
| `+0x58/+0x5c/+0x60` | bucket 數 8、sentinel key、乘數 2 |
| `+0x68..+0x87` | 四個 entity pointer |
| `+0x88..+0x4a7` | 四筆 `0x108` 記錄 |
| `+0x4a8` | 下一個 owner 子物件 |

`55285d..5528c8` 直接初始化 counts、bucket pointer、八筆 buckets 及 hash 參數。這裡的 8 是 buckets 數。完整 `172f790` 加入 helper 以 capacity 為探測上限，找不到位置時會繼續到零指標寫入；沒有在這個 helper 內看到四筆常數或配置／成長呼叫。不能把 bucket 數直接當成已驗證的八人支援，亦不能無證據假定擴容一定要改成 16 buckets。

若保留此 header 及八筆 buckets，只把兩個陣列連續排為八筆，指標起点仍為 `+0x68`，記錄起點會移到 `+0xa8`，結尾達 **`+0x8e8`**，新增 **`0x440` bytes** 的指標／記錄內容。這是布局算術；尚未驗證所有讀寫者，也不是可直接套用的 allocation 或補丁。

## 3. 移除與壓實必須共同處理

已登錄的 `51c1a0` 以 entity+8 的 ID 呼叫 `172f8a0` 移除 map entry，取得 ordinal，然後依相對 `+8` 分界更新 count、選擇來源 ordinal。另一個 `9bac20` 做同型處理，entity 來自 RDX，且會保留 entity+0x10 作返回值。

需要填補位置時，兩者把 S、目的 ordinal、來源 ordinal 傳給 `9ba8d0`。完整 helper 顯示：

1. 若兩個 ordinal 相同，直接返回。
2. 把來源 `S+0x68+source*8` 指標寫到目的槽位。
3. 按兩個 ordinal×`0x108` 定位記錄。兩輪各複製 `0x80` bytes，再複製尾端 8 bytes，總共 **`0x108` bytes**。
4. 以搬入 entity 的 ID 查 map，將 entry+4 更新為目的 ordinal。

這是**單向壓實複製**，不是兩筆交換。Helper 沒有在本段清零來源槽，也沒有從中推論新的 allocation。修改布局需要維持 pointer、整筆資料及 map value 的一致性。

## 4. 只改 global 會漏掉外層 owner 的直接存取

### 直接更新

`FDAEE0` 保存 entry context 為 RDI；`FDAF4B/4F` 把 `context+0x40` 傳給 `571250`。`57128d` 將該 owner 保存為 RDI；`5715cd/5715d7` 直接用 `owner+0x2a988` 呼叫 `9ba6c0`，沒有讀 `global3326af0`。

`9ba6c0` 按 `S+8` 的 count 迭代，讀 pointer `+0x68` 及 record `+0x88`，並處理記錄內部的 count 和小項目。它的外層迴圈是 count-driven；陣列搬移仍會影響實際地址。

### 直接 count 複製

`FDC780` 保存 entry context 到 RBX；`FDC7A3/A7` 把 `context+0x40` 傳給 `576cf0`。該函式在 `576d0d` 保存 owner 到 RBX；`577e7b/84` 直接執行：

```text
owner[0x2A990] = owner[0x2A98C]
即 S[+8] = S[+4]
```

若另配置整個 S 並只替換 global，這裡仍會改寫舊位置。

### 診斷與用途線索

`56a950` 讀取已證明為同一 owner 的 `global346bfc8`，`56b3df` 讀 `owner+0x2a988`，以原始字串輸出：

```text
"kill_streak" : { "max" : %u, "capacity" : 4 }
```

這提供與參考 `KillStreakComponentData` 一致的原生診斷名稱線索，不把它延伸為已確認的完整 C++ 類別名稱。

## 5. 每筆記錄內的 16 不等於玩家容量

另一個 global consumer `9ba430` 以 entity ID 查 ordinal，讀同一 pointer 與 `0x108` 記錄。記錄內有最多 16 個、間距 16 bytes 的項目，以及 `record+0x100` 的 count；相關資料更新在 `9ba526` 比較 `0x10`。

這個 16 限制位於**單筆玩家元件記錄內**，與外面的四筆元件記錄不同。八人擴容應保留兩層索引的用途區別，不能把該內層限制當作玩家數直接改動。其精確玩法效果沒有在本輪實測。

## 未完成的部分

- 本文固定了必要存取，沒有宣稱列出所有直接／間接讀者；global 交叉引用中的其餘大型 caller 仍可能需要納入搬移。
- 八筆滿 hash table 的完整生命週期尚未執行驗證；相關 shared helper 的靜態容量與玩家容量分開看待。
- 目前實際 resource metadata、callback 執行與八人建立結果未直接觀察。
- 需要結合其他元件布局，選定完整搬移方案及修改位置，再做第五位真人玩家的實際加入、生成、同步與任務測試。

重播（輸出須為新路徑）：

```powershell
python -B five_player_feasibility_20260927/component43_lifecycle_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output NEW-component43-lifecycle.json
```
