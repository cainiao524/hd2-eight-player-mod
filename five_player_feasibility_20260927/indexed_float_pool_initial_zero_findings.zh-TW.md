# 共用池的初始零值來源與重用限制

## 結論

**後續生命週期補證：** [直接建立／清理清單](indexed_float_pool_lifecycle_inventory_findings.zh-TW.md)已核對305個S的位址／次序相同，以及八筆獨立儲存的325項投影。回收推論仍以唯一所有權、有效indices與context、無重入修改為前提；本文件對初始清零的範圍限制不變。

已找到先前局部 constructor 未顯示的**外層初始清零來源**。`4EE160` 向間接介面要求 `0x7AF7628` bytes，保存回傳指標後，以 byte value 0、相同長度呼叫已核對的 byte-fill helper `208AAA0`；之後才把該指標發布至 global `3326340`。

沿下述靜態 caller / owner / manager 關係，`k=0` 時的共用池 descriptor、used count、search cursor、256 個 nodes 與 occupancy bytes 都在此清零範圍內。因此可以解釋它們**最初的零值來源**，不必推定 `142B990` 自己遺漏初始化。

本結果沒有證明這些 bytes 從配置後一直保持零值到每次 D constructor 呼叫，也沒有證明重用／重入時會重新清零。間接配置介面的實際 target、回傳指標及成功狀態未由執行期資料驗證。**不得把這條首次清零路徑當成 active pool 的可重複 reset。**

## 1. 外層物件到 D 的位址鏈

為避免與其他支線的 owner 名稱混淆，本文件以 `X` 表示 global `3326340` 指向的外層配置；`O` 才是既有 float storage 證據的 owner。

| 來源 | 已核對的指令／關係 |
|---|---|
| `4EE524` | 呼叫間接配置介面；此前 EDX=`7AF7628`。實際 API target 未捕捉。 |
| `4EE527..4EE535` | EDX=0、R8D=`7AF7628`、RCX=回傳 RAX、RBX=同一 RAX；call `208AAA0`。 |
| `4EE564` | `global3326340 = RBX = X`；所有通往此發布點的正常 CFG 路徑都經過上述清零 call。 |
| `AB5025 / AB5030 / AB5072` | 從同一 global 取 X 至 R14，以 RCX=X 呼叫 `AB4520`。此 caller 只納入從 unwind entry 到該 call 的前綴。 |
| `AB453F / AB476F / AB4772` | `AB4520` 保存 entry RCX 至 RDI，條件路徑以同一 X 呼叫 `AB8B70`；入口另有狀態／初始化旗標控制。 |
| `AB8C48 / AB8C76` | 以 `X+E49F0` 呼叫 `FDA190`，令此 interior object 為 W。 |
| `FDA352 / FDA375` | 以 `W+40` 呼叫 `551B60`，故 `O=X+E4A30`。 |
| `551B7D → 568230` | 同一 O 傳入 pointer publication 函式。 |
| `5687E4 / 5687EB` | 發布 `M=O+1F7AE8` 至 global `3326AA0`。 |
| [既有 D 來源](indexed_float_storage_findings.zh-TW.md) | `U=M+4F90+k*55A698`；`D=U+4C8260=M+4CD1F0+k*55A698`。 |

因此：

```text
O = X + E4A30
M = X + 2DC518
D = X + 7A9708 + k*55A698
P = D + 36F8
```

**k 是 manager instance ordinal，與玩家／network index 不同。** 此次逐項清零界限計算採 k=0；不能把新增第五名玩家換成 k=4，也不能從大配置仍有空間就推定存在更多有效 manager instances。

## 2. 清零涵蓋哪些池欄位

以下區間皆為相對 X 的 offset，右端不含；皆小於 `7AF7628`。

| 欄位 | 起點 | 末端 | Bytes |
|---|---:|---:|---:|
| P descriptor | `7ACE00` | `7ACE20` | 32 |
| P used count，`P+10` | `7ACE10` | `7ACE14` | 4 |
| P search cursor，`P+18` | `7ACE18` | `7ACE1C` | 4 |
| 256 個 nodes，`D+3718` | `7ACE20` | `7CD620` | 133,120 |
| occupancy bytes，`D+23F18` | `7CD620` | `7CD720` | 256 |

`7ACE20 + 256*208 = 7CD620` 再次核對了 node backing 緊接 occupancy 的布局。`142B990` 後續設定 P 的 node / occupancy pointers 及 capacity=256，並逐一初始化 nodes；它沒有在該 root 明確重設 used count、cursor 或 occupancy。新證據補的是更早的 zero-fill 來源，並未把局部 constructor 改寫成具備完整 reset 語義。

byte-fill 的語義沿用已固定雜湊的[storage 證據](indexed_float_storage_evidence.json)：相關大長度向量寫入路徑與 `208AA80` 的 REP STOSB 路徑先前已核對。本次沒有僅因參數看似 memset 就替未知 API 指派語義，也沒有執行 native helper。

## 3. 同一 owner setup 會呼叫模板建立函式

完整 `551B60` root 中，`553E30` 形成同一 `O+1F7AE8` manager 位址，`553EB4` 明確 call `1258050`。這為[上輪模板預算](indexed_float_template_budget_findings.zh-TW.md)補上靜態初始化 caller。

此 caller 證據提升了模板建立流程與該 owner 的關聯強度，但尚未觀察 live invocation、writable template 內容、後續 writer 或所有跨函式副作用。每筆11格、八筆88格仍是有前提的預算，不變成已測量的 live occupancy。

## 4. 對八人實作的具體要求

1. **沿用正在使用的 P：** 新四筆記錄的20個 S 各自 fresh-initialize，保持既有 P 的 occupancy、used count、cursor 與 active nodes。不可為了新增玩家再套用一次整池 zero-fill。
2. **配置全新的空池：** 要建立一致的 node backing / occupancy backing；初始 occupancy、used count、cursor 為零，再設正確 capacity 與 pointers。node 的型別／事件狀態初始化仍依已證 constructor 流程，不能只寫 capacity。
3. **替換或搬移舊池：** 先解決 active node 資源、全部 S indices、P aliases 及外部 pointers 的所有權／改接。直接清空舊池、留下 active S，會使占用紀錄與既有引用失去一致性。本次沒有證明任意 memcpy 遷移可行。
4. **容量預算：** 指定模板的八筆記錄為88格；保留256格仍須證明其他用途及額外暫存合計不超過168格。初始清零不能回答遊戲期間的最高占用。
5. **重用與失敗：** cleanup 後的池一致性、重新進入初始化路徑、partial allocation／同ID不重試等仍須處理，不能把首次配置的零值前提套到所有生命週期。

以上是實作約束，沒有在本次修改遊戲或產生可安裝的八人補丁。

## 5. 重播與審查範圍

- [重播程式](indexed_float_pool_initial_zero_replay.py)
- [正式證據](indexed_float_pool_initial_zero_evidence.json)
- [同來源重跑](indexed_float_pool_initial_zero_recheck.json)
- [額外原始 bytes／fragment／位址算式核對](indexed_float_pool_initial_zero_review_checks.json)

正式證據 SHA-256：`bde73bc5efde3267f812c7c2077264fd91ecec261a6054fa23b63c87b0c874e1`。

重播包含6個完整 roots、14個 unwind fragments、5,601條完整-root指令，另有 startup caller 前綴。完整正常 CFG 都可達；兩處外部 tail jumps 明列邊界。22項 register reaching-definition 檢查建立清零／發布／caller 位址鏈；另以移除 clear node 的可達性檢查，確認 clear 必經才會發布 X。Call 的 volatile / nonvolatile 行為依 Windows x64 ABI；沒有宣稱涵蓋例外路徑、損壞 stack 或不遵守 ABI 的 callees。

主代理另核對5,667條 evidence rows、5,638個不同地址的原 bytes、完整 fragment 集合與區間算式，重跑 JSON 逐 byte 相同。這是主代理另一套核對程序與人工審閱，沒有宣稱獨立代理語義審查。

```powershell
python -X utf8 five_player_feasibility_20260927/indexed_float_pool_initial_zero_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/indexed_float_pool_initial_zero_new_recheck.json
```

輸出必須是新路徑。只讀固定保存資料，沒有 process query、記憶體擷取或 native execution。第四次擷取仍待先前問題的授權。

## 仍未完成

- pool 在使用、清理、重新進入時的一致性，以及其他consumer的最高／暫時占用。
- live模板等同性、外部資源／aliases，以及新reader候選`72F780`／`730230`的caller身分。
- 其他固定四人資料結構的共同修改、實體生成、事件綁定、可安裝mod與第5–8人的實際遊戲驗證。

這輪完成初始零值來源的離線證明，**八人Mod目標仍未完成**。
