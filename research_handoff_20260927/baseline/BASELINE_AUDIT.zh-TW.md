# 基準與保留資產核對（2026-09-27 香港時間）

本紀錄只做 HTTP 唯讀查證和本機檔案雜湊；原資產、原 runtime、preview.9 候選及追蹤模組均未修改。完整保護清單涵蓋 40 個檔案，核對前後逐檔 SHA-256 相同。

## GitHub 已發布基準

[GitHub v0.3.0-preview.8 Release](https://github.com/cainiao524/HD2-Projectile-Collision-Filter/releases/tag/v0.3.0-preview.8) 的 API 列出恰好兩個手動資產，預覽旗標為 true；target commit 為 `46ba372ba2d18ed8d063b579386e6da604e9550c`。Mod 重新從 GitHub 公開下載端點讀入記憶體核對，沒有另存或產生新的 Mod ZIP。

- Mod ZIP：298,797 bytes，SHA-256 `0e536c29908001513115dafdabe366f45d126b6bbf09e39377c045ee1d024783`。遠端實際下載、API digest、原研究 repo 的 `dist/release/` 及旧工作區 `_pcf_assets/` 均一致。
- Toolkit 1.3.2：14,689,109 bytes，API digest 與上述兩個本機副本均為 `844f8a935d70fd07f408869d0ee3ac92955c8e77eec4c1488891b409887d6a84`；本次沒有重新下載 Toolkit。
- Release 的對應條件仍為 Steam build 25480438、EXE 1.8.46015.0、Bingus Shared Loader v17 / API 1 / internal 16。
- Release 對第四範圍只提出可能嚴重影響性能；70 → 130 FPS 歷史回報屬 P-11 0.2.3。此次沒有新 FPS 或幀時間量測。

機器可讀紀錄：`github-preview8.json`。

## AyakaMods 實際頁面版本

使用者指定的舊 slug HTTP 200 可讀；web 閱讀工具對舊／新 slug 均回傳 Internal Error，因此改用一般公開 HTTP GET，沒有登入。頁面 canonical 已改為 [Projectile Self-Hit / 子彈能擊中自己，同 ID 4166](https://ayakamods.com/mods/projectile-self-hit-%E5%AD%90%E5%BD%88%E8%83%BD%E6%93%8A%E4%B8%AD%E8%87%AA%E5%B7%B1.4166/)。

可見 H1 旁的版號和側欄 Version 都是 **0.5**；正文仍介紹 **v0.3.0-preview.8**。JSON-LD 與 Twitter version metadata 也為 0.5，但判定主要依據是可見 H1 和 Version 欄位。`ayakamods-version.json` 保留來源 URL、查詢時間、整份 HTTP 回覆 SHA-256 及這三處最小 HTML 證據。

這是站內顯示版號與 GitHub tag 的差異。未取得 AyakaMods 下載檔指紋，不能僅憑正文便認定兩站二進位相同。程式與性能對照基準採已核實指紋的 GitHub preview.8。其他追蹤 Mod 的警告或頁面評論不列入本 Mod 的 FPS 量測。

## 同名本機 ZIP 差異

舊 checkout `dist/` 及原研究 repo `dist/` 的同名 preview.8 ZIP 均為 299,224 bytes，SHA-256 `0f2449dbdd3f15f87b2b6c875723e694191d813b54fc158c53b46efbf485b6a3`。不可用檔名替代已發布指紋。

逐 entry 比對顯示，與已發布 ZIP 的 entry 集合相同，只有四個 scope 各自的 `Source/<scope>/SECONDARIES.md` 和 `source-integrity.json` 共八項內容不同；其他 entry 內容一致。這說明本機包的差異出在文件及來源完整性清單，並不將它提升為本次指定的發行 ZIP。完整差異在 `same-name-archive-comparison.json`。

## 受保護的本機候選與追蹤模組

原研究 repo 是 `C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced`。

| 相對原研究 repo 的資產 | SHA-256 |
| --- | --- |
| `dist/candidates/v0.3.0-preview.9/Projectile-Collision-Filter-v0.3.0-preview.9-candidate-build25480438.zip` | `2c57bfd8dfa5256d37115756afb8514ed3cec85dcd23a615700c5528bc8958d5` |
| `dist/candidates/filediver-maintenance/HD2-Projectile-Collision-Filter-Update-Toolkit-1.4.0-candidate-win-x64.zip` | `caecefd3e2c690dc82d387e503b132fd428779ecd3e32b6365ac2cd7a24f442c` |
| `dist/homing stim-performance-visual-fix-smooth-v2.zip` | `a46ab775d0c16ffca383cb5c4f6a902b9268ef71c598c242182c46c7ebf4e675` |
| `vendor/homing-original.lua` | `03e5d6b51a8bb0fe476d01b8547ede55ca933e177b241d9d9029a63323f37cbf` |

`third-party/homing.json` 的既有指紋與實檔吻合；其來源是使用者提供的本機 smooth-v2 修訂，未聲稱等同 AyakaMods 公開下載。清單也包括 preview.8／preview.9 runtime 源碼、builder、候選清單和原 preview.8 候選 ZIP。完整路徑、大小、雜湊在 `protected-assets.before.json` 和 `protected-assets.after.json`。

後續研究結束後可在此獨立資料夾執行 `python audit_baseline.py --verify-preserved` 再確認 40 檔。此檢查不連網、不重新產生基準、不寫原資產。
