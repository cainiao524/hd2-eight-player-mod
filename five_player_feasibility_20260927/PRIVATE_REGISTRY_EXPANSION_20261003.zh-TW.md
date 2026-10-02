# 接收端私有記憶體擴大掃描（固定版 25480438）

本輪在已授權的固定版本程序上只讀重播接收端註冊表搜尋。掃描工具新增 `--limit-mib` 與 `--max-read-mib` 參數，保留原本 128 MiB 預設值，並以 512 MiB 上限重跑一次。掃描只查詢可讀的 `MEM_PRIVATE` 頁面，不呼叫遊戲函式、不跟隨指標、不寫入程序、不安裝或注入 Mod。

## 結果

- 128 MiB 基線：295 個私有區域、32,768 頁、134,217,728 bytes，目標命中 0。
- 512 MiB 重播：1,481 個私有區域、131,072 頁、536,870,912 bytes，目標命中 0。
- 1 GiB 重播：2,113 個私有區域、262,144 頁、1,073,741,824 bytes，目標命中 0；輸出為 `live_private_registry_20261003_1024m.json`，驗證為 `private_registry_expansion_verification_20261003_1024m.json`。
- 查找項目包括 `BABA80` receiver、`B90B20` confirmed-peer insert、`1093590` consumer、`10937A0` state update 及 `0x4804FCF4` 事件 hash。
- 兩次 capture 都保持固定 build identity 與 read-only flags；沒有生成 stable hit page。

## 邊界

這是負面證據，不能證明程序不存在更高位址、非私有配置或尚未載入的 receive registry。即使找到指標或 hash，也必須再恢復 owner、lookup、呼叫慣例、cleanup 和 exception unwind，才能成為可回滾 hook。因而 `receiver_registry_resolved=false`、`installable=false`、`multiplayer_verified=false` 仍是正式結論。

機器驗證輸出：`private_registry_expansion_verification_20261003.json`。
