# Network-index float writer：主代理獨立核對

對象：[indexed_float_storage_evidence.json](indexed_float_storage_evidence.json)，SHA-256 `11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378`。只核對原始固定 capture，沒有查詢活程序。

## 核對結果

1. 遞迴核對 832 筆指令記錄，去重為 812 個位置；由 unwind fragment 起點重新解碼，所有 bytes、SHA、asm 一致。
2. 六個宣告完整的 root 均重新枚舉全部 chained fragments：`140C160` 一段、`140C200` 三段、`142B990/142C9B0/14335F0/208AA80` 各一段，保存集合與目錄完全相同。所有 span SHA 一致。
3. 七組 base prefix 的完整 bytes SHA 與暫存器 explicit-write 集合一致。核對 owner 恢復、manager global、實例位移與 constructor／writer／cleanup 的同一 D 算式，不以相同 stride 代替物件身分。
4. 檢查完整 initializer 的四次迴圈：起點 `80E18`、stride `298`、末端 `81878`；下一個 `81888` 子物件確實呼叫 `140C160`，首個 qword 由建構參數 RDX 寫入。
5. 重算 index 4 寫入 `[81884,8188C)`，與下一物件 `[81888,81890)` qword 有四 byte 交集。
6. 重算 index 7 寫入 `[8204C,82054)`，其相鄰子物件 base=`81D10+2*180=82010`，覆寫 `+3C/+40`。`140C160` 初始化該區；同一 D 的 cleanup 迴圈呼叫 `140C200`，後者以 `+28+i*4` 讀索引、乘 `208`、經 pool pointer 使用。是否讀到兩項仍取決於 count。

## 判定

可將此入口從「容量未知」更新為**條件成立時會覆寫既有欄位的四筆區域**。第 5 或第 8 個 network index 若抵達這次寫入，其地址不屬於可供擴容的空位。

沒有觀測第五名玩家、實際呼叫或錯誤症狀。父 callback 的 Galaxy_map 字串不足以命名 D 的正式類別，findings 保留用途未知是合適的。D 是大型物件，寫入仍在其整體範圍內不等於此陣列有空間。

獨立審查未發現需要修正的實質結論；沒有新增 probe、patch 或 runtime 驗證。
