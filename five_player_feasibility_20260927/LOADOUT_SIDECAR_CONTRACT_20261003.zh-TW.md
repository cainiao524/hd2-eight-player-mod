# MenuScreenLoadout 八槽 sidecar 契約（固定 build 25480438）

`loadout_sidecar_contract_20261003.py` 把已審計的 constructor／transition／release 邊界收斂成一個可驗證的八槽資料契約。它只管理隔離的資料，不讀取程序、不解析指標、不呼叫遊戲函式，也不安裝 hook。

## 契約

- network index 固定為 `0..7`，刪除保留洞位，不壓實網路索引。
- UI slot、widget token、network index 和 generation 分開保存；forward／inverse map 必須完全一致。
- `reserve → confirm → begin_release → finish_release` 是唯一成功生命週期；資源／widget 建構被拒絕時可用 `cancel_pending` 解開 pending reservation，釋放失敗可 `abort_release` 回到 confirmed。
- 每次重新佔用同一 network index 都增加 generation；舊 token 不能清理新 record。
- 重複 index、UI slot、widget token、越界 index、generation 不一致與版本不符都 fail-closed。

這個 sidecar 是給後續 native callback 使用的 storage contract。它不代表 `0x14AA5C0`、`0x189E080`、`0x1451100`、`0x144DD70` 或 `0x18A0FD0` 已可安全 detour，也不代表 UI package、allocator 或第五人畫面已接通。

## 驗證

```powershell
& 'C:\Program Files\Python312\python.exe' -m pytest -q five_player_feasibility_20260927/test_loadout_sidecar_contract_20261003.py
```

合成報告保留 `production_patch_ready=false`、`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。
