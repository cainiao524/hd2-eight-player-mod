# 名單與角色 handle：dummy、player 與 avatar 的兩段處理

本頁只用固定 `game.dll` 捕捉及工作區 FileDiver 原始碼／名稱表。沒有讀取遊戲程序或安裝資產，也沒有執行引擎函式。[重播器](spawn_resource_identity_replay.py)固定來源 SHA-256，通過 FileDiver 原有兩個 Murmur64A 測試向量，再重算名稱雜湊並核對 91 個指令位置。結果在[證據 JSON](spawn_resource_identity_evidence.json)。

**後續進度：** 本頁記錄初步兩段資料流。引擎介面其後已由第三次授權擷取定位至 EXE `0x30FF50`，見 [介面分析](spawn_interface_findings.zh-TW.md)；元件 239 的 callback 已找到 [靜態登錄](spawn_callback_registration_findings.zh-TW.md)，player 的參考資產清單亦有 [獨立解析](spawn_resource_metadata_findings.zh-TW.md)。本頁下方「未知介面／未解表值」應依上述後續證據區分：靜態目標已部分補上，執行期表值及執行結果仍未驗證。

## 三個雜湊的名稱對照

| 捕捉中的 64-bit 值 | 工作區名稱表的精確雜湊匹配 | 程式用途 |
|---|---|---|
| `0xb04d927afb137b9b` | `content/entities/dummy` | `0xac9c19` 及 `0x10868bf` 引擎間接呼叫的 RDX。 |
| `0xcdc1f82ce3337a82` | `content/entities/player` | index `<4` 路徑取得 handle 後，於 `0x10868d7` 交給 `0xfdc140` 的 R8。 |
| `0x4d1c334d294dfa97` | `content/fac_helldivers/cha_avatar/avatar_helldiver` | 等待復活路徑取得 handle 後，於 `0xac9c2d` 交給 `0xfdc140` 的 R8。 |

名稱分別位於固定 `FileDiver/hashes/hashes.txt` 第 91225、91230、95433 行；重播也掃描 `thinhashes.txt`。這是完整 64-bit 雜湊相等的核對，沒有證明字串唯一，也沒有讀出目前遊戲安裝中的資產內容。因此以「名稱對照」描述，不能只靠路徑名稱推斷資產全部元件。

## handle 取得後還有一段資源處理

在 `0xac8800` 復活路徑中，`0xac9b9f` 把 avatar 雜湊放入 RBX。引擎呼叫 `0xac9c19` 使用 dummy 雜湊，回傳 EAX；隨後 `0xac9c23/26/28` 設置 `(RCX=原上下文, EDX=返回 handle, R8=avatar 雜湊, R9=另一份參數)`，在 `0xac9c2d` 呼叫 `0xfdc140`。其後同一 handle 才交給 `0x607820` 寫入 roster。

另一條 index `<4` 的路徑也先用 dummy 雜湊取得 handle，再將 player 雜湊與該 handle 交給同一個 `0xfdc140`。這說明兩條路徑傳入不同的後續資源雜湊，不能把兩次初始間接呼叫都直接命名為同一個「玩家角色分配器」，也未證明第二步另行建立另一個實體。

## `0xfdc140` 的已確認行為

此 helper 保存入口的 handle、資源雜湊和參數指標，並在一筆 24-byte 記錄的 `+0` 寫資源雜湊、`+8` 寫 handle。它還將同一資源雜湊配上字串 **`entity_path`** 傳給另一個介面呼叫；該字串位於捕捉 RVA `0x225d3a8`。

記錄選取使用上下文 `+0xf32f14` 的索引，並在索引達 `0x800` 時歸零；掃描也以 `0x800` 為界。這是此記錄區的搜尋／環繞行為，**不是 2,048 位玩家容量的證據**。

接著 helper 將上下文 `+0x40`、該記錄及參數傳入 `0x581320`，稍後再傳給 `0x581780`。這兩者按資源雜湊查表，取得 16-bit 索引清單，從下列位置取函式指標並間接呼叫：

| helper | 相對其入口上下文的表起點 | 呼叫位置 |
|---|---|---|
| `0x581320` | `+0xf0c110 + index*8` | `0x581421` |
| `0x581320` | `+0xf0cb30 + index*8` | `0x58152f` |
| `0x581780` | `+0xf0d550 + index*8` | `0x581a4e` |

此處的表基底相對於 `0xfdc140` 傳入的上下文 `+0x40`，不能混用為原上下文的同名偏移。程式支持「handle 建立後，依資源所對應的索引清單繼續分派處理」的資料流；各索引及函式的具名語義仍待確認。表值、清單內容及上述間接函式目標都不在舊捕捉中，尚不能把某個槽位直接指認為已知四槽 roster 的插入函式。

## 對八人實作的影響

1. `api+0xc0 → 首指標 → +0x18` 仍是未知的引擎介面，但現在知道它的兩個已查 caller 都傳入 dummy 名稱雜湊。這個指標布局尚不足以確認 C++ 類別／方法 ABI。
2. 除了底層 handle 產生，player 與 avatar 的後續資源分派也需要查證；只驗證 generic handle 可建立，不能證明第五名玩家的元件和玩法資料能完成配置。
3. 已找到三個具體的後續分派表位置，可作為追查真正 roster 插入事件的入口。它們與 tag `0x69` 的物件登錄表目前沒有已證實的索引對應。
4. 本頁沒有實作八人補丁，亦沒有驗證五人／八人同場玩法。
