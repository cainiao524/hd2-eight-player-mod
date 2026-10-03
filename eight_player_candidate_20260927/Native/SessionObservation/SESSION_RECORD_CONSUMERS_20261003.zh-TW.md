# GameSession opaque record consumers（2026-10-03）

這份合約只重播倉庫裡已保存的 `helldivers2.exe` vtable disassembly，以及選定的 `game.dll` protocol/join 文字與邊界資料。它不啟動遊戲、不呼叫任何擷取的函式、不寫入程序記憶體，也不把 ordinal 或 qword token 命名成 PeerId、玩家索引或隊伍位置。

## 能從保存指令直接證明的 consumers

- `0x292BE0`（vtable slot `0x70`）讀 session `+0x138`，只記錄為 opaque count field。
- `0x292BF2–0x292C00`（slot `0x78` 的 indexed getter）先以 `index * 3 * 2` 形成 `index * 0x30`，再讀 session `+0x140` 的 table entry。這個 getter 本身沒有可見的 count check；呼叫端必須先驗證 index 與生命週期。
- `0x292C4A`（slot `0x88` 的 predicate）比較 table entry 起始 qword，即 `record + 0x00`，與 session `+0x20` 的 opaque self key。
- `0x292CF7–0x292D07` 在相同的 count bounded loop 中比較 `record + 0x00`，命中後讀 `record + 0x29`。
- `0x292D20` 是另一個 indexed byte read，使用相同的 `index * 0x30` table addressing，再讀 `record + 0x29`；它同樣沒有可見的 bound check。

這些 site 建立的是 table、stride、token 和 byte 的讀取關係。它們沒有提供 token 的外部型別、ordinal 的玩家意義、byte 的同步狀態或 owner 的 host 意義。

## 與 protocol/join 保存資料的關係

選定的 `protocol_slot_consumers.json` 保存了 `0x108DDD0` 的字串 `Adding %llx to game session with player index %u`；`join_handler_followup.json` 則描述 `game.dll` host peer 的四筆 `+0x38` record、四個 index byte 與另一個四筆 pending path。對這兩份選定資料搜尋 `0x292BE0/0x292BF0/0x292C20/0x292CC0` 沒有直接文字 xref，因此合約把兩個模組當作不同證據域，未宣稱它們互相 alias 或已綁定呼叫。這是選定保存檔的 bounded negative result，不是整個映像的 xref 完整證明。

## Fail-closed 邊界與測試

```powershell
python -B -m unittest test_ep_session_record_consumer_contract.py
python -B ep_session_record_consumer_contract.py --output session_record_consumer_receipt_20261003.json
```

合約會拒絕版本漂移、指令 bytes/asm 漂移、缺少任一 record read site，以及 protocol/join 保存檔出現選定 session target RVA。輸出 receipt 明確保留 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`，並列出尚未綁定的 constructor、mutation、destructor、callback、client replication 與 whole-image xrefs。
