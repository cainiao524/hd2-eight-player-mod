# 完整名冊搬移／三函式共同建置：審查紀錄

## 審查版本與分工

原 emitter 作者完成 [roster_move.py](../Native/roster_move.py)、固定來源 replay／evidence／findings。主代理閱讀候選、撰寫 [roster_bundle.py](../Native/roster_bundle.py) 與獨立指令執行測試，再核對結果。另一代理直接從保存 capture 與 Capstone 核對 emitter，之後獨立審查 bundle 與 chain oracle。靜態審查者沒有修改 source 或重跑測試，也沒有操作遊戲程序。

- Mover source SHA-256：`cc6df86a567fda45fcac9a258372df52aad085fff67a620b5f4a2d46c100c23f`。
- Bundle source SHA-256：`7041074e818277f45476b91611bf8a37a0a94a9244c48c321148341dac824fbf`。
- Mover evidence／recheck SHA-256：`115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242`。
- 固定原 body SHA-256：`b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b`。

## 有限靜態核對

獨立審查未發現此改接範圍內的具體缺陷，核對了：

1. 保存原 body 的全部 430 bytes／78 指令與 evidence 一致；沒有外部 call／RIP operand。
2. 從原 operands 重算 primary 14 個 displacement 加 `20h`、auxiliary 8 個加 `1E0h`、property 4 個加 `2C0h`；原 body 變動限這 26 處與兩 splice。
3. `C419` guard 位於任何陣列／map 存取與 prologue stack 寫入之前；兩 ordinal／binding 拒絕契約符合實際指令。
4. 成功路徑以 `B−E8h` 存取四組陣列，`C543` 從新目的 pointer slot 取 entity，`C54A` 在第一個 map 讀取前恢復原 S。
5. 同低 DWORD ordinal 的直接返回與不同時的零延伸語義保留；epilogue 恢復非揮發暫存器。
6. Bundle 將 pair 的 property 子區間替成完整 `680h` 區間，保留 pair 所有 code／reject／原函式／global／helper 範圍，再加入 mover 的相關範圍。這避免只檢查 property 卻漏掉其他三組陣列碰撞。
7. Chain 的 receiver 以 entity ID 查更新後的 map，沒有在測試直接指定接收 ordinal。其 whole-page oracle 核對四組 bytes、map value、cursor、來源保留與 network index。

此範圍不含 Windows unwind 正確性、hook 可用性、引擎同步、完整 caller 合法狀態、全域 alias 或真實 multiplayer。

## 第一輪測試失敗與修正

第一轮 11 個方法中出現 69 個 assertions failures，沒有 errors。完整非 stack 記憶體頁比對已通過；失敗集中在寫入事件的粒度：測試預期 MOVUPS 是一筆 16-byte hook，Unicorn 2.1.4 將它回報成兩筆相鄰的 8-byte hooks。原四格函式對照也出現相同差異。

修正只在測試：將事件轉成**完全有序的 byte 地址序列**比對，仍拒絕多寫、漏寫、重複或順序不同；每頁全部最終 bytes 的独立 oracle 保留。沒有修改 emitter 來迎合模擬器。

修後 [tests/test_native_roster_move.py](../tests/test_native_roster_move.py) 的 SHA-256 為 `603259862dcc109b0be9c3227954ff771342fbfd416eb71eb9f0687e770bb687`。重跑 [正式報告](native_roster_move_tests.json)：**11 個方法、103 次 x64 執行、0 failures／0 errors**。之前失敗狀態由本節保留，正式 JSON 為修後結果。

| 執行類別 | 次數 |
|---|---:|
| 八格完整搬移全部來源／目的 | 64 |
| 原四格原函式對照 | 16 |
| 高 32 bits／另一 ASLR | 4 |
| 相等低 DWORD／無資料映射 | 4 |
| 不相等輸入的 ordinal／binding 拒絕 | 6 |
| 三條拒絕 rel32 共同範圍的兩端 | 6 |
| Producer → move → receiver | 3 |
| 合計 | 103 |

靜態修改範圍、指紋、輸入範圍及 bundle 交疊測試包含在 11 個方法中，沒有額外計作指令執行。既有六套 79 組／106 次報告的 source／evidence pins 維持核對，這輪沒有重跑它們。七套累計 90 組／209 次屬保存離線結果，不能解讀為多人成功率或遊戲覆蓋率。

## 測試與實作的必要前提

- Mover fixtures 具有有效來源 entity 與 map entry，目的舊 key 已由模擬 caller 移除。Whole-page oracle 不證明所有 caller 都維持這個不變量。
- 原 map empty／miss 行為仍可能在 copy 後出錯；guards 只驗 ordinal 與 binding。
- Chain 的 producer 完整初值／descriptor 語義由既有 producer suite 的固定 oracle 負責；chain 著重同一儲存、搬移與更新後 map 的串接。Allocator 使用成功契約，incoming payload 人工提供，沒有 serializer／transport。
- 活記錄 opaque bytes、資源 ownership、外部 aliases、建立／清理與發布時點未完成。原生初始化證據不支持「全零八格即有效」。
- 三種拒絕 continuation、Windows unwind、可恢復 hook、其他插入／壓實／分類／移除／讀者及八人實測均是剩餘工作。

有限候選可納入 `0.6.0-offline`；`installable_mod`、`game_integration`、`multiplayer_verified` 全部維持 false。
