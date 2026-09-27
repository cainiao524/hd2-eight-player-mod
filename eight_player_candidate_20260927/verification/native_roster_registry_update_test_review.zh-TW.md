# Registry 更新候選：測試 oracle 獨立審查

## 固定版本與計數

本審查只讀[測試原始碼](../tests/test_native_roster_registry_update.py)及[正式測試報告](native_roster_registry_update_tests.json)，並對照[候選原始碼](../Native/roster_registry_update.py)、[固定 evidence](../../five_player_feasibility_20260927/roster_registry_update_native_evidence.json)和[契約說明](../NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)。未重新執行測試、舊套件或遊戲程式。

| 物件 | SHA-256 |
| --- | --- |
| 候選 `Native/roster_registry_update.py` | `1e97c7e52c6d723fe43824c599cfc27871650dea3fe4357f9fcf14dfaa2edd01` |
| 測試 `tests/test_native_roster_registry_update.py` | `5d9bc2c41def4b85191a062b61c47f6d3dae9a378796839ec16c324986df3e4d` |
| 報告 `verification/native_roster_registry_update_tests.json` | `68769e53dc8cfe4d74e78d3745f68327a72e262c9e017c43309072321f998890` |
| source evidence | `7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1` |

正式報告為 **8 個方法、87 次頂層 Unicorn x64 執行、0 failure／0 error**。逐列重算 `emulator_runs`：原碼 root return 8、原碼 helper return 4；候選 root return 32／reject 20、候選 helper return 17／reject 6。原碼合計 12、候選合計 75，與 `execution_counts` 相符。內層真 `FD9BA0` 入口 114 次、原碼 root 進 `606520` 1 次、候選 root 進 clone 7 次，是上述頂層執行內的事件，沒有再加到 87。

## Oracle 實際核對範圍

- `Fixture` 在 synthetic S、B、registry、entity、context map、外部物件與 stack 建立可重現狀態。原四格完整 body 與候選四格分別執行後，逐組比較四陣列結果；另以候選覆蓋 tag `69h` 八個 ordinal、原／候選 `606520`、tag `73h` 的既存 buffer 與 fallback。候選八格執行的 count 與 map 是合成有效狀態，並非原遊戲已發布八格資源的證明。
- 成功路徑以**所有非 stack pages** 與獨立列出的預期變更比對，包含 untouched records、S count、map、primary 與 canary；另檢 Win64 nonvolatile GPR／XMM6–15 及返回 RSP。tag `69h` 的 aux `==2` 留原值／其他值寫 1、entity bit 0 控制 property flag 清除、首個重複關聯 ID 命中，以及 D 之外 pending 不掃描，均有獨立案例。
- 六個 root 及兩個 helper 陣列 patch 先核 emitted bytes 與指令邊界，再以實際指令 RIP 檢查各次 property traversal、pointer、aux、property flag 的地址、寬度與條件出現；候選執行中另斷言未讀原 S 的 inline 四陣列範圍。這同時核 LEA 衍生的 property pointer，不只檢查直接 memory operand。
- `FD9BA0` 用保存的 220-byte 真機器碼執行，核一般 context 命中與 `7FFFh` 預設轉換；`606520` 亦用原碼或候選完整 body 執行，核它略過 `7FFFh`、只掃 D、保留 OUT pointer，並能在 explicit RCX=S 與 global S 不同時獨立讀取。兩者不同的 sentinel 語義未被 test stub 混同。
- root reason 1–9 與 helper 適用的 reason 1／3／4、tag `73h` 呼叫前 precheck、空／錯 map ordinal 及容量、null entity、count 順序、先前 tag `2Eh` 效果在後續拒絕後仍存在，均有受控案例。reject 路徑檢 RSP、nonvolatile、R10D；root 檢原輸入 ECX，helper 檢 RCX/RDX/R8、OUT 與零 stack／非 stack 寫。兩個 reject rel32 可達邊界與越界拒絕亦有檢查。
- `build_bundle` 只作離線建置與有限區域重疊核對，包含十五個 roster 函式及既有 player-count 計畫；舊函式在此測試中**僅 build，沒有重跑舊套件**。

## 界限與結論

tag `2Eh` 的先前 marker、`FD9AF0` 轉換、tag `73h` 的 `1731A60`、兩個 indirect virtual call 是明示 ABI／順序／副作用契約替身；測試實際執行的外部 leaf 為 `FD9BA0`。替身會檢參數、call stack 對齊與 shadow space，並破壞 Win64 volatile GPR／XMM0–5，但不模擬真實資源失敗、回呼重入或其他隱藏狀態。tag `73h` fallback 保留的 opaque stack bytes 只核原指令產出的位元組，未證其真實所有權或初始化契約。

**未發現這份固定測試／報告的局部 oracle 或計數缺陷。** 結論限於 synthetic fixture 的完整原碼／候選 x64 執行與明示外部契約；未證 B 的配置、初始化／遷移／發布／清理、context 任意無效 map、hook／unwind／reject continuation、真實 callback、遊戲執行或五至八帳號同場驗收。這些界限與[候選契約](../NATIVE_ROSTER_REGISTRY_UPDATE.zh-TW.md)一致。
