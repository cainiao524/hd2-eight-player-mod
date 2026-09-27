# HostSynchronizer 嵌入引用核對

範圍：固定 build 25480438 的已捕捉程式碼。證據在 [host_relocation_inventory.json](host_relocation_inventory.json)，可用 `python host_relocation_inventory.py --capture-dir <pinned-capture-directory>` 重播。這次在原始 capture 驗證 100 個指令的位元組、指令邊界與 unwind root，9 組皆通過。

- 外層物件在 `+0x159b0` 直接嵌入 HostSynchronizer。建構點 `0x134dc9e` 形成其位址，`0x134dca8` 將外層物件指標放在 `host+0`；`0x134dcd0..0x134dcfe` 直接初始化四個 peer 記錄。這些操作不經由可替換的 HostSynchronizer 指標。
- 更新點 `0x134e42b/0x134e432` 把嵌入 host 傳到 pending consumer `0x108a440`。相鄰子物件從外層 `+0x162c8` 開始，即 `host+0x918`；`0x134e437/0x134e43e` 立即更新它。
- 子物件 `0x1083150` 透過 `[sibling+0]` 回到外層物件，直接讀寫外層 `+0x159c8`（`host+0x18`）。`0x134e545` 呼叫的 `0x10845b0` 路徑也如此。其他呼叫者的輸入型別尚未逐一證明。
- `0x1350680` 從外層形成 host 位址，直接處理四個 peer 與 `host+0x908/+0x910` 兩個尾端 qword。`0xb99ff0` 和 `0xbaa560` 從 owner list 取得外層物件，在 fallback 各掃四個 peer、stride `0x38`，再呼叫 `0x108d190`。

架構結論：`[host+0]` 已是外層 backpointer，不能直接改成 sidecar 指標；原位擴大 pending 會覆蓋有用途的尾端與相鄰子物件。現有清單是有 base provenance 的界限內子集，並非完整 hook 清單。其它 literal offset 命中、計算式位址、未查 helper 與動態 callback 仍需核對。
