# 八格 entity map 模型：主代理獨立審查

正式對象：[evidence v4](component_map_capacity_evidence_v4.json)，SHA-256 `f8918247d729a1bde957739ffa7d724ffceba831416e8d526aacc5f70e53e61b`；replay SHA-256 `6f6eba90fde65944a2f9c1a05de35febc23814c501066235b05c7d86c6a955f3`。

## 原始程式與模型核對

- 從 capture 重新枚舉三個 roots 的全部 fragments，核對 184 條完整指令的 bytes、SHA、asm；插入／刪除共 112 條，代表性 lookup 所在的 receiver 共 72 條。
- 獨立閱讀 `MapModel` 與限定 `Interpreter`：32-bit 暫存器寫入零延伸、乘法／LEA 取低 32 bits、unsigned compare、八 byte bucket 同時搬移 key/value，以及刪除 hole 的 backshift 條件均與保存程式對應。
- 檢查 Interpreter 省略算術旗標的界線。Reaching-definition 程式按 CF／ZF 各自回溯正常 CFG，將 undefined flag 也算成寫入；19 個實際 flag consumers 均由 CMP／TEST 供應，不依赖省略的 ADD／SUB／INC／IMUL 旗標。
- 全表新增第九個不同 key 時，第一次無效存取是 `172F7F2 [RCX+4]`，地址為 `4`；沒有把它錯寫為首先寫地址零或安全返回。

## 獨立重播

主代理重新執行正式腳本，輸出 [review recheck](component_map_capacity_review_recheck_v4.json)，與正式 evidence **逐 byte 一致**。

| 檢查 | 通過量／範圍 |
|---|---|
| 八筆 key 的 home 分布 | 65,536 種（固定 cap8、multiplier2） |
| 滿表逐項刪除、重插、既有 key 更新 | 每項 524,288 次 |
| 完整刪除順序 | 80,640 種，645,120 次連續刪除 |
| 高階模型與指令直譯對照 | 4,506 次操作，394,110 指令步驟 |
| 指令／條件分支覆蓋 | 插入／刪除 112/112 指令，11 個 conditional 的兩結果 |
| 其他輸入 | 多種 2 的整數次冪容量、乘數、sentinel0／FFFFFFFF、高位元 key、32-bit 溢位算術；另示範非 2 的整數次冪容量與 invalid-key 問題 |

## 可接受的設計結論

**在文件列明的不變條件下，這兩個 map helper 的離線模型能保存八個有效 key，刪除後仍可查找與重新插入。** 不需要單因玩家數從四增至八便一律將 buckets 改成十六。

必須維持最多八個不同有效 key、正確 sentinel、非零且為 2 的整數次冪的 capacity、足夠的 bucket backing，以及外層 ordinal 對應資料陣列的範圍。更新已有 key 不會新增佔用；第九個不同 key 沒有安全失敗路徑。

Map-invalid 與代表性 lookup 的 entry invalid-ID 來自不同 global 地址。這份模型把二者人工設為相同值做 lookup 對照，沒有捕捉其執行期相等關係；有效 ID 仍需避開相關 invalid 值。此假設與 map 內部八項測試分別列明，沒有被擴大成全遊戲證明。

審查通過限定結論。Python 模型與有限指令直譯不是原生遊戲執行或形式化驗證，亦未驗證任何遊戲配置、八人網路或玩法。
