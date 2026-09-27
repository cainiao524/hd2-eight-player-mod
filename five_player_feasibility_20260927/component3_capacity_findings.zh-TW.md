# 元件 3：既有 512 筆容量與動態擴容

## 對八人方案的結論

參考 player 清單的 component index 3（`TagComponentData`）已從已登錄 callback 接到同一 owner 物件及初始化程式。它**不是四筆內嵌陣列**：初始化設定 512 筆資料容量、1,024 個 hash buckets，資料透過兩個 heap pointer 存取，加入流程另有擴容路徑。

因此，對本次核對的初始化／加入／搬移路徑，**沒有需要把四筆容量改成八筆的地方**。八人實作清單可將這個元件列為「保留既有動態儲存，後续驗證相容性」，不需跟七個固定四筆元件一起重排其 header。

容量計算的是此元件的所有 entities，不是玩家專屬額度；當前佔用量、配置成功、完整下游及八人遊戲行為均未觀察。上述結論限定固定版本的程式路徑，不能單憑 512 宣稱整個模組已支援八人。

## 1. 元件身分與 owner

- Callback initializer 在 `F0C110+3*8` 登錄 `516540`；它讀 global `3326430`。
- `56825E/568265` 將 `owner+E8` 發布到同一 global。下一個發布物件在 `owner+128`，兩者間距 `40` bytes。
- `551BB9/551BE2/551BE5` 以同一 `owner+E8` 呼叫 constructor `6B5750`。
- 後續 registry 使用 tag `91` 保存此物件到 `5C00/5C18` 兩個表；這是該 owner constructor 的兩個已證副本，沒有宣稱全遊戲只有兩個別名。

四個已登錄 callbacks 為 `5164C0`、`516540`、`5165C0`、`516620`；另六個 table slot 在此 initializer 沒有 assignment，不能据此判定 runtime 永遠空白。

## 2. Header 與分離的資料配置

| S 內欄位 | 已核對用途／初始值 |
|---|---|
| `+0` | 兩個資料陣列的容量，constructor 設 `0x200=512` |
| `+4` | 高水位追蹤欄位；本 constructor 未證明其初始值 |
| `+8/+C` | 加入流程使用的兩個 count；constructor 一次 qword 寫零 |
| `+10` | Hash bucket backing pointer |
| `+18` | Map storage pointer，初始化等於 `+10` |
| `+20/+24/+28` | Bucket 容量 1,024、invalid key、乘數 2 |
| `+30` | Entity pointer 陣列的指標，每筆 8 bytes，初始 4,096 bytes |
| `+38` | 每 entity 的 tag 值陣列指標，每筆 8 bytes，初始 4,096 bytes |

Bucket 陣列初始 `1024*8=8192` bytes。兩個資料陣列與 buckets 都透過外部配置介面取得，沒有把資料接在這個 `40`-byte header 後方。故 owner 下一成員不是這些陣列的擴容邊界。

`516620` 用 entity ID 查 map、讀 `+38` pointer，再把該 entity 的 tag masks 做 OR。函式內 `cmp EDI,40h` 是每 entity 的 tag 輸入迴圈，**不是 64 名玩家或四名玩家限制**。

## 3. 加入與擴容

`516540` 在寫入前先比較總 count 與 map capacity `+20`，滿時呼叫 `6B5A90`；再比較資料 capacity `+0`，滿時呼叫 `6B5C90`。另一登錄加入入口 `5164C0` 和分離入口 `6B5E30/6B5EB0` 的完整程式也已保存，均使用物件容量而非常數四。

### 資料陣列：每次增加 256

`6B5C90` 從 readonly `23C73D8` 載入 double `256.0`，經 `21012E4` 的整數輸入路徑後，加入舊 capacity 並寫回 `S+0`。在已核對的正常小整數範圍，512→768→1024。

它為 `+30` 和 `+38` 分別提出 `new_capacity*8` 的配置要求，呼叫清零 helper，再以新 pointer、舊 pointer、`old_capacity*8` 呼叫 `20988F0`，最後把舊 pointer 交給釋放介面。兩個陣列都隨同一容量增加，未見只增一邊的情況。

### Map：增加後取 2 的整數次冪容量

`6B5A90` 讀 readonly `23C6AD0` 的 float `0.5`，在正常小整數容量下計算 `old+ceil(old*0.5)`，再由重複 SHR／OR 向上取 2 的整數次冪容量。例如 1,024→2,048。

此函式初始化新 buckets，逐一重新插入旧表中非 sentinel 的 key 與原 ordinal，並替換 storage／capacity／乘數。這是 map 的獨立增容，不能與資料陣列的固定 +256 混為一談。

本次保存 `21012E4..21013A6` 的 leaf 程式，入口由兩個已證直接 calls 固定。對 256、512、1024、2048 的 bit-mask 路徑計算顯示這些整數輸入原樣返回。NaN 相關外部尾分支不屬於這些容量例子，未展開分析；沒有執行此 helper 或任一遊戲函式。

## 4. 移除與搬移

`5165C0` 先經共用 map deletion 取原 ordinal，再按分類區域決定搬入來源。`6B5620` 在 source 與 destination 不同時：

1. 複製 entity pointer qword。
2. 複製 tag value qword。
3. 以搬入 entity 的 ID 查 map，把 value 改成 destination ordinal。

它使用 `+30/+38` 的指標，沒有四筆內嵌位移。`6B5A40` 也把 `+30/+10/+38` 三個 backing pointer 分別交給釋放介面。

## 5. 證據與界限

- [Replay](component3_capacity_replay.py)
- [Evidence](component3_capacity_evidence.json)：11 個完整 roots、797 條 root 指令，另保存 owner pins、callback assignments、常數及 rounding leaf。
- Evidence SHA-256：`1ed27a70a2a1662c3e324c774da877687ae0388d54fe4320e94057f07fd14330`。

配置／釋放採外部介面槽 `+58/+60`；本支線沒有解析或執行其目標，也未展開通用 copy helper 的全部實作。容量充足與擴容順序是靜態程式證據，配置成功及資料在當前遊戲中正確搬移仍需驗證。

Global 的其他消費者沒有全部審完；本研究沒有提出改動這個元件的容量常數。當前目標仍是完成八人 Mod，這份文件本身不構成可玩原型。
