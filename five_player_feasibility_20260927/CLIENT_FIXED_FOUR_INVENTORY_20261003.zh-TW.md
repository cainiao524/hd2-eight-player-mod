# 客戶端 confirmed-peer 固定四槽稽核（2026-10-03）

這份稽核把固定版本 `25480438` 的客戶端 confirmed-peer 物件整理成可重播的離線契約。資料只來自已保存的 `client_expansion_inventory_v2.json`、`protocol_client_layout_scan_extended.json` 和 `client_expansion_index_scan.json`，沒有開啟遊戲程序、讀寫記憶體、注入或產生 patch。

## 已固定的 reader / writer

客戶端物件有五組容量為 4 的欄位：

| count | base | stride | 用途 |
| --- | --- | ---: | --- |
| `+0x10` | `+0x18` | 8 | 鄰接指標陣列 |
| `+0x38` | `+0x40` | 16 | 鄰接記錄陣列 |
| `+0x80` | `+0x88` | 16 | 鄰接記錄陣列 |
| `+0xC8` | `+0xD0` | 32 | confirmed-peer 主記錄，玩家索引欄位在記錄 `+0x14` |
| 無 | `+0x150` | 16 | peer-keyed 搜尋區，觀察到結尾 `+0x190` |

固定 literal `4` 的兩個直接 guard 也已保留：移除流程 `0x1087730: cmp eax, 4`，以及 peer-keyed 搜尋 `0x1084F83: cmp edx, 4`。主記錄的 append、remove/neighbor compaction、兩條 reset、kicked 路徑與 host migration handoff 都有保存的 RVA 與指令雜湊。

## 不能從這份稽核推出的內容

欄位偏移和固定四槽邊界不等於 `+0x14` 就是可用的 network index，也不等於第五至第八名可被建立。仍缺少 client callback/cleanup ABI、資源生命週期、host migration 所有分支的收束、以及實機的第 5～8 名接收與任務流程證據。因此 receipt 明確保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。

執行：

```text
python -B test_client_fixed_four_inventory_20261003.py
```
