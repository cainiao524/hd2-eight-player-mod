# HD2Runtime ModBuilder 公開研究（2026-10-07）

## 來源固定

- 倉庫：`https://github.com/SkyeShade/HD2Runtime-ModBuilder`
- 固定提交：`0213552c9ea52d3dbf104f9dc5ae7efea6648c38`
- 本地副本：`external_repos_20261007/HD2Runtime-ModBuilder`
- README 宣稱版本：ModBuilder 1.6.0，主要綁定 HD2Runtime SDK 0.28.1。

## 實際能力

這個專案是 Windows `.NET 10 MAUI Blazor Hybrid` 編輯器，用來從 HD2Runtime SDK metadata 建立武器、戰略配備、載具、背包、Boosters 和自訂 Lua 的 mod ZIP。它會生成帶有 expected baseline、`hd2.patch`／`hd2.transaction`／`hd2.plan`／`hd2.ensure` 與 opt-in flags 的 guarded Runtime Lua，也可以選擇接入 Mod Options Menu。它保留專案的 SDK 版本綁定，並在 export 前檢查 metadata、ownership、baseline、shared scope 與 unsupported fields。

README 明確說明此倉庫與 HD2Runtime 分離；應用程式不啟動遊戲、不部署 mod，也不存取遊戲程序，snapshot inspection 只讀取使用者選定的本地檔案。原始碼搜尋未發現 Session/Party peer admission、player-slot allocation、Player Clone creation、entity replication、host migration 或八人 lobby writer。

## 對八人 Mod 的判定

| 邊界 | 判定 |
| --- | --- |
| Mod 編輯／Lua 生成 | 可用，適合作為資料型 mod 的 authoring 工具 |
| Mod Options UI | 可作為可選 UI 輸出，但不提供容量能力 |
| Steam build `25480438` native gate | 未涵蓋；SDK 版本與遊戲 EXE fingerprint 是不同契約 |
| Session／Party／peer admission | 未提供 |
| 第 5～8 個 Player Entity 建立 | 未提供 |
| client entity replication／death／reinforcement | 未提供 |
| host migration／重連／八帳號驗收 | 未提供 |
| 目前八人候選可安裝性 | 不變，`false` |

因此本倉庫不能作為八人能力證據，也不能取代目前 `Native/OfficialPlugin` 的固定版本 ABI 探針。它可在未來 native admission/replication 完成後，協助產生獨立的武器或 Lua mod ZIP；不應把它放在第 5 人到第 8 人的網路生命週期路徑上。

## 採用與限制

- 採用：SDK 版本固定、baseline/ownership/shared scope 驗證、生成 Lua 前 fail-closed、export ZIP 保存依賴與 metadata。
- 不採用：把 GUI 的 SDK capability catalog 當成 network capacity、peer admission 或 Player Clone 證明。
- 目前八人主線仍是：取得允許的 Session/Party admission callback、authoritative network index、Player Creation/cleanup、client replication 與 host migration ABI，然後完成五至八帳號同任務驗收。
