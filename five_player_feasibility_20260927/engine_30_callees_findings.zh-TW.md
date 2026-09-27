# `+0x30/+0x18` 兩個直接下游入口

本輪只使用已保存的第二次唯讀擷取、先前入口前綴、固定 `game.dll` 捕捉與磁碟 EXE 的 PE import metadata；沒有再讀遊戲程序。新快照 SHA-256 為 `157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a`。兩段各 4,096 bytes 的保存程式碼與各自重讀版本一致，但快照並非原子。逐指令 pin、RVA 與依賴在 [engine_30_callees_evidence.json](engine_30_callees_evidence.json)，由 [engine_30_callees_analyze.py](engine_30_callees_analyze.py) 以保存資料重播。

## 第 6、7 個參數在 `0x4acde0` 的用法

前次保存的 caller `0x3494b0` 將自身入口 `ECX`、`EDX` 的低 32 bits 分別放入呼叫 `0x4acde0` 的第 6、7 個 stack argument。依 Windows x64 stack 規則，進入 `0x4acde0` 後先 `push rdi`、再 `sub rsp,0x30`，兩者在函式主體分別位於 `[rsp+0x68]`、`[rsp+0x70]`。

- 第 6 個參數：`0x4acf23` 只取其**低 16 bits** 至 `ECX`，`0x4acf2d` 執行未解析的間接呼叫，`0x4acf35` 將返回的 `AX` 寫到 16-byte local buffer 的 offset `+2`。同一 buffer 的 `+0` 是 word `2`（`0x4acf28`），`+4` 是另一未解析呼叫的 32-bit 返回值（`0x4acf4b`）；它以指標及長度 `16` 傳入 `0x4acf5b` 的未解析呼叫。這個 **family / port / address** 形狀符合 Microsoft 所定義的 [`SOCKADDR_IN` 16-byte IPv4 位址布局](https://learn.microsoft.com/en-us/windows/win32/api/ws2def/ns-ws2def-sockaddr_in)。因此第一個入口數值是 **port-like** 的有根據推論；尚未識別任何間接目標，不能把它們確定命名為 `htons` 或 `bind`。
- 第 7 個參數：`0x4ace6f` 取其低 32 bits，`0x4aceaf` 原樣寫入新初始化物件的 `+0xa8` dword。到 `0x4acf15` 時原 stack slot 已被重用作暫存值。這條入口可達控制流程沒有把此參數與常數 `4` 比較，也沒有在本函式證明 `+0xa8` 的正式意義或下游上限。

固定 `game.dll` 的一條呼叫路徑在零設定時使第一數值預設為 `0x2710`、第二數值預設為 `4`，但第一數值可被設定覆蓋；已保存快照沒有該設定實值。第二數值進入物件 `+0xa8`，**不能僅因預設為 4 就命名為玩家容量**。

本入口另在 `0x4ace3b/0x4ace47/0x4ace50` 形成 `ECX=2, EDX=2, R8D=0` 的未解析間接呼叫，返回值保存在物件 `+0xa0`。依 [Microsoft 的 `socket` 參數表](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-socket)，這組數值符合 `socket(AF_INET, SOCK_DGRAM, 0)`，即 IPv4 datagram／UDP socket 的候選形狀。隨後 `0x4ace73` 使用常數 `0x8004667e`、`0x4acf15` 使用值 `1`。間接目標沒有擷取，所以仍不能把 `0x4ace5d` 確定命名為 `socket`，也無法由此推定遊戲服務行為。

## `0x349110` 的用法

第二個直接下游函式收前者返回的物件指標作為 `RDX`。它將 `RCX+0xb8` 的 dword 當作目前數量、`RCX+0xbc` 當作目前容量、`RCX+0xc0` 當作 qword 資料指標：若 `count+1 > capacity`，以 `2*capacity+10` 的值呼叫未保存的 `0x172ae0`；然後把 `RDX` 指標寫入 `data[count]` 並增加數量。此入口本身沒有固定 `4` 上限，但這個陣列的業務身分未證明，不能稱為玩家名單。

## 控制流程與名稱缺口

從各入口追全部保存範圍內的正常直接分支，`0x4acde0` 有 106 個可達指令、`0x349110` 有 29 個；正常分支均在各自 4 KiB 範圍內，沒有在第一個 `ret` 停止探索。這不涵蓋例外路徑、間接跳轉目標或函式呼叫內容。直接呼叫 `0x5c2c40`、`0x4af960`、`0x172ae0` 位於四段已保存範圍之外；十多個間接呼叫的 runtime 指標也沒有捕捉。

磁碟 EXE 的 PE import metadata 列有 `WS2_32.dll!ntohs`、`PartyWin.dll!PartyNetworkSetCustomContext` 與 `PlayFabMultiplayerWin.dll!PFLobbySendInvite` 等名稱；它們的宣告 IAT RVA **均不等於**此入口使用的 RIP-relative 間接呼叫槽位。因此沒有足夠證據將任何已保存 call site 配對到上述名稱。這些下游片段仍無法證明平台服務可接受八人房，或第五人能進入任務。
