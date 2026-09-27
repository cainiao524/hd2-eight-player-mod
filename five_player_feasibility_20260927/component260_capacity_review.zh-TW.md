# 元件 260：主代理獨立核對

對象：[component260_capacity_evidence.json](component260_capacity_evidence.json)，SHA-256 `567cc06bda9590295bef91b61e20b6f5cb04c8c4410289e39f2c67a76fd09455`。只讀原始固定 capture 與本機證據檔。

## 原始資料核對

- 遞迴核對 2,164 筆指令記錄，共 2,123 個不同位置；bytes、SHA、由完整 unwind fragment 起點重新反組譯的 asm 一致。
- 16 個 roots 的全部 chained fragments 與原 unwind 目錄重新枚舉結果一致，逐段 SHA 與選定 owner spans 的 SHA 一致。
- 三個無 unwind leaf 由兩個 registration assignment 及 rounding helper 的直接 call 提供入口證明；完整 body bytes 均重核。Callback initializer 本身另核固定 SHA 後從其已證入口解碼。
- 重算 owner header 間距 `EB5E68-EB5E10=58`；四組 backing 為 `64*(8+8+178h+24h)=27,392` bytes，map 另 `128*8=1,024` bytes。

## 實質結論核對

1. `568FEE/568FF5` 發布 `owner+EB5E10` 到 global3326A50，與 index260 的已登錄 callback 讀取同一 global；property dispatcher 的 `BD1DE4/BD1DF2` 因此可確定指向元件260。此前將該 index 留空是舊證據範圍，現在已补上身分鏈。
2. Constructor 設資料 capacity64，map capacity128，資料經四個 pointer 存取。與固定四筆內嵌元件不同，八筆資料不會因 ordinal4 而跨入 owner 下一成員。
3. 加入以總 entity count 比較 map／data capacity；資料擴容 +32 並同時處理四個 backing。Map 獨立擴容及 rehash，沒有將資料容量與 bucket 數混用。
4. `7992D0` 搬移兩 qwords、完整 primary 和 property record，並修正 map ordinal。分類增加／減少對 `+40` row 的操作不同，findings 已保留清零與交換的差別。
5. 所有上述容量結論以已初始化、配置成功、entity ID／ordinal 有效為前提，沒有證明外部 allocator、當前佔用量、全體 consumers 或多人相容性。

**審查通過。** 就這些路徑，沒有發現八槽需要修改此元件容量或重新配置 header 的理由；保留既有動態儲存是目前有證據支持的方案。這不是八人遊戲實測。
