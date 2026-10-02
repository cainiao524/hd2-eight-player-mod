# 外部 Party／PlayFab 容量邊界審計（2026-10-03）

這份紀錄針對固定 Steam build `25480438` 的本機 DLL 做只讀字串與雜湊審計。DLL 沒有載入、沒有呼叫 API、沒有存取遊戲程序、沒有寫入記憶體、沒有安裝或注入 Mod。它只回答外部服務 SDK 是否公開了可調整的網路／Lobby 容量入口，不能把這些入口當成遊戲內第五至第八名玩家已接通的證明。

## 可重跑命令

```text
python five_player_feasibility_20260927/external_party_playfab_capacity_audit_20261003.py --write --output five_player_feasibility_20260927/external_party_playfab_capacity_audit_20261003.json
```

程式只讀取：

```text
F:\Game\Steam\steamapps\common\Helldivers 2\bin\PartyWin.dll
F:\Game\Steam\steamapps\common\Helldivers 2\bin\PlayFabMultiplayerWin.dll
```

若 DLL 不存在，程式會失敗，不會以缺失檔案產生假陽性報告。

## 固定檔案指紋

| 檔案 | 大小 | SHA-256 |
| --- | ---: | --- |
| `PartyWin.dll` | 4,031,520 | `de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0` |
| `PlayFabMultiplayerWin.dll` | 1,878,048 | `95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17` |

## 實際觀察

`PartyWin.dll` 含有 `PartyNetworkGetNetworkConfiguration`、`PartyNetworkGetLocalUsers`、`PartyNetworkGetEndpoints`、`PartyNetworkCreateEndpoint`、`PartyNetworkAuthenticateLocalUser` 與 `PartyNetworkConnect` 等 API 名稱。`PlayFabMultiplayerWin.dll` 含有 `PFLobbyGetMaxMemberCount`、`PFLobbyGetMembers`、`PFLobbyAddMember`，以及 max member count 驗證和 Lobby state change 文字。

兩個外部 DLL 都沒有固定擷取中已知事件雜湊 `0x4804FCF4` 的 little-endian bytes，也沒有 ASCII `4804FCF4`。這表示目前沒有理由把 `PartyWin` 或 `PlayFabMultiplayerWin` 當作該遊戲 native receiver selector 的所在位置。

## 判讀

官方文件描述 Party network 的 user/device 設定可獨立指定，且 Windows quickstart 使用 8 名成員的範例；Lobby 也有 max member count API。這支持「外部服務 SDK 的容量層與遊戲內四槽 native admission 層是不同層級」這個判斷，但不代表遊戲實際建立了第 5 至第 8 個 peer。

目前仍未解開：

* `Session/Party → peer admission → confirmed-peer` 的遊戲 native writer；
* `player index = 4..7` 的建立與跨客戶端複製；
* 離隊、重連、房主轉移和 cleanup/unwind；
* 八個獨立帳號在同一任務的實測。

因此本紀錄的 `installable` 與 `multiplayer_verified` 都保持 `false`。下一個實作閘門仍是同一 build 的 native admission／player-creation 呼叫鏈；外部 DLL 的容量 API 不能取代它。

## 官方參考

* [PartyNetworkConfiguration](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partynetworkconfiguration)
* [Windows Party quickstart](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unified-sdk/quickstart-windows-party)
* [PartyManager.CreateNewNetwork](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork)
* [PlayFab Lobby MaxMemberCount](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/lobby/unity-multiplayer-api-reference/playfab.multiplayer/lobby/maxmembercount)
