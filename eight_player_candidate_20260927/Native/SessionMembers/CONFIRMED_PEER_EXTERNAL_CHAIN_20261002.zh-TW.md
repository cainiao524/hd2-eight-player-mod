# Confirmed-peer 外部生命週期鏈（2026-10-02）

這份機器可讀證據把第五至第八個 peer 的外部接納鏈固定在 Steam build `25480438`：host capacity、host index allocator、host confirmed-peer sender、client receiver append，以及 player creation gate。資料來自 PID `38588` 的既有固定 RVA 只讀擷取；沒有呼叫、寫入、hook、注入或多人測試。

## 已核對的邊界

| RVA | 路徑 | 目前證據 | 八槽必須閉合的工作 |
| --- | --- | --- | --- |
| `0x108C18F` | host capacity | `4 - occupied`，transport callback 另傳 `r8d=4` | sidecar occupied/generation 與兩條 continuation |
| `0x108C3D8` | host index allocator | host `+0x100` flags 掃描比較 `<4`；另一張表有 `<4` | 分配 `0..7`、保留 hole、重連與 migration |
| `0x108C760` | host confirmed sender | `+0x20` / `+0x40`，stride `0x38`，四筆 | sender、serializer、receiver、cleanup 必須同一 owner sidecar |
| `0xB90B20` | client append | `+0xC8` count，`+0xD0` 起 stride `0x20`；第五筆到 `+0x150` | 搬移八筆儲存，並同步 remove/reset/readers |
| `0x1086460` | player creation gate | `[rdx+r8+0x163AC] >= 4` 直接拒絕 | 角色資源、component、roster、handle 和 cleanup |

host migration、host cleanup、client remove/reset 的生命週期路徑也列在 JSON 的 `required_lifecycle_paths`；它們不能由 sender-only immediate patch 取代。

## 驗證

```text
python verify_confirmed_peer_external_chain.py --artifact confirmed_peer_external_chain_20261002.json
python -m unittest -v test_confirmed_peer_external_chain.py
```

目前結果為 `passed_static_external_chain_verification`、2/2 tests；`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。這份證據只收斂 blocker，不宣稱八人可玩。
