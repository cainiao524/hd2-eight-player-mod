# `0x8E1370` 的設定值與網路建立請求

本輪只重播已保存的 EXE 載入後程式前綴及磁碟 PE 匯入表，未再次讀取程序、呼叫函式或執行連線。來源 `engine_callee_live_20260927_1.json` SHA-256 為 `157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a`；`0x8E1370` 的 4,096-byte 前綴 SHA-256 為 `0e6e20315ee6e64b80c48b78197feb4b968e68e2995c659496d3c3fe049a5fb2`。可執行的離線重播器為 [engine_f8_request_analyze.py](engine_f8_request_analyze.py)，逐條指令及分支摘要在 [engine_f8_request_evidence.json](engine_f8_request_evidence.json)。

## 已確認的參數資料流

既有[建立路徑證據](creation_path_findings.zh-TW.md)顯示零設定分支取 `4` 再加 `4`，將 `8` 當作介面 `+0xF8/+0xA0` 方法的首個整數參數。保存的[介面入口證據](interface_target_f8_findings.md)則顯示此值從 EXE `0x8C6730` 的 `ECX`，經 `ESI`／`EDX` 傳至 `0x8E1370`。在 `0x8E138F`，該函式將 `EDX` 存入 `R13D`；在 `0x8E1551`、`0x8E1559`，原值分別寫入 `[RSP+0x80]`、`[RSP+0x84]`。其後四個 dword 依序為 `1, 1, 1, 0xF`，形成連續 24-byte 結構。`0x8E15B5` 將結構起點放入 `R8`，`0x8E15CB` 透過 RIP 相對指標槽 `0x13F6DB8` 間接呼叫。可達控制流程從入口到唯一 `ret` (`0x8E1682`) 共 170 條指令，所有可達直接分支都落在保存窗口內；在這段流程中沒有對 `R13D` 的 `4` 比較、截斷或遮罩。被呼叫函式及例外路徑不在此結論範圍內。

## 與 PlayFab Party SDK 的對照

[Microsoft 的 `PartyNetworkConfiguration` 定義](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partynetworkconfiguration)正好是六個連續 32-bit 欄位：`maxUserCount, maxDeviceCount, maxUsersPerDeviceCount, maxDevicesPerUserCount, maxEndpointsPerDeviceCount, directPeerConnectivityOptions`。以上程式填入的序列是 `(8, 8, 1, 1, 1, 0xF)`，其中前兩項在其他設定分支隨傳入值改變。`0xF` 亦符合[直接連線選項的位元旗標](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/enums/partydirectpeerconnectivityoptions)之組合。

另一個局部結構起於 `[RSP+0x98]`：首欄是物件 `+0xA0` 的指標，接著是 `1`、`0`、空指標；它與官方 [`PartyInvitationConfiguration`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partyinvitationconfiguration) 的 `identifier, revocability, entityIdCount, entityIds` 佈局吻合，其中 [revocability 的 `Anyone` 數值為 `1`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/enums/partyinvitationrevocability)。

`0x8E15CB` 的九個 Win64 參數位置依序是 `RCX=manager-like object`、`RDX=localUser-like object`、`R8=&六欄設定`、`R9=0`、棧參數 `0, &邀請設定, 本物件, &本物件+0x289, 0`。此順序逐項吻合官方 [`PartyManager::CreateNewNetwork`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork) 的隱含 `this` 加八項明示參數。這是**高信心的 SDK 語義對照**，還不是此間接指標實際載入後目標的 export 綁定證明。

對 `0x8E15CB` 的立即返回值，程式以 `EAX==0` 走向 `0x8E1970`，否則寫物件狀態 `4`。已保存窗口中的 `0x8E1970` 共 109 條可達指令，三處後續間接呼叫的參數形狀分別吻合 [`PartyManager::ConnectToNetwork`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_connecttonetwork)、[`PartyNetwork::AuthenticateLocalUser`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_authenticatelocaluser) 與 [`PartyNetwork::CreateEndpoint`](https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_createendpoint)。這提供獨立的呼叫鏈佐證；三個指標槽的載入後函式值亦未擷取。

磁碟 EXE SHA-256 為 `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`。其具名匯入表有 `PartyWin.dll` 的 `PartyNetworkSetCustomContext`，但 `0x13F6DB8` 並非具名匯入 thunk。該槽位於匿名 PE section 的磁碟 raw extent，磁碟八個 bytes 為 `cbb329e16cb29b45`；僅憑這些 bytes 無法判定載入後指標。因此沒有直接觀察到 `PartyManager::CreateNewNetwork` 的實際入口。

## 對八人遊玩的邊界

這份證據支持以下**高信心推論**：預設零設定分支的 `8` 用於 PlayFab Party 網路使用者數與裝置數的上限請求；具名函式的載入後綁定仍未直接確認。資料沒有揭示遊戲為何把設定加 `4`，也沒有揭示此網路對各種遊戲流量的實際分工。官方 SDK 對 `CreateNewNetwork` 的 `0` 返回值只定義為非同步建立操作已排入；實際網路建立、裝置連接和使用者驗證仍會在後續狀態變化中成功或失敗。從現有保存資料不能推論服務接受八名真人，也不能推論八名可玩角色能進入同一任務。遊戲內另有已確認的四槽 roster 與平台成員列舉限制，見[總報告](REPORT.zh-TW.md)。
