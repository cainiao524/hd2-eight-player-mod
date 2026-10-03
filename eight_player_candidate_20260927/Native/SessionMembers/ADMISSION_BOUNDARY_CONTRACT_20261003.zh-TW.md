# 固定版本 admission call-shape 契約（2026-10-03）

此資料只重播已保存的 `host_expansion_disasm_108d9f0.json`，不啟動或存取遊戲程序，不呼叫函式，不寫入記憶體，也不安裝 hook。

## 已固定的 call shape

- `game.dll+0x3326308` 取出的介面表再取 `+0x40`。
- `0x108DDC7` 呼叫 `[r8+0x08]`，`RCX` 來自 network context `+0xB390`，`RDX` 來自 `[r12]` 的不透明 ID。
- 呼叫後寫入 `[r12+0x20] = 7`。
- `0x108DE09` 以同一 owner 與 ID 呼叫 `[r8+0x50]`。
- 隨後送出 `0xA497A2DD` 與 `0x8FE70196` 兩個 dispatcher hash。

`Native/SessionMembers/admission_boundary_contract_20261003.py` 會逐項核對 RVA、bytes、反組譯文字與來源雜湊；任何漂移都拒絕產生契約。合成測試覆蓋正常收據與 call bytes 變更拒絕。

## 尚未證明的部分

兩個間接目標的實際函式、回傳值、PeerId／network index 語義、拒絕與 cleanup、host migration、player creation 及客戶端 replication 尚未解析。因此這份契約不能產生 production hook，也不能宣稱第五至第八個玩家已加入。收據固定為 `admission_boundary_contract_20261003.json`，`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。
