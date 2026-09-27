# 元件 260：身分閉合、64 筆預設配置及動態容量

## 結論

**已把 `property_dispatch` 末段 `owner+0xEB5E10 → 799790` 閉合到元件 260／global `3326A50`。** 既有 reference metadata 的名稱是 `WeatheringComponentData`；本輪不宣稱 reference metadata 已與 installed/runtime 資源相符。

**此元件的原生配置已能容納 ordinal 0–7，不需要為八槽修改容量常數或重排內嵌陣列。** 建構器直接建立 64 筆的四組資料陣列，以及 128 個 map buckets；追加前會按物件內容量檢查，必要時同步增長 backing。這是已審查的配置／追加／增長／搬移／property 接收路徑結論，不代表所有消費者已完整稽核，也沒有證明第五名玩家能進入這些路徑。

## 產物與重播

- `component260_capacity_replay.py`
- `component260_capacity_evidence.json`
- 正式 evidence SHA-256：`567cc06bda9590295bef91b61e20b6f5cb04c8c4410289e39f2c67a76fd09455`
- 重播結果：16 個完整 unwind roots、1959 條 root 指令、50 條已證入口 leaf 指令、47 個來源／語義 pins。
- 重用完整 registration leaf `556D90..55E1E3` 的既有證明，驗證 2127 個 assignment pairs，只輸出 index 260 的相關項目。
- capture 身分：`5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。
- `captured-data.bin` SHA：`31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。
- `capture-report.json` SHA：`132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`。

```powershell
& 'C:\Users\OvO\AppData\Local\Programs\Python\Python314\python.exe' `
  'five_player_feasibility_20260927\component260_capacity_replay.py' `
  --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output 'five_player_feasibility_20260927\component260_capacity_recheck.json'
```

輸出檔需尚不存在。過程只讀固定 capture 和工作區資料；沒有程序查詢、live read、新擷取或遊戲修改，也沒有修改總報告。

## 1. 身分鏈與 owner 邊界

1. 既有 `player_component_capacity_evidence.json` 已定位 index 260 的 `F0C110` callback slot：`F0C930`，由 `55C7F6/55C7FD` 寫入 `544FD0`。
2. `544FE4` 從 global `3326A50` 取元件指標。
3. owner publication 的 `568FEE` 執行 `LEA RAX,[RBX+EB5E10]`，`568FF5` 將它寫入同一 global `3326A50`。
4. `BC2D85` 取 `[global346BFC8]` owner，`BD1DE4` 傳 `owner+EB5E10`，`BD1DF2` 呼叫 `799790`。因此前一輪留空的 property 末段元件身分，現在可填為 **260**。
5. owner 建構的 `5567C0/5567CA` 呼叫 `7998B0(owner+EB5E10, ...)`；`5567CF/5567D6` 再呼叫 `B29410`。
6. 下一個 owner member 明確從 `EB5E68` 開始，差 `0x58`。此 `0x58` 是指標／計數描述區大小，資料 row 在分開的 heap backing，沒有「第 5 筆跨進下一個 member」的內嵌布局問題。

共用 owner 來源鏈的 `FDA352/360/375 → 551B7A/7D → 568236/239/242` 納入 pins；不是只因位移相同就推定同一物件。

## 2. 十張 callback table 的 index 260

| table base | 此 index 的入口 | 本輪範圍 |
|---|---|---|
| `F0B6F0` | `544F30` | 簡單追加 |
| `F0C110` | `544FD0` | 按分區追加 |
| `F0CB30` | `545130 → 7994E0` | 建立 36-byte property record／九個欄位 |
| `F0D550` | `545160` | property 後 callback，透過 map ordinal 取 primary row |
| `F0DF70` | 無 assignment | 不推定 live 值為零 |
| `F0E990` | `5450A0` | 移除並壓縮 |
| `F0F3B0` | `5452A0 → 79A420` | prefix 升格 |
| `F0FDD0` | 無 assignment | 不推定 live 值為零 |
| `F107F0` | `5452B0 → 79A970` | prefix 降格 |
| `F11210` | 無 assignment | 不推定 live 值為零 |

兩個 8-byte wrapper leaf 有 registration 作入口證明。各 callback table 的未證正式名稱不另創造。

## 3. 初始配置不是四槽

`7998CA` 直接設定 `S+4 = 0x40`（64）。`7998B0` 配置並清除四組 row backing，map 配置使用二倍 row capacity 後向上取 2 的冪，本例為 128。

| 欄位 | 作用 | 初始數量／容量 |
|---|---|---:|
| `S+4` | row capacity | 64 |
| `S+8` | high-water 計數 | 此建構器沒有提供獨立初始值證明 |
| `S+C` | total entity count | 0 |
| `S+10` | active count | 0 |
| `S+14` | prefix count | 0 |
| `S+18` | 擁有 map backing 的指標 | 128 個 pair |
| `S+20` | map descriptor 的 backing 指標 | 與 `S+18` 相同 |
| `S+28` | map bucket count | 128 |
| `S+2C` | map sentinel | 取自既有 sentinel global |
| `S+30` | map hash multiplier | 2 |

| backing 指標 | 每筆 bytes | 初始配置 bytes | ordinal 0–7 使用 bytes |
|---|---:|---:|---:|
| `S+38`，entity pointer | 8 | 512 | 64 |
| `S+40`，另一個 qword row | 8 | 512 | 64 |
| `S+48`，primary record | `0x178`（376） | 24,064 | 3,008 |
| `S+50`，property record | `0x24`（36） | 2,304 | 288 |
| `S+18/+20`，map pair | 8 | 1,024 | 八個有效 pair 的資料量為 64；其 hash 位置分布於 128 buckets |

四組資料 backing 合計 `0x6B00`（27,392）bytes，另有 map `0x400` bytes。`0x24` 是每 entity 的 property 大小；其中的 byte 欄位仍用四位元組 serialized slot，與前一輪格式結果一致。

## 4. 追加與容量增長

### 追加前依實際容量檢查

兩個追加入口都先比較 total count 與物件內的 map bucket count／row capacity，再寫新 row：

- `544F30`：`544F51 → 799CA0` 檢查／增長 map；`544F61 → 799EA0` 檢查／增長 rows。
- `544FD0`：`544FF4 → 799CA0`、`545004 → 799EA0`；使用 unsigned `< capacity` 通過，否則增長。
- 插入 entity ID → ordinal 的 map 使用 `172F790`；新 pointer 與 primary record 的位址來自 backing pointer 加 ordinal stride。
- 這兩條容量路徑沒有 `count+1 <= 4` 或 zero-address trap。

### 四組 row 一起增長

`799EA0` 保存舊容量，读取常數 `32.0`（readonly `23C7288`），呼叫 `21012E4`，將結果加上舊容量並寫回 `S+4`。對此正整數輸入，已證 leaf 的位元操作原樣返回 32，因此 **row capacity 每次加 32**。

隨後對 `S+38`、`S+40`、`S+48`、`S+50` 分別配置新容量、清新區域、複製舊容量的完整資料，釋放舊 backing，再保留新指標。每筆 stride 依序為 `8,8,0x178,0x24`。不是只增長 entity pointer 而遺漏 property row。

### Map 獨立增長並 rehash

`799CA0` 使用 readonly `23C6AD0` 的 float `0.5`，計算小正整數容量下的：

```text
new_map_capacity = next_power_of_two(old + ceil(float32(old) * 0.5))
```

初始 map 128 若滿，下一次為 256。函式分配新 pairs、以 sentinel 初始化全部 buckets、遍歷所有舊 buckets 並將非 sentinel pair 重新插入，釋放舊 `S+18`，更新 `S+18` 和 `S+20..37` descriptor。保留每個 entity 的原 ordinal。

`21012E4..21013A6` 完整 leaf 已存證；其特殊 NaN 尾跳 `2103E50` 不在上述小正整數容量路徑，不需要擴展成數學函式的全面分析。

### owner 批次路徑也會預先擴容

`576CF0` 的 `57EB2B..57EBCF` 使用同一 `owner+EB5E10`，當 total 達到 `ceil(float32(capacity)*float32(0.8))` 時呼叫相同 map／row growers，然後用 `7992D0` 移動分區並同步 active count。

`576D0D` 保存 owner 到 RBX，`576D15` 載入 float32 0.8 到 XMM6；重播檢查從此到 `57EBCF` 的整段 unwind 指令，這兩個暫存器沒有其他明確寫入。正式證據保留此來源鏈檢查，沒有只靠遠端同位移判定。

一般八筆資料從 64／128 的建構容量開始，無需觸發上述增長。計數代表該元件的 entity membership，不能假定是純玩家人數；其他 entity 若使用相同元件，仍可能進入原生增長路徑。

## 5. 搬移、移除、分區與釋放

### `7992D0` 搬移完整四組 row

函式簽名的可觀察效果是 `copy(self, destination, source)`：

- `7992F7..FB` 複製 entity qword；`799308..30C` 複製第二個 qword。
- `799310..3D0` 以 `ordinal*0x178` 定址；兩圈各 `0x80` 加尾端 `0x78`，共複製 `0x178` bytes。
- `7993CC..3F8` 複製 property record 的 `0x10+0x10+4 = 0x24` bytes。
- `79940B..466` 取搬移後 entity ID，找到 map pair，將 value 改成 destination ordinal。
- source 等於 destination 時直接返回；一般搬移不清除 source bytes。

`5450A0` 先移除 map key，再依 total／active／prefix 分區遞減相關計數，透過此 helper 填補被移除的位置。

### Prefix callbacks 的行為並非完全相同

- `79A420` 升格會增加 prefix，交換 entity pointer、primary、property rows，並清除 `S+40` 的目的 row；不能概括成四組陣列全都對稱交換。
- `79A970` 降格會減少 prefix，除上述三組外也交換 `S+40` 的 row。
- 兩者都依 map ordinal 定址並修正 entity map，沒有固定四槽作為 row 位址上限。

`545160` 的 post-property callback 仍假設有效 ID，沒有一般 not-found 安全保證；這是既有 membership 前置條件，不是八槽專屬容量問題。

### 釋放與 alias

`565E77..565EEF` 依序釋放 `S+38,+18,+40,+48,+50` 五個 backing。`B29410` 將此 system 以 tag `B1` 註冊到 `[global3326E68]` 的 `+6C0` 計數／`+6C8` entries；`565EF6..565F0B` 用同一 owner member 取消這個 alias。

既有 owner 位移可保留，因此本元件不需要像四槽內嵌元件那樣移動整個 descriptor 或更新它的所有 owner aliases。

## 6. 八人方案分類與證據界限

| 決策 | 判定 |
|---|---|
| ordinal 0–7 的資料配置是否足夠 | **足夠**；初始 64 rows、128 map buckets |
| 是否要把此元件某個 `4` 改成 `8` | **本輪沒有此需求**；欄位／alignment／stride 的 4 不能當玩家數 |
| 是否要搬移 owner descriptor 或加 inline rows | **本輪沒有此需求**；`0x58` descriptor 管理分開的 heap backing |
| 原生 grow 是否遺漏已知 property backing | **沒有**；四組 row 都按新容量重配 |
| 是否已證八人 gameplay 完整相容 | **未證**；其他 consumers、上游 API、平台與實際呼叫均未完成執行期驗證 |

正常使用仍以建構完成、配置成功及有效 membership／ordinal 為前提。配置函式實作和 allocation failure 回復沒有在本輪證明；程式也沒有在每次配置後做本地 null-check。`208AAA0`／`20988F0` 按既有零填／複製操作使用，本輪未重審整個 CRT 實作。

先前 `property_dispatch` 的 `null` 身分現在由本文件补足；既有版本和 SHA 保留作稽核。本結論只縮小八槽容量修改清單，沒有安裝、執行或宣稱完成八人 mod。
