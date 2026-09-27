# Roster remove 原生測試獨立核對

2026-09-27；範圍僅限 `tests/test_native_roster_remove.py` 的 oracle 與 `verification/native_roster_remove_tests.json`，未修改候選來源、測試或報告，也未重新執行廣泛測試。

## 結論

最後版本未發現阻擋性的局部測試或報告缺陷。報告為 9 個方法、2,293 次 Unicorn x64 模擬執行，0 failure、0 error；其中候選 2,141 次、原四格 baseline 150 次、原版已知反例 2 次。三類相加等於 2,293，與 `emulator_runs` 長度一致。報告中的 7 份 Native source 與 5 份固定 evidence 雜湊均與現有檔案相符，測試檔雜湊也相符。這些是離線合成狀態證據，不代表可安裝、真實遊戲生命週期或多人執行已驗證。

## 核對的 oracle

- `success()` 從輸入 partition 和被刪 ordinal 獨立求出 survivor 的順序，驗證 `T/D/P`、唯一 ID 集合、四組完整記錄 bytes、保留尾端資料及非 stack 頁面的預期變化；`map_is_bijection()` 另驗每個存活 key 對應 ordinal 唯一且依指定 multiplier 從 hash home 線性探測可達。全 `T=1..8`、`P<=D<=T`、每個被刪 ordinal、兩個 body 均納入。
- `test_04` 對原版 `D<T` 的 dense 刪除實際執行反例，再要求候選修復結果符合完整 survivor oracle；包含 `Dnew=0`、仍有 pending 的情形。
- `rejected()` 要求 reject reason、非 stack 所有頁面逐 byte 不變、沒有 helper call，且全部執行期寫入位址落在 stack；不存在 key 的滿表及非滿表案例均受此約束，故包含 map delete 之前拒絕的檢查。
- 原版四格只在 `D==T` 或刪除 ordinal `>=D` 的 preserving 範圍作 baseline；registered body 的每個此類 case 另與候選配對比較 `RAX`，反例亦比較。legacy body 的 `EAX` 與原輸入 entity 的 return word 比較。
- 串接測試實際執行 append、remove、再 append 與 receiver。receiver 選用先前由 ordinal 7 移至 ordinal 2 的 key 67，驗證 property 寫入新 slot 2、原 map header 與 bucket 有讀取、整張 map 仍可探測，並保持 wire network word 7 不作 ordinal。

## 已修正的兩項審查發現

1. 初版串接只收 ordinal 0，無法排除忽略 map、固定寫 slot 0 的錯誤；最後版本改用被移至 slot 2 的 key 67，且檢查 map 讀取。
2. 初版未對 registered body 的 return `RAX` 做原版配對；最後版本於全部 preserving baseline case 及已知反例加入直接比較。

## 邊界

fixture 使用合成且 ID 唯一的 entity/map/partition；未證真實 caller 的生命週期、所有非目標 slot 的有效性、並發或 Windows unwind。測試執行的是 Unicorn RAM 中的固定機器碼，並未接觸遊戲程序或安裝 hook。報告 `fixture_synthetic=true`、`game_process_accessed=false`、`host_native_code_executed=false`、`installable=false` 與此範圍一致。

## 固定指紋

- 測試 SHA-256：`0d2795a840cdf6f5522f193cae2c5587e10d2094619454d522d37a17d9ef337b`
- 報告 SHA-256：`ce134e2b94de2d3ca3f224fee22d0d501cb2896660c939c3e614a0300c0af82a`
- Remove source SHA-256：`097e34c1087f3b311ecf6c9ed85de9165fa739b416e9c99ff7a834aa021c9716`
