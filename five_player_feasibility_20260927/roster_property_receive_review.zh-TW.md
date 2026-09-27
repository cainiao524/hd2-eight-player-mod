# Roster property receiver：獨立離線審查

日期：2026-09-27。審查者：`spawn_interface_probe` 子代理。本次只檢查既有固定 capture 與指定產物，沒有執行 live query/read、probe、遊戲修改或多人測試。

## 結論

**未發現需要修正的核心結論。** `60C890` 的第四個 DWORD 是原樣 32-bit copy，未經 `<4` 判斷、mask、clamp 或窄化。目的 record 由入口 entity ID 查 map 後取得的 ordinal 決定，沒有使用收到的 network index 選 record。

原文也正確保留兩項關鍵前提：已有有效 entity→ordinal，以及足够的有效 payload。此 callee 沒有替呼叫者檢查這些條件，不能將「欄位能保留 4–7」延伸成「第五位玩家可以安全建立或接收更新」。

## 核對範圍與來源

- `roster_property_receive_replay.py`
- `roster_property_receive_evidence.json`，SHA-256：`bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10`
- `roster_property_receive_findings.zh-TW.md`

重新以 `inspect_capture.Image` 驗證原 capture report/data 的固定 SHA 及 capture identity，然後獨立比對：

- **303 bytes／72 條 receiver 指令**的 RVA、bytes、反組譯文字。
- 四個 unwind fragments 的起訖、unwind RVA、所屬 root 與片段 SHA。
- **42 條**額外 caller／owner／producer pins 的 bytes 與指令邊界。
- 正常 CFG 的全部邊、八個 DWORD 目的欄位，以及缺少 entity ID 的路徑是否仍到達 store。

這些比較均通過。此審查沒有將前置兩份文件所含的 690 筆檢查記錄再次全部重播；其 SHA 與逐筆重核是被審 replay 本身的工作。本次獨立審查聚焦新 receiver、caller 和題目指定的資料流。

## 1. 完整函式與正常 CFG

四段 unwind fragments 連續涵蓋 `[60C890,60C9BF)`，無遗漏分段。以原始反組譯重新建出的 CFG 與 JSON 完全一致：

- 72 個節點皆從入口在正常控制流圖上可達。
- 每條跳轉、條件分支及 fallthrough 均落在已證明的指令邊界。
- 函式沒有 call、間接跳轉或跳到此集合外的正常邊。
- 正常返回在 `60C9AC`；查表命中尾段 `60C9B5/60C9BA` 會跳回前方的恢復／寫入路徑。

這是正常 CFG 的靜態可達性，並非每個節點已被 runtime 執行，也不對例外處理或記憶體 fault 作成功保證。

## 2. Record 是由 entity ID 與 map ordinal 定位

入口 EDX 保留待查 key。入口指標分別保存為：R11=roster S、RBP=payload buffer、R14=cursor pointer。查表使用：

```text
S+D0  map entries pointer
S+D8  capacity
S+DC  sentinel / invalid-key value
S+E0  multiplier
```

命中時 `60C9B5` 從 `[RBX+R8*8+4]` 取得 map value 到 EAX；`60C92B` 以 `mov R8D,EAX` 保留該 ordinal，`60C92E` 左移 5 得 record byte offset。真正 payload 第四欄的讀取在更後方 `60C95C`，所以它不能是前面已完成的 record 選擇依據。

caller 的 `BD13A2..BD13B3` 連續指令與所述 ABI 相符：RCX=`owner+EA0818`，EDX 來自 `[RBP+28]`，R8=payload，R9=`&cursor`。既有 owner/global 發布 pins 足以將此 roster 與 global3326468 接合。這條直接 owner 位移別名確實需要在重定位設計中納入。

至於 `[RBP+28]` 的產生與 upstream selector，本文明確交由上游支線分析，沒有僅憑暫存欄位位置就保證 entity ID 有效。此限制正確。

## 3. 第四欄完整保留 32 bits

關鍵三條連續指令已從原 capture 核對：

```text
60C95C  mov ECX, dword ptr [RDX+RBP]
60C95F  add EDX,4
60C962  mov dword ptr [R8+R11+3B4],ECX
```

唯一介於 load 與 store 的指令修改 EDX，即 buffer offset；它不修改 ECX。因此收到的第四個 DWORD 在此保留所有 32 bits。`4`、`7` 或其他位元型態在這兩條資料 MOV 之間都不會被轉型或截斷。

八個 record store 位移依序為 `3A8,3AC,3B0,3B4,3B8,3BC,3C0,3C4`，寬度皆 4 bytes。原文的 payload 相對位置 `0,4,8,C,10,14,18,1C` 與實際 cursor 遞增一致。

`60C994` 先將最後 DWORD 讀入 ECX；`60C99A` 恢復 RBP 後才於 `60C9A2` store。這個先後順序不破壞最後欄資料：payload 已在恢復 RBP 前完成讀取，而目的 base 仍是 R11。

尾部將 cursor 寫成入口 cursor 加 `20`，使用 32-bit 算術。原文限定在有效、不溢位的正常 buffer 範圍，沒有把 uint32 wrap 當作任意大 cursor 的安全消耗規則。

## 4. 缺少 entity ID 並沒有安全早返

兩種失敗路徑都仍能到达第一個 store `60C938`：

1. 入口 key 與全域 invalid-entity sentinel 相等：`60C8A8` 設 EAX=`FFFFFFFF`，直接跳到 `60C928`。
2. Map capacity 為零、走遍仍無 key，或遇到不匹配的 sentinel：到 `60C914` 設相同失敗值，再繼續寫入。

一個容易誤讀但原文没有寫錯的細節：`mov R8D,EAX` 會將 `FFFFFFFF` **零延伸**至 R8，再以 64-bit shift 左移 5。其 offset 為 `1FFFFFFFE0`，不是負的 `-20`，也不是「寫到 record 前一格」。這進一步說明為何不能把缺項當成 callee 會拒絕的正常情況。

此函式也没有 buffer length 參數或八次 load 前的長度檢查，沒有驗證 map value 小於 record count 或 4。原文把既有有效映射、目的記錄空間及有效輸入 buffer 列為前提，判斷適當。

## 5. 結論應保持的界線

這個 receiver 的 scalar 寬度足以保存 network index 4–7，**但 record ordinal 4–7 的儲存是否合法，是另一個布局問題**。重新配置須同步調整八個 store、map／ordinal 不變條件、cursor 消耗，以及直接 owner 別名。

此頁没有將 producer descriptor 當成已證實線上封包格式，也没有宣稱所有獨立 property 更新都必然經過此函式。固定 direct-call 搜尋只證明被捕捉且有 unwind 邊界的 `BD13B3`，沒有排除間接或未捕捉入口。

綜合上述，本次審查 **無待修正事項**；通過的是固定版本的離線資料流與邊界敘述，不是 runtime 或八人成功驗證。
