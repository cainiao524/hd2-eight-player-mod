# Property 分派：主代理獨立核對

核對固定離線 capture，沒有讀取活程序。審查對象：[property_dispatch_evidence.json](property_dispatch_evidence.json)，SHA-256 `9cabca2fa61fd59e9c776230da80ad68716f947c46f56c6b9c203ba011d0d55d`。

## 已完成核對

- 由原始 capture 的完整 unwind fragments 起點重新反組譯，核對 JSON 中遞迴出現的 915 筆指令記錄，共 848 個不同位置的 bytes、SHA 與 asm。
- 獨立枚舉所有 chained fragments，11 個 root 的保存集合與原始 unwind 目錄完全相同；逐段 SHA 及五個選定 span 的 SHA 一致。
- 重讀 `BD9EB8` 的 1,855 個 DWORD table entries；在選定 case 範圍中，唯一命中是 selector `3A7 → BD138C`。表雜湊吻合。
- 直接閱讀入口與 API 分支：`R8B=0` 用介面 `+A8`，非零用 `+B0`；後者 AL=false 時返回。16-byte output 的 `+0` 是 payload pointer，`+8` 是 selector。沒有把此 API output 命名成已驗證的網路封包 header。
- 核對六次 receiver 呼叫及共用 cursor：`4+32+64+56+88+36=280` bytes。Roster 在起始 cursor=4 時讀自身第 4 個 DWORD，因此 index 位於整體 payload `+0x10`。
- 最後 `799790` 讀九個四 byte 槽，其中一個槽只取 byte，但仍使 cursor 加四；前置 `671860` 同樣只讀 byte、消耗四。未以目的欄位寬度代替序列化消耗量。
- `FD9BA0` 的 handle map miss／sentinel 路徑沒有普遍的有效 entity 保證；某些 no-entry 路徑會以零作指標讀取。不能把 creation 先建立再套用的順序延伸為所有 callers 都安全。

## 判定與限制

本次限定分支的 selector、呼叫順序及 280-byte 消耗量可接受。這是一份單一 entity 的資料格式；它不含本次辨識出的四位玩家陣列，也没有要修改的四人容量值。`73E` 是 selector 最大值，四 byte 是欄位槽寬，均不能視為玩家上限。

參考 component index 的清單迭代發生在其他 caller 的 callback 階段；此 dispatcher 使用 API 提供的 selector。API 如何產生 selector／payload、執行期是否給 player 選擇 `3A7`、完整 buffer 長度與 service 行為仍未知。

末段 `owner+EB5E10` 的 36-byte 消耗量已驗，正式 artifact 留空其 reference component index，這是適當的證據界線。未把它未核實地標成 260。

本審查沒有生成或測試八人 Mod。
