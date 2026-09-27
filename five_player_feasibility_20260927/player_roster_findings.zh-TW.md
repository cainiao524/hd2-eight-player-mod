# 玩家 roster 四槽容量：限定離線靜態追查

來源為已固定的 Steam build `25480438` 擷取；`captured-data.bin` SHA-256 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。本次沒有啟動遊戲、讀取程序或寫入安裝檔。逐指令的位址、原始位元組及 SHA-256 在 [`player_roster_evidence.json`](player_roster_evidence.json)，由 [`player_roster_replay.py`](player_roster_replay.py) 重播產生。

## 所有者、初始化與全域指標

- 巨型 owner 建構流程 `0x551B60` 於 `0x5565EF` 取 `owner + 0xEA0818`，`0x5565F9` 呼叫 `0x60C9C0` 初始化該子物件。`0x556605` 隨後呼叫 `0xB27560` 註冊子物件；其 tag `0x69` 只可稱註冊標籤，不能推成事件或玩家容量。
- 全域 `0x3326468` 的識別到的直接寫入是 `0x568EC8` 取 `owner + 0xEA0818`，`0x568ECF` 把指標存入此全域。這將下述插入函式的 `rbx` 連回同一個子物件。
- `0x60C9C0` 於 `0x60C9CA` 將子物件 `+0x80..+0x87` 歸零，涵蓋 `+0x80`、`+0x84`。`0x60C9EF` 寫入 `+0xD8 = 8`，接著以 `0x60CA10` 起的迴圈初始化八個雜湊桶；這個 8 不代表可容納八名玩家。`0x60C9C0` 是無擷取 unwind 記錄的短 leaf，入口由已驗證的直接呼叫 `0x5565F9` 確定；重播程式從該入口順序解碼。

## 插入上限與相鄰記憶體

| 路徑 | 判斷及超限分支 | 指標插入與計數 |
| --- | --- | --- |
| `0x60CA80` | `0x60CA94` 讀 `+0x80`；`0x60CA9A` **先加一**；`0x60CA9C` 比較 4；`0x60CA9F` 若 `<=4` 跳到 `0x60CAAC`；否則 `0x60CAA1` 對位址 0 寫入 0。 | `0x60CB62` 增 `+0x84`，`0x60CB6E` 增 `+0x80`；`0x60CB85` 寫入 `[rbx + ordinal*8 + 0xE8]`。 |
| `0x60CBA0` | `0x60CBB0` 讀 `+0x80`；`0x60CBB7` **先加一**；`0x60CBBB` 比較 4；`0x60CBBE` 若 `<=4` 跳到 `0x60CBCF`；否則 `0x60CBC0` 對位址 0 寫入。 | `0x60CC48` 寫入 `[rbx + ordinal*8 + 0xE8]`；`0x60CC5F` 增 `+0x80`。`0x60CC70` 壓實路徑在 `0x60CE54` 將 `+0x80` 值同步至 `+0x84`。 |

兩個超限分支在組語上都於零位址寫入後線性落到下一條指令；正常 Windows 程序若零位址未映射，該寫入會先觸發存取違規。不能僅憑擷取還原其原始碼 assert 巨集或實際例外處理。

四個 qword 指標位置從 `+0xE8` 起，依次是 `+0xE8`、`+0xF0`、`+0xF8`、`+0x100`，最後一個至 `+0x107` 為止。第五個索引會落在 `+0x108`。兩條插入路徑分別在 `0x60CAE9`、`0x60CBDC` 對 `+0x108 + ordinal*0x70` 的另一組紀錄進行清零；`+0x2C8 + ordinal*0x38` 也是相鄰輔助紀錄。因此只改比較立即數，仍會讓第五個指標覆寫下一個欄位，並會留下其他按四槽排布的結構問題。

`0x60CB74–0x60CB7B` 維護 `+0x7C` 的最高觀測計數。診斷輸出 `0x56E7DE` 讀 owner 的 `+0xEA0894`，恰是子物件 `+0xEA0818 + 0x7C`；`0x56E7EC` 使用 `"player" : { "max" : %u, "capacity" : 4 }` 格式字串。原先該字串只算提示；現在可連到實際 roster 的更新欄位。遊戲 state-4 路徑 `0xACC622` 讀 `+0x84`，`0xACC638` 讀 `+0xE8 + ordinal*8`，所以同一組計數與指標也被遊戲邏輯消費。

## 證據邊界

這足以判定此原生 player roster 有明確四筆插入護欄及相鄰記憶體布局。它尚不能證明整體 entity heap allocator、平台 lobby 或後端服務的上限。兩個插入函式的精確直呼叫掃描沒有找到 caller；掃描沒有涵蓋間接呼叫、計算位址、未覆蓋的 leaf caller 或執行時派發。擷取不含可寫資料與動態執行狀態。`runtime_verified=false`。

重播：

```powershell
python five_player_feasibility_20260927/player_roster_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/player_roster_evidence.replay.json
```
