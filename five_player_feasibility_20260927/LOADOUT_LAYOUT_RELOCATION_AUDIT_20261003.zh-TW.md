# MenuScreenLoadout 八槽布局搬移審計（2026-10-03）

這份審計只重播固定 build `25480438` 已保存的 `index_slot_mapping_evidence_v2.json`。它不讀取遊戲程序、不呼叫函式、不寫入、不產生可安裝 patch，也不把畫面證據當作多人成功。

## 已核對的四槽結構

`MenuScreenLoadout`（tag `E5`）同時擁有多組彼此獨立的四項資料：

- network-index 記錄：`+0x10`，步幅 `0x9F0`，結束於 `+0x27D0`；
- forward map：`+0x27D8..+0x27E7`；
- inverse map：`+0x27E8..+0x27F7`；
- 下一個旗標欄位從 `+0x27F8` 開始；
- 大型 UI widget：`+0x53A78`，步幅 `0x1EE18`，四項後的下一個物件從 `+0xCF2D8` 開始；
- 建構配置大小參數：`0x2739D0`。

審計也重新核對建構的 `mov edi,4`、network index／roster ordinal 的 `<4` 分支、四項釋放迴圈、transition 迴圈與 `0x9F0` 記錄的 `<4` 分支。

## 為何不能直接把 4 改成 8

若把記錄擴成八項，`+0x10 + 8*0x9F0 = +0x4F90`，因此原本的 map 區域已被記錄覆蓋，兩張 map 必須搬到新位置。若把 widget 迴圈擴成八次，結束位址為 `+0x14AB38`，會越過原本下一個物件 `+0xCF2D8`，重疊 **0x7B860 bytes**。在維持相鄰物件相對關係的內聯方案中，配置大小至少要由 `0x2739D0` 增至 `0x2EF230`；若不搬動整個物件，就必須使用明確的 sidecar 指標與版本化 ABI。

因此第五至第八名至少需要同時處理：

1. 記錄、雙向 map、旗標及大型 widget 的新布局；
2. 建構、初始化、本地槽位、名冊更新、事件填表、清除、transition 和 destructor；
3. 所有 indirect callback、封包／資源生命週期及重新加入時的重建；
4. network index、UI slot 與 gameplay roster ordinal 的獨立映射。

任何單一 `<4` 或 `mov ...,4` 的替換都不符合這個契約。`loadout_layout_relocation_audit_20261003.json` 的固定檢查全部通過，但 `production_patch_ready=false`、`installable=false`、`multiplayer_verified=false`、`runtime_verified=false` 保持不變。

## 重播

```powershell
& 'C:\Program Files\Python312\python.exe' five_player_feasibility_20260927/audit_loadout_layout_20261003.py `
  --output five_player_feasibility_20260927/loadout_layout_relocation_audit_20261003.json
& 'C:\Program Files\Python312\python.exe' -m pytest -q five_player_feasibility_20260927/test_loadout_layout_20261003.py
```

來源 `index_slot_mapping_evidence_v2.json` 的 capture identity、report/data 固定雜湊均由 verifier 核對。下一步是取得完整 loadout 物件的讀寫／destructor／callback ABI，並在 confirmed-peer 與 player creation 實際可達後，先驗證第五人再逐級推進；此審計本身不提供遊戲安裝出口。
