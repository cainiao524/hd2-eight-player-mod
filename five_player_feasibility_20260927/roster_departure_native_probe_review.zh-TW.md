# 605950 原碼 departure probe v2 獨立複核

## 範圍與來源

本審查只讀固定 Steam build `25480438` capture、probe 原始碼及結果，另重跑一次 probe 至臨時輸出；未修改 probe、候選 emitter、既有證據或遊戲程序。此 probe 執行的是保存的**原四格**機器碼，沒有八格候選。

| 項目 | SHA-256 |
| --- | --- |
| [root/reader evidence](roster_departure_native_evidence.json)，`605950` 與 `606820` | `0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609` |
| [remove evidence](roster_remove_native_evidence.json)，`540A40` 與 `172F8A0` | `67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af` |
| [callee evidence](roster_departure_callee_evidence.json)，包含 `FD9C80` | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |
| [probe v2](roster_departure_native_probe_v2.py) | `961d96575dd07987cc96fc9675faf34df0d0a992aa1af6885551be2837f222a4` |
| [保存結果 v2](roster_departure_native_probe_results_v2.json) | `13c45a80d7657548d92142663dbab278f08eeffe026e32e30ba379f7e45b1874` |

直接用 `inspect_capture.Image` 重新驗證 capture report/data 身分，再讀原 RVA：`605950..605F2F` SHA `4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681`；`606820..6068E5` SHA `0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce`；`540A40..540AE0` SHA `35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8`；`172F8A0..172F9A3` SHA `d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f`；`FD9C80..FD9D33` SHA `0533fa336a0f696021412e722716c7de8ee2096439a98f7e8671a9ea44487eae`。另直接核 `23C6D70` 四 bytes 為 `00 00 80 3F`（float 1.0），與 probe 的 fixture 相同。

在 workspace 根目錄重跑時，把 `--output` 指向尚不存在的臨時 JSON。獨立執行 `py -3.12 -B five_player_feasibility_20260927/roster_departure_native_probe_v2.py --output <新檔>` 得 3 cases、6 top-level executions、2 count mismatches；輸出 SHA 與保存結果逐 byte 相同。probe 自身逐條重建五個 body，驗每條 RVA、bytes、SHA、連續邊界及完整 body hash，因此所執行的 body 可追到上述固定來源。

## 真實執行與 stub 邊界

每個 case 實際執行 `605950`，由其呼叫實際 `606820` 與實際 `FD9C80`；synthetic harness 在 root 尾跳完成後另啟動實際 `540A40`，它呼叫實際 map delete `172F8A0`。這是依既有 FDC820 callback 表先後順序構造的**兩次頂層呼叫**，probe 沒有執行 FDC820 或證明該 pending state 的真實 caller 可達性。

v1 的 fixture 以 `FFFFFFFFh` property 值配強制 null stub，不能證明真實 `FD9C80` 會如此返回；這是本次審查找到並要求修正的可達性漏洞。v2 已將 property 首 DWORD 改成 `7FFFh`，移除該 stub。三個 case 的實際 `FD9C80` trace 均恰為 `FD9C80/C84/C87/C8D/D2C/D2E/D32`；固定指令在 `FD9C87` 比較 `7FFFh`、`FD9C8D` 跳至 `FD9D2C xor EAX,EAX`，`605A6D` 讀得 RAX=0。這只證明 **7FFFh 直接 null 分支**，不把其他 key 的 map miss 當安全 null。

仍由受控 stub 代替的只有 `139C360` network notification、`94C9C0` UI notification、`60C2A0` count notification 與尾部 engine interface `+480h`。它們記錄傳入參數、只寫 Win64 shadow space、改寫 volatile GPR/XMM、保持非 stack fixture 不變；probe 在每個 stub 入口驗 counts 與所有已映射 nonstack pages 等於初始 snapshot，departure 完成後再驗全部實際 memory writes 只在 stack。`94C9C0` 的 `[1,4]` clamp、`60C2A0` 的資源 hash／數值通知及所有 callback 後續效應並**未**在 probe 執行，由獨立 callee evidence 與[有限前提](roster_departure_native_prerequisites.zh-TW.md)支撐靜態結論。

| 原四格 fixture | `T/D/P` | 移除 ordinal | UI stack 參數／`60C2A0` EDX | tail `player_count` EDX | 實際原 remove 後 D |
| --- | --- | ---: | ---: | ---: | ---: |
| dense | `1/1/0` | 0 | 0 | 1 | 0 |
| pending，另有 dense | `2/1/0` | 1 | 0 | 1 | 1 |
| pending，無 dense | `1/0/0` | 0 | `FFFFFFFFh` | 0 | 0 |

probe 查核網路 index DWORD 與指定 target ordinal 一致，確認每 case `606820`、`FD9C80`、map delete 的實際入口及其順序。原 remove 後驗 `T/D/P` 與 map ID→ordinal；三次均刪各 segment 末筆，所以原 mover 未執行。非 volatile GPR 與 XMM6..15 在兩次頂層呼叫後恢復。上述兩個 pending 差異只成立於無外部 callback 干擾的 fixture；它們不決定通知參數本來應代表何種玩家數，也不推出八格候選已可接入。

## 結論與保留邊界

v2 已修正 v1 對 `FD9C80` null 返回的未證假設；在限定 fixture 與 stub 契約下，原 root 兩個 `D−1` 消費者與後續原 remove 的 D 有兩個可重現差異，D=0 會傳 `FFFFFFFFh`。未發現 v2 在 pinned bytes、7FFFh 分支或三個結果上的局部複核缺陷。

真實通知 callback 可能改 roster、map、global S 或重入；probe 沒有執行這些函式，也沒有執行 FDC820。pending target 在真實移除 caller 是否可達、`D−1` 的產品語義、`94BE10` 對 5..8 人的有效範圍及八格 sidecar 生命週期皆未閉合。此結果應作為原碼條件式反例與後續設計約束，不作為八人安裝或遊戲內多人驗證。
