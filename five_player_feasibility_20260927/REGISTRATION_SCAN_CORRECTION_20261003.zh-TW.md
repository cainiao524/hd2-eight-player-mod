# 2026-10-03 registration scan correction

先前的 1 GiB scan 使用 `limit_mib=1024` 與 `max_read_mib=1024`，讀到 262141 pages 後距離名義上限少 12288 bytes，且舊工具沒有把 postflight image/module identity 分開核對。因此原本的 `truncated=false` 不能當作完整覆蓋證明，原本 12/12 收據已撤銷。

原始 JSON 保留並加上 `audit_correction`；修正後的 scanner 會分開記錄 `termination_reason`、`coverage_complete`、錯誤與 postflight。PID 6884 的修正版 128 MiB 重讀達到讀取上限，但 postflight 發現 module list 不穩定，故仍是 incomplete，沒有有效的 registry-negative 結論。

下一次 live capture 必須使用 `max_read_mib > limit_mib` 並通过 postflight，才能产生有效的有界负面观察。
