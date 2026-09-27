# 名冊整理的原四格執行反例

## 結果與實作決策

**保存的 `60CC70` 不能僅以 `P≤D≤T` 作為「保留全部有效實體」的前提，直接改接成八格整理候選。** 原指令先將 P 槽複製到 D 槽，再把已覆寫的 D 複製回 P。在 `P<D<T` 且每筆 tracked 記錄原本互異的合成狀態，原 D 實體會遺失，ID→ordinal map 也會留下錯誤對應。

這項調查對應成品驗收 A「額外玩家不取代既有玩家」及 B「角色生命週期」。它否定的是目前預定的直接重定位方案及其輸入前提；尚未證明真實遊戲會到達反例狀態，也沒有宣稱現行遊戲存在可重現的玩家遺失問題。

候選保持 `0.7.0-offline`。本輪沒有新增 compactor emitter；局部插入／屬性／搬移候選仍有原先的限制，不能據此啟用完整名冊。只接受 `P==D` 或 `D==T` 的退化分支，也不能算完成完整整理需求。

## 固定來源與實際執行

使用 build `25480438` 已保存的原 x64 bytes，在 Unicorn 的合成記憶體中執行。沒有讀取遊戲程序、執行主機原生遊戲程式或安裝修改。

- [完整指令及 CFG 證據](roster_compact_native_evidence.json)與[逐 byte 相同的重播結果](roster_compact_native_recheck.json)：`60CC70..60CE76` 共 518 bytes、100 條指令、三個 unwind fragments。
- [靜態資料流分析](roster_compact_native_findings.zh-TW.md)及[獨立 caller／前提審查](roster_compact_native_prerequisites.zh-TW.md)：确认兩次單向複製、原 shared mover ABI，以及已知 caller 未提供直接 roster count guard。所有衍生 alias 與上游 callee 狀態仍未閉合。
- [執行反例程式](roster_compact_native_probe.py)及[完整結果](roster_compact_native_probe_results.json)：執行保存的 compactor、mover、map helper；額外合成序列也執行原 dense／append bodies。沒有替換 helper 或修改執行中的 RIP 來模擬其行為。
- [獨立 probe 審查](roster_compact_native_probe_review.zh-TW.md)及[獨立重跑](roster_compact_native_probe_review_recheck.json)：未發現使反例無效的具體缺陷。兩次輸出只在 Python 版本欄位不同，其他欄位、bytes hashes、events 與 writes 逐值相同；另獨立重算 map keys／ordinal 全集及 35 種分段結果。

記錄使用原四槽 inline 布局：pointer `+E8/stride8`、primary `+108/stride70h`、auxiliary `+2C8/stride38h`、property `+3A8/stride20h`。四個實體 ID 為 11、19、27、35；八個 map buckets 刻意包含碰撞鏈，起始每筆有效實體均有正確且唯一的對應。

| 執行範圍 | 結果 |
|---|---|
| `T=0..4`、`D=0..T`、`P=0..D`，共 35 個分段 | 每個案例實際執行原 compactor；未超出原四槽容量 |
| 10 個 `P<D<T` 案例 | 實體保留／唯一性／map 雙向一致性不成立 |
| 其餘 25 個案例 | 上述保留性成立，限定所提供的合成資料 |
| dense→append→compact 的三步合成序列 | 原插入函式可在指定呼叫順序下形成最小反例；實際遊戲的 dispatch 順序仍未證 |
| 總 top-level 函式執行 | 38 次，含 35 次分段測試及序列中的 3 次；內部 helper 呼叫不另加算 |

這 38 次是反例調查，**沒有加進候選原有 99 組／724 次的通過測試數**。

## 最小反例

初始 `T=2,D=1,P=0`，兩筆記錄 A／B 的 ID 分別為 11／19。

| 時點 | slot 0 | slot 1 | map 11 | map 19 |
|---|---|---|---:|---:|
| 入口 | A | B | 0 | 1 |
| inline `0→1` 與 map 更新後 | A | A | 1 | 1 |
| shared mover `1→0` 後 | A | A | 0 | 1 |

返回時 `T=2,D=2,P=1`。四組 parallel records 全部遵循相同覆寫順序；map 19 仍指向 slot 1，但該槽已屬於 ID 11。原 B 沒有在此 body 內被保存或移往其他位置。

Probe 分開核對兩種性質：其一是全部非 stack pages 是否精確符合原指令的複製順序；其二是原 ID 是否完整保留、槽位 ID 是否互異、map 是否仍雙向一致。前者符合不代表後者正確。另核對非揮發 GPR、XMM6–15 及返回 stack pointer。

三步序列從空名冊開始，先以 flag 0 執行 `60CA80` 建立 A，再以 `60CBA0` 追加 B，最後執行 `60CC70`。這證明選定原 bodies 在該合成順序的局部結果，沒有證明遊戲會按此順序派送同一名冊。

## 重現

以下命令只讀既有 capture；output 必須是尚不存在的路徑。它不查詢或啟動遊戲。

```powershell
& 'C:\Program Files\Python312\python.exe' -B -X utf8 `
  'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_compact_native_probe.py' `
  --capture 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438' `
  --output 'E:\File\Codes\0\26.10.1\HD2\five_player_feasibility_20260927\roster_compact_native_probe_local_recheck.json'
```

程式自行核對五段原 body SHA-256；保存的結果記錄 probe 原始碼、capture 及 body 指紋。原機器碼執行依賴工作區已固定的 Unicorn；指令讀取使用既有 `inspect_capture.py`。

## 派送查核與下一步

已針對註冊的 append table `owner+F0B6F0` 作[有限派送查核](roster_append_dispatch_findings.zh-TW.md)，其中 component 239 的 slot `owner+F0BE68` 指向 `540850`。已證 `FDC780→576CF0→60CC70` 的整理呼叫鏈；既有建立階段 `FDC140→581320` 使用另一張 `F0C110` 表，不能用來替代 append reader。已保存 caller 片段也不足以證明兩者完整先後關係。[證據](roster_append_dispatch_evidence.json)、[重播](roster_append_dispatch_replay.py)及[獨立重跑](roster_append_dispatch_review_recheck.json)已保存，三份輸出逐 byte 相同。

本次未找到已驗證的第一張表 reader。這是有限查核的覆蓋結果，不能推出 reader 不存在。仍需回答 pending 記錄何時建立、原 D 是否必須保留、誰保證 `P<D<T` 不可達或提供額外所有權前提；取得可接合的計算地址來源或新保存資料後才重開這條支線。不得自行把兩次 copy 改成 swap／rotate，也不能靠刪除不通過情境宣稱完成。

下一個可獨立離線推進的切點是已固定的移除入口 `60CEA0`／`540A40`：先核 map 刪除、tracked／dense／prefix 的前提與 shared mover 呼叫順序，再選擇有完整語義根據的八格改接，驗證移除後其餘 entity／記錄／map 仍一致。此工作不會解除上述整理缺口。

平台加入、第五至八人生成與同步、分類／移除／其他讀者、儲存配置與清理、執行整合及多人任務驗收仍未完成。
