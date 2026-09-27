# Player-count 原生候選測試 oracle 獨立審查

本審查只讀[候選 source](../Native/player_count.py)、[測試](../tests/test_native_player_count.py)、[保存報告](native_player_count_tests.json)及固定 capture evidence；未修改 source／tests，也未重跑其他 suite、接觸遊戲程序或安裝 patch。

| 項目 | SHA-256 |
| --- | --- |
| `Native/player_count.py` | `d89b5cb7d8c6a574dbb4d1ef24346524c3a9d2cfeae36357a9bf8fd94967d8ab` |
| `tests/test_native_player_count.py` | `1de597c9788fc84394d1946c2e77a75c3d2e4271bbdef7ccee475f0e9ad30796` |
| `verification/native_player_count_tests.json` | `3915a4b1a06b6da4a10b70c385acc96dd284a0095cc9d07975c2fb292ced7e2f` |
| `roster_player_count_native_evidence.json` | `8f0fad49d9f5bc7e95ffe8735007b59c302034704707602c8d8093ad795676e3` |
| `roster_departure_callee_evidence.json` | `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0` |

報告列 7 methods、188 次 Unicorn execution、0 failure/error；直接重算其 `emulator_runs` 為 **26 次 `94C9C0` prefix**（原／候選各 13）與 **162 次完整 `94BE10` filter**（原 65／候選 97），每次 outcome 分別為 `prefix_observation`／`return`。97 次候選完整 filter 中有 86 次進入新 trampoline；另 11 次由原 `94C079` lower-bound 分支先拒絕，故不把所有候選執行誤稱為已測 trampoline。

## Oracle 覆蓋與證據

1. `test_01` 固定原 context/filter bytes SHA，驗兩個原位 patch 的預期 bytes、51-byte trampoline 解碼、所有分支目標為內部指令或原 `94C081/85`，並驗來源 bytes 被改動會拒絕生成。
2. `test_02` 真實執行保存的 `94C9C0` **入口至 `94CA3A`**，對 raw 0..9、`FFFFFFFFh` 與 tech 1／10 比較原 `[1,4]`、候選 `[1,8]` clamp；驗 tech 仍獨立、沒有 nonstack 修改與外部 stub call。這是 caller 前綴觀察，沒有走其通知或後續 15 個 `94BE10` callsite。
3. `test_03/04` 對 `1≤min≤max≤4` 的十種 profile，先驗 count 1..4 的原／候選全配對；再將候選 count 5..8 對原 count4 配對。每次先按合格與否核 hard-coded D8 輸出欄位、count、暫存索引、整張非 stack page 快照，再比較原／候選返回資料。這比僅以兩個實作互相比較有獨立 oracle。
4. `test_05` 含 max 非 4、`min5/max4` 空範圍在 count4/5/8 的保持、`FFFFFFFFh` 及 override。override 案例先實際走候選 range-fail continuation，後由原 `94C09B` bypass 的完整 filter 返回成功；aggregate 兩種分支均與原 bytes 比對。因此新的 `min≤4` 限制確實避免 min5/max4 被新政策意外接受。
5. `test_06` 在第二個 ASLR base 用 tech 1／3／10 執行完整 filter，核兩個來源表的四次實際 float 欄位讀取地址皆為 `tech−1` 對應位置；玩家數與 tech 索引沒有混用。`test_07` 覆蓋配置區域對齊／重疊與 rel32 可達區間兩端及越界拒絕。

完整 filter 執行載入原 `94BE10` 1594 bytes 與原 `177E3C0` 156 bytes；後者不設 stub，合格案例實際進入兩次，並核 RCX/RDX。四個明示 contract stub 為 `94A0A0` eligibility、`949E10` modifier、`173B8D0` allocator、`2088770` security cookie；它們核傳參與 Win64 stack 對齊、改寫 volatile GPR/XMM、寫 shadow space，再返回固定 scalar／配置值。報告的兩個 float literal `23C675C=cdcccc3d`、`23C7A74=0000af43` 已獨立從相同固定 capture 讀回吻合。

## 判定及實際界限

未找到這組測試或報告的局部阻塞缺陷。它支持 **離線原生兩處 patch 的數值與完整 filter 選集／輸出 oracle**，特別是新 `max==4 && min≤4` 政策在有效四人 profile 下的 5..8 等價，以及原 1..4、override、tech index 的保持。

`94C9C0` 僅測到 `94CA3A`，完整 filter 是另行直接呼叫；報告沒有把兩者寫成已執行的端到端 context，也沒有證明 15 個 caller callsite 的 runtime 配置。輸出 buffer 只容納一筆 synthetic template，allocator 與其餘外部 helper 採受控契約；真實 R8/R9 資產值、更多 templates、資源可用性、failure/rollback、同步／unwind／安裝與八帳號任務均仍需獨立證據。`FFFFFFFFh` 在新上界會變 8，pending D=0 的來源缺口並未由此 suite 解決。
