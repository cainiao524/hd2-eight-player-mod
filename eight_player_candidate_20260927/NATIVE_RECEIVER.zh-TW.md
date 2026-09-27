# 原生候選：八份 roster property 的接收改接

## 本元件完成什麼

[Native/roster_receiver.py](Native/roster_receiver.py) 產生真正的 x64 指令 bytes，將固定 build `25480438` 的 roster property receiver 改成寫入指定的八份獨立儲存。它以保存證據中的完整 `60C890` 函式為來源，保留 entity ID 查表、八個 DWORD 的讀寫順序、32-bit network index 內容、cursor 推進與正常返回。

這是**單一接收函式的原生候選產生器**。目前沒有入口／caller hook、原生頁面配置、Windows unwind 登錄或完整 roster 改接；不能單獨啟用，也不是可安裝八人 Mod。產生器不讀取或修改遊戲程序，只處理提供的 bytes 與地址。

## 固定來源與修改位置

- [接收函式證據](../five_player_feasibility_20260927/roster_property_receive_evidence.json) SHA-256：`bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10`。
- 原函式 `[60C890,60C9BF)`，303 bytes，SHA-256：`23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411`。
- 成功入口 ABI：`RCX=roster S`、`EDX=entity ID`、`R8=payload base`、`R9=uint32 cursor pointer`。Network index 是記錄的第四個 DWORD，與 map 找到的 roster ordinal 分開。
- 詳細切點及已有 caller 身分見[原生切點分析](../five_player_feasibility_20260927/roster_property_receiver_native_cutpoint_findings.zh-TW.md)。

原 303 bytes 的相對布局保留。候選只修改原 body 兩處：

1. `60C897` 的 RIP-relative displacement，仍指向實際 `game_base+3483C20` sentinel；不保留搬移後已失效的原 displacement。
2. `60C932` 起兩條完整指令、共 6 bytes，換成 `E9 rel32` 與 NOP，跳到附加的 trampoline。成功時重播原兩條指令，再跳回對應 `60C938` 的第一個 store。

附加指令先以 unsigned 比較拒絕 ordinal `>=8`，包括 map miss 的 `FFFFFFFF`；再要求實際 R11 與提供的 roster binding 相等。成功時設 `R11=property_address−3A8h`，讓原八個 stores 寫入 `property_address+ordinal*20h+[0,4,...,1C]`。RAX 在 ordinal 檢查後用作 binding 比較暫存，之後由原本第一個 payload load 覆寫；不增加 stack 操作或原生 calls。

**綁定不符時沒有原四槽 fallback。** 否則 ordinal 4–7 仍會寫入相鄰物件。地址檢查只涵蓋已知 code、roster、property、sentinel、原 receiver 及 reject 入口之間的範圍；不能判定整個程序 allocation map、有效權限或物件存活。

## 明確的拒絕入口契約

產生器要求呼叫者提供 `reject_address`，不提供假裝成功的預設返回。機器碼拒絕時：

| 欄位 | 值／狀態 |
|---|---|
| R10D | `1`：ordinal 不在 0..7；`2`：roster binding 不符 |
| RSP | 入口 RSP−8；`[RSP]` 是已保存 R14，`[RSP+28h]` 是已保存 RBP |
| RBP／R14 | payload base／cursor pointer，尚未執行正常 epilogue |
| R11／R8 | 輸入 roster／uint32 ordinal×32 |
| RCX | uint32 入口 cursor |
| RAX | reason 1 時為 uint32 ordinal；reason 2 時已是 expected roster 地址，不可當作通用 ordinal |
| 記憶體 | 本 receiver 尚未讀取 payload 欄位，也未寫 property 或 cursor；原 prologue 的 stack 保存與 map／cursor 讀取已發生 |

真正的整合層必須在該入口正確處理此函式 frame、診斷，並停止本次完整 property dispatch。僅 `ret`、略過 32 bytes 或保持 cursor 後繼續下個元件，都沒有被證明能維持遊戲狀態。因此此候選不能在缺少該處理時安裝。

Binding 檢查發生在原 map lookup **之後**；它不保護此前的壞 roster pointer、map backing 或 cursor pointer 存取。輸入 ABI、有效 map header、合法記憶體、足夠 payload、無相互覆蓋、來源與目的存活及引擎同步仍是外層的必要條件。產生器也不以地址相等推論 allocation generation 相同。

## 產生與重現

Python 標準庫即可執行產生器。所有地址均必須明確提供；它們是整合／測試輸入，工具不會自動查詢程序。輸出是帶機器碼 hex、原始碼指紋、修改範圍、拒絕狀態及缺口的 JSON，`installable=false`。

下列地址**全部是離線範例**，不能直接用於遊戲。從工作區根目錄執行，輸出路徑須尚不存在：

```powershell
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/Native/roster_receiver.py --evidence five_player_feasibility_20260927/roster_property_receive_evidence.json --game-base 0x7FF800000000 --code-address 0x7FF805000000 --roster-address 0x20000000 --property-address 0x30000000 --reject-address 0x7FF805010000 --output eight_player_candidate_20260927/verification/native_roster_receiver_synthetic.json
```

支援 low canonical 地址；game base 須 4 KiB 對齊，code base 須 16-byte 對齊，roster／property 須 8-byte 對齊。外部 sentinel 的 RIP displacement、trampoline 的相對分支及 reject 入口須在各自 signed rel32 距離內，不會默默截斷。

## x64 指令驗證

測試使用 [Unicorn](https://www.unicorn-engine.org/docs/tutorial.html) 執行隔離的 x64 記憶體情境，並用 Capstone 檢查實際產生指令；不把原生遊戲碼載入主機執行。依賴只安裝在本候選資料夾：

```powershell
& 'C:\Program Files\Python312\python.exe' -m pip install --disable-pip-version-check --only-binary=:all: --no-deps --target eight_player_candidate_20260927/.native-test-deps -r eight_player_candidate_20260927/requirements-native-tests.txt
& 'C:\Program Files\Python312\python.exe' -X utf8 eight_player_candidate_20260927/tests/test_native_roster_receiver.py
```

檢查重點是原版與候選的查表／copy／cursor 對照、全部八份記錄、ordinal 與 network index 的不同排列、非零 cursor、碰撞查找、無效 ordinal／綁定拒絕、原記錄和邊界資料不被覆蓋、nonvolatile registers／stack 正常恢復，以及高位地址下的 RIP／rel32 重定位。拒絕測試在指定 continuation 停止，沒有假裝該處理已實作。

最新[原生候選測試報告](verification/native_roster_receiver_tests.json)記錄 11 組測試、52 次 x64 模擬執行全部通過；[獨立審查紀錄](verification/native_roster_receiver_review.zh-TW.md)列出指紋與驗證界限，[合成地址範例](verification/native_roster_receiver_synthetic.json)保存 375-byte 輸出。這些是保存指令與合成記憶體的執行結果；Windows 例外展開、真實 caller 的整合、並行回呼及多人任務仍未驗證。

## 下一個必要原生工作

`0.5.0-offline` 已加入 [property producer 與兩端共同建置](NATIVE_PROPERTY_PAIR.zh-TW.md)，並完成合成資料格式橋測試。接著需將移除壓實、分類交換及其他已知讀者接到**同一份**八格儲存，保留 entity ID、roster ordinal 與 network index 的分工；再閉合 sidecar 配置／綁定／釋放、reject dispatch、unwind 與 hook 安裝／移除。只改 producer／receiver 仍會讓其他路徑使用舊資料，不可當作原型啟用。

完整八人目標仍需平台加入、角色生成、其他固定容量子系統、同步及任務全流程驗收。此處只完成其中一段必要的原生目的地改接。
