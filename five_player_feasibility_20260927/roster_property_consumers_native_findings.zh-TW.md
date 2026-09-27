# Roster property sidecar：有限原生修改清單

## 本輪決策與停止條件

成品需求是讓八筆 roster property 在建立、接收、移動、分類、移除與讀取時仍對應同一 entity。固定物件記為 `S=owner+EA0818`，原 property 為 `S+3A8 + ordinal*20h`，sidecar 起點記為 `B`。八筆需 `100h` bytes；原四筆恰到下一 owner 成員 `S+428`，不能直接延長。

本輪只沿既有 lifecycle、dispatch、index usage、property apply、player roster 證據，並接其直接依賴的 producer binding／receiver 證據。有限清單共 **21 個 roots、56 個必要存取或地址計算標記**，已核原 bytes 與來源身分。沒有全 capture 重掃、沒有擴展 callee 樹。

實作決策是讓 property 的直接存取、衍生指標與本地暫存副本都使用同一綁定 B，保留原 S 給 map、count 與其他三組陣列。下列清單固定後即停止；它是已知必要修改集合，**不是全域 aliases 已閉合的聲明**。

## 1. 身分與資料契約

- Owner 以 `5565EF/5565F9` 建立 `owner+EA0818`，`568EC8/568ECF` 發布同一位置至 global `3326468`；`B27560` 註冊同一物件到 tag `69` registry。
- `B54E00` 必須保留 registry 路徑：`B54E58/B54E5B` 檢查 tag，`B55003` 取得同 table `+10F8` 的 S。只替換 roster global 不能改到這個保留指標。
- `57E00F/57E01C` 是 owner 直接取 S 並呼叫壓實的已知來源。
- Property 第四 DWORD `+C` 才是 network index；整筆的 roster ordinal 來自 entity ID map，可因搬移而改變。其他七個欄位也必須跟著同一 entity。
- JSON 對每個 root 列出**全部已保存 chained unwind fragments 的邊界與 SHA**。這表示捕捉中的程式範圍已識別；巨型 roots 的其他分支、資料表或任意 callee 沒有因此獲得完整語義審查。

## 2. Producer、receiver、搬移與分類

| Root／已保存末端，不含 | 必改 property 位置 | 地址／指標處理 | 原副作用與界限 |
|---|---|---|---|
| `60C640..60C882` | `C6F2、C720、C74C、C77D、C7A7、C7D3、C807、C82F`（共同前綴 `60`） | RBP=S、RBX=ordinal×20h；第七欄先經 `60C7FF/60C803` 形成衍生 offset，不能只找 literal `3A8..3C4` | 原 payload 配置、八個 descriptor 與 count 更新、network-index leaf 都需保留；拒絕應在 allocator 前。完整 producer 實作由本輪另一分支處理 |
| `60C890..60C9BF` | `60C938/946/954/962/970/97E/98C/9A2` | R11 為 S；八個 store 共同改接；保留 map、payload 與 cursor | 無 callee；map miss／payload 長度及 interior reject 仍需整合契約 |
| `60C410..60C5BE` | `60C51F/528/531/53A` | RBX=S、R10=來源×20h、R9=目的×20h；只改 property 的四個 memory operands | 全 root 無 call；同時搬其他三組並修 map，不能把 RBX 永久改成 B |
| `60CC70..60CE76` | `60CD90/99/DA1/DAA`；另 `60CE24→60C410` | Inline copy 與 shared mover 都須使用 B；RBX 仍是 S | 維護 dense／tracked／prefix、map；不能只修 shared mover 而漏 inline copy |
| `60CF50..60D2F6` | `60D19F/1AA/1B6/1BF/1C7/1D0/1DB/1E8` | RBP=S；兩個 ordinal offset 在 RDI/R15；RAX 為獨立暫存 buffer | 移入方向將目的 70h state 清零；兩笔 map 更新、`+88` 增加，不能抽象成完全對稱 swap |
| `60D300..60D760` | `60D61A/625/631/639/641/649/654/660` | RBP=S；RDI/RSI 為兩個 ordinal offset；RAX 暫存 buffer | 完整交換其他三組、修兩笔 map、`+88` 減少；通知及 entity bit 清除有原順序 |

### 分類 swap 的暫存資源不可遺漏

這兩個 property swap 不是只用現成 stack bytes。原碼先以 `173B6F0` 建立暫存上下文，再以 `173B8D0(size=20h, alignment=4)` 取得 RAX 指向的暫存 record，交換後呼叫兩次 `173BC20`：

- 移入：`60D17A → 60D18D → property copy → 60D1F1/60D1FB`。
- 移出：`60D5F5 → 60D608 → property copy → 60D668/60D672`。

本輪只固定呼叫、參數與 copy 順序，沒有展開這些 helper 的資源管理內部。不能把暫存 buffer 誤當 S 的別名，或為 sidecar 改接移除原資源協定。

## 3. 插入與移除的必要配套

下列完整 roots 沒有直接 `3A8..3C7` property operands；仍不可忽略它們的 count／map 與 shared move：

| Root／末端，不含 | 原生配套 |
|---|---|
| `60CA80..60CB9F` | RDX=entity、R8=flags，四筆 guard；`60CAC9→60C410`；初始化 70h／38h |
| `60CBA0..60CC6B` | RDX=entity，四筆 guard；初始化 70h／38h；property 由後續階段建立 |
| `540850..54091E` | RCX=entity，四筆 guard；另一套 ABI 的初始化版本 |
| `540920..540A3E` | 已登錄 component 239 插入；RCX=entity、RDX=flags；`540968→60C410` |
| `60CEA0..60CF4C` | Map 刪除、tracked／dense 更新；`60CF0E/60CF3A→60C410` |
| `540A40..540AE0` | 已知實際移除回呼；`540AA4` call、`540AD5` tail-jump 至 `60C410` |

「沒有直接 property operand」只適用這些完整本地 roots，不能推出所有 callees 不會讀寫。插入的其他三個平行陣列和四筆 guard 仍須擴充；property sidecar 不能獨自使它們支援八人。也沒有從缺少 property 清零 store 推定移除後所有 bytes 已失效或可立即釋放。

## 4. 已證同來源的 readers／writer

| 完整 root／保存末端，不含 | 指令／改接 | 必須保留的行為 |
|---|---|---|
| `605950..605F2F` | `605A5B` 讀 B+ordinal×20h 的第一 DWORD | 這是關聯 entity ID；保留實際 roster 移除前的 state 處理、解析與通知 |
| `B54E00..B55169` | `B5501C` 形成 RDI；`B55030` 經 RDI 讀；`B5504A` 增 20h；另 `B550FB` 修改 B+ordinal×20h+4 | R14 繼續是 registry S；關聯 entity 查找、指標與另一組 38h 狀態仍用各自原來源 |
| `FFD8C0..FFE579` | `FFE3FF`：B+ordinal×20h+C | Network index 寫入 tag DA 的 90h 記錄；該下游另有已證四筆容量衝突 |
| `ACA400..ACABCE` | `ACA58B`：B+C，固定第一筆 | 保留第一筆語義及 `ACF1F0` 有界預設路徑 |
| `12A98D0..12AA189` | `12A9C80`：B+ordinal×20h+C | 原 map lookup 與 `ACF420` 狀態操作；其 index≥4 回 false 不是帳號加入拒絕證據 |
| `1277920..1277F7B` | `1277A06`：B+ordinal×20h+C | Sentinel 與 32-bit mask test；bits 4–7 寬度足夠，mask producer 仍另有前提 |
| `606AD0..606B75` | `606B6B`：B+ordinal×20h+C | Map 缺項回 FFFFFFFF；純量 getter 不需四人 clamp |
| `725160..72B8E0` | `7275D6/7275E1/7275EA`：B+ordinal×20h+C／1C／18 | Network index 與兩個 float 一起改接，保留向 `14335F0` 的參數；該玩家元件需獨立擴容 |
| `6054F0..605947` | `605760`：B+ordinal×20h+C | 原四列 palette 的有界 fallback 與獨立 `player_count` 通知 |

這些是已證 block 的 field 改接。對大型 root，沒有宣稱表中單一欄位即涵蓋整個函式的全部可能 S aliases。

## 5. 下一個最小實作切點：`60C410` property copy

完整 body 為 **430 bytes、78 指令、3 個 chained fragments**，SHA 與完整 CFG 收錄於 JSON。四條 property 指令形成 `[60C51F,60C543)` 的直線段；沒有配置／資源 callee，適合下一個離線 native emitter。

入口 ABI：`RCX=S、EDX=目的 ordinal、R8D=來源 ordinal`；相等即直接返回。Property 段按順序複製來源前 16 bytes 至目的、來源後 16 bytes 至目的。可以使用經驗證的 B 改寫這四條的基址，保留其餘陣列與 hash 的原 S。

**拒絕檢查必須在第一個平行資料寫入 `60C440` 前完成。** 若只在 `60C51F` 才因 binding／ordinal 無效拒絕，其他三組已被部分搬移。下一個 emitter 應先驗 binding、兩個 ordinal 與整合契約，並保持 same-ordinal 行為、copy 順序、map 修正和非 volatile registers。

此切點不代表八格整體 mover 已可執行：其他三組仍需有八格儲存，map 必須有效，且 sidecar 的配置／重建／卸載、併發、clone unwind／安裝／失敗續行都需整合。有限清單已足以開始局部 emitter；本輪不再擴搜。

## 6. 核對與重跑

- [機器可讀清單](roster_property_consumers_native_inventory.json) 與[同來源重跑](roster_property_consumers_native_recheck.json) 逐 byte 相同。
- SHA-256：`0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2`。
- [重播程式](roster_property_consumers_native_replay.py) 固定 7 份前序 artifact SHA，重新比對 1,600 條唯一原指令 rows；另核本清單的必要指令、完整 roots 的保存邊界／SHA、shared-move edges 及 `60C410` 正常 CFG。
- 有限掃描只用於所列六個插入／移除 roots 的直接 operand，以及小型 mover 的完整局部。沒有重做全 capture xref／field scan。
- 主代理逐讀有限清單及重播，另從固定 capture 核對輸出的 178 條 rows／170 個不同地址、59 個 fragments 及前序指紋；[核對紀錄](roster_property_consumers_native_review_checks.json)保留此範圍。它不是對所有大型 roots 或全域 aliases 的重新語義審查。Producer 地址敘述中的 EAX 已更正為原指令 RAX，再重跑正式清單。

```powershell
python -X utf8 five_player_feasibility_20260927/roster_property_consumers_native_replay.py --evidence 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' --output five_player_feasibility_20260927/roster_property_consumers_native_local_recheck.json
```

輸出路徑需尚不存在。本輪未改既有正式證據、候選原始碼或 manifest，未查詢／操作遊戲程序。此清單不證明全域所有權閉合、實際 sidecar 儲存已配置或八人任務可用。
