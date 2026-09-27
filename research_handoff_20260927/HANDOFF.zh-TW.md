# 四範圍免逐彈研究續查 — 2026-09-27

**結論：尚未找到符合條件的共同本機武器欄位。`field_binding=null`、`status=UNBOUND`。本輪交付離線證據、工具、測試與具體缺口，沒有製作新的可啟用 Mod ZIP。** 這是對固定來源及已捕捉程式碼的有界結論，不是「所有方法都不可能」的證明。

本輪在獨立的 `research_handoff_20260927/` 目錄工作。已讀原專案 `AGENTS.md`、Agent 指南、生成研究、条件式 Mod 規格、上游驗證設計與既有報告。原專案位於 `C:/Users/OvO/Documents/Codex/2026-09-26/referenced-chatgpt-conversation-this-is-an/outputs/healing-pistol-enhanced/`。該路徑及本目錄是本機交接資料，不應整包公開；本目錄包含私人捕捉的局部反組譯及資料衍生分析。

## 基準核對

| 項目 | 核對結果 |
|---|---|
| GitHub `v0.3.0-preview.8` | 重新下載遠端 Mod ZIP 至記憶體核對：298,797 bytes；SHA-256 `0e536c29908001513115dafdabe366f45d126b6bbf09e39377c045ee1d024783`；tag commit `46ba372ba2d18ed8d063b579386e6da604e9550c`。原研究 repo 的 `dist/release/` 資產一致。 |
| AyakaMods ID 4166 | 2026-09-27 06:35（香港）公開 HTTP 頁面可見 H1 版號與側欄 Version 均為 **0.5**；正文仍寫 **v0.3.0-preview.8**。頁面 canonical 名稱已是 Projectile Self-Hit / 子彈能擊中自己。沒有驗證 AyakaMods 下載資產。 |
| 同名 ZIP 陷阱 | 原 repo `dist/` 與舊 checkout `dist/` 中另有同名 ZIP，SHA `0f2449dbdd3f15f87b2b6c875723e694191d813b54fc158c53b46efbf485b6a3`；僅八個文件／integrity entries 與發布包不同，但仍不能用檔名冒充發布指紋。 |
| 保留的 preview.9 | ZIP SHA `2c57bfd8dfa5256d37115756afb8514ed3cec85dcd23a615700c5528bc8958d5`。 |
| 保留的原追蹤 Mod | ZIP SHA `a46ab775d0c16ffca383cb5c4f6a902b9268ef71c598c242182c46c7ebf4e675`；Lua SHA `03e5d6b51a8bb0fe476d01b8547ede55ca933e177b241d9d9029a63323f37cbf`。 |

程式與性能對照基準繼續使用已驗指紋的 [GitHub preview.8](https://github.com/cainiao524/HD2-Projectile-Collision-Filter/releases/tag/v0.3.0-preview.8)。[AyakaMods 顯示版本](https://ayakamods.com/mods/projectile-self-hit-%E5%AD%90%E5%BD%88%E8%83%BD%E6%93%8A%E4%B8%AD%E8%87%AA%E5%B7%B1.4166/)與下載內容身份分開記錄。

詳見 [基準稽核](baseline/BASELINE_AUDIT.zh-TW.md)、[頁面版本證據](baseline/ayakamods-version.json)、[GitHub 資產證據](baseline/github-preview8.json)、[40 檔保留清單](baseline/protected-assets.before.json)。

## 固定來源與重播

- FileDiver 本機 checkout HEAD 為 `bf0ce329db3cf0043994eb717ea86433c303cb36`。重播原有 16 檔 `generation-research-v1` bundle：bundle fingerprint `44a3acc0e56685768544b0adcc14e8e47b58845e362258d089fd9bef56b190cd`，analysis fingerprint `a1c7d72ba38d91f3526af7d8a58f2eee0ec235198d9a28d454abf2bc84eca1b3`，與規格完全相同。
- 原生程式碼：Steam build `25480438`，`game.dll` SHA `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e`。原 framed capture SHA `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`；抽出的 `captured-data.bin` SHA 為不同層次的 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`。兩者不可混用。
- 捕捉保存 42,153,827 bytes，包含所選 code、readonly、unwind 範圍；未包含所有模組區段、可寫全域或 heap。`capture_complete=true` 只表示所選範圍完整，並不代表完整 runtime 狀態或原子快照。
- 舊 schema 3 生成證據重播 fingerprint `91a2468bb745b6f266ca7aa3f537e7dba35569fd937c0a8ee4a39a0b46d65ac2` 不變；比較為 `unchanged_still_unverified`。本輪新增發現保存在獨立續查報告，未把舊報告偷偷升格。
- 外部方法參考 checkout HEAD 確認為 `d1811983ab4fec230ede24bdd3d274f77b0b82fd`。已核對 Eruptor/Dominator 案例是整筆共享定義替換；不能作本機武器獨占設定的證据。本輪沒有執行或導入其 runtime。

重播的分類數為：副武器槽位 27 筆、帶已辨識射擊元件 20 筆、彈頭 350 筆、霰彈／多彈丸排除 38 類、其中多彈丸 32 類。這些是固定參考資料分類，`matches_game_build`／玩法對應沒有因重播而提升。

## 本輪新增的路徑證據

### 1. source entity gate 與碰撞結果分支

同版指令核實 source entity 相等檢查在 **`0x13AC68F`**，相等跳轉在 `0x13AC697`。舊 `HANDOVER-CODEX.md` 的 `0x13AC5FF` 不能沿用：此捕捉該位址是 `movss [rax+0x18], xmm0`。新 schema 3 文件已使用正確位址。

在 entity/unit 相等檢查之前，`0x13AC65A` 測試結果資料的 `0x800000` 位元，`0x13AC66E` 可轉走另一條結果處理支線。已追明這是 **0x2C-byte 查詢結果記錄的 `+0x20` dword**，不是武器設定或 projectile runtime flags。

結果資料由兩條物理查詢 buffer 複製而來：普通 worker `0x175C63C` 呼叫 API `+0x68`，另一種 worker `0x175B902` 呼叫 API `+0x80`；相關另一分支經 API `+0x128`。API 由註冊查詢取得（其中 provider ID 為 `0x4C26B82B`），但全域 API pointer slots `0x3326328`／`0x3326338` 在捕捉範圍之外，無法從此捕捉還原實際函數地址與寫入該位元的實作。

這項發現擴充了碰撞控制流程；它沒有建立「發射前、本機武器私有欄位 → 結果 bit」的資料邊。普通 query 先在 `0x13ABD6D..7F` 依 runtime `0x20` 選來源 unit 或 0，並在 `0x13ABE02` 寫入既有解析的查詢排除參數。後段 hit-result bit 沒有證據能撤銷較早的來源排除，因此僅看到後段跳過檢查，也不能證明來源會進入查詢結果；本輪未重證 API 全部語義。

具體 bytes、欄寬、兩條結果來源、API 註冊及缺口見 [entity 證據](entity/entity-evidence.json) 與 [entity 報告](entity/entity-report.zh-TW.md)。

### 2. entity component 196 的兩個派發階段

註冊程式碼證明兩張不同 callback 表：

| 階段 | 表與 component 196 slot | 註冊值 | 派發 |
|---|---|---|---|
| 第一階段 | `system+0xF0C110+196*8 = +0xF0C730` | `0x537AD0`，註冊指令 `0x55AE6C/73` | `0x581421` |
| 第二階段 | `system+0xF0D550+196*8 = +0xF0DB70` | `0x537C70`，註冊指令 `0x55AE96/9D` | `0x581A4E` |

第二階段 wrapper 可到 `0x641050 → 0x646030 → 0x64625C → 0x13A9830`；該原生生成呼叫仍把 `options+0x18` 設為 1。註冊與可能 call graph 已比舊報告具體，但沒有當次 P-11 的有效 GUID、heap metadata、元件實例或實際派發。不能把第一階段 `0x581421` 直接寫成派發到第二階段 wrapper。

另外核實 `0x641D7A` 檢查的是 `0x504720` 回傳 resource 的 `+0xAD` byte；零會跳過這段 native spawn。它尚無已證名稱、本機獨占或原射擊等價性，不能把「能跳過生成」當來源碰撞開關。

### 3. 間接引用與上游函數指標

對已捕捉 code／readonly 及 unwind 邊界做有界掃描，constructor `0x13A9830` 仍核實既有 13 個 direct CALL。未在受檢的 MOV／LEA RIP-relative address-taking 或 absolute VA 指標模式中找到新的 constructor 入口。readonly 中兩個指向 constructor RVA 的字面值是 chained unwind 記錄，不能當可呼叫指標。

沿 caller 上推找到 readonly **`0x214D040`** 保存 `base+0xBB9950` 的 8-byte 函數地址；可見 code chain 為 `0xBB9950 → 0xBB99F9 → 0xB86F10 → 0xB871BE → constructor`。這是已保存函數指標及靜態 code chain 的證據，其表的 runtime consumer／本機武器關聯仍未定位，不能稱實際 dispatch 已證。

此支線 `options+0x18` 在 `0xB87102` 仍固定為 1。上游記錄 `+0x14` 的最低位（mask `0x01`，bit 0）可進 `options+0x1B`，constructor 存到 motion record `+0x54`（system-relative `+0x3094`）；已找到的消費在 `0x13A8794` 清理／延後釋放支線。已見 helper 的 OR 1、caller 的 OR `0x4000`／AND `0x7FFF` 對 65,536 個 u16 輸入都保留原 `0x20`，且該支線會寫入 0.3f 的 motion 欄位。它不是已證首次来源排除開關。此清理函式也可能由 constructor 回收舊槽位時呼叫，不能籠統聲稱每次都晚於首次碰撞。完整邊界與搜尋限制見 [間接引用結論](indirect/indirect-findings.json) 及同目錄工具、報告。

這次搜尋不涵蓋任意算術組合、動態 heap/vtable、全部未列入 unwind 的 leaf code 或未捕捉區段；「沒有模式命中」不能提升為「沒有任何間接入口」。

### 4. 有效模式與另一個設定消費欄位

[設定續查工具](settings_findings.py) 對 **44 個指令位置**同時核對固定 bytes 和從已知邊界連續解碼的結果：

- `0x615B19` 呼叫 `0x1787500(weapon ID, 8)`，只有回傳 1 才選用 alternate 欄位。`settings+0x240` 是 u32 projectile type，`+0x248` 是 u64 entity resource；各自非零才取代先前選值，零會保留先前值。有效 entity 為零才走 `0x616502` 原生支線。這補上該局部優先序，未證完整附件／彈藥生命週期。
- constructor 在初始 flags 已寫入後，另查 `0x1787500(ID, 7)`；回傳 1 且解析設定 **`+0x23C` float32 > 0** 時，把該值載入 XMM6。它再乘另一個 manager record `+0x50` 和可選 `options+0x2C`，用於三個方向分量的初始速度項；其後還可能加 `options+0x20` 指向的 XYZ 速度。這證明它控制發射速度縮放，沒有證明 self-hit-only 且速度等價的改法，也沒有流入 `options+0x18`。等值、零因子與浮點捨入可能不改數值，不能說每次欄位變動都必然改最終速度。
- 同一 manager 下有不同記錄：`manager+0xD0`、stride `0x268` 的解析設定，與 `manager+0x78`、stride `0xA8` 的另一張記錄表。不能因 manager 相同就合併欄位身份。`0x515100` 也可回退基礎資源，故欄位名稱使用 resolved setting，不預設其私有性。

一般與 `python -O` 產生完全相同的 [設定證據 v2](settings-findings-v2.json)。初版保留供審查歷史；以 v2 的限縮敘述為準。第二位工程代理已獨立重播 bytes 並審查資料流。

## 四範圍準入狀態

| 類別／範圍 | 這次補充 | 尚缺 |
|---|---|---|
| P-11；四範圍都包含 | 普通入口、entity 兩階段靜態鏈與既有 P-11 分類 | 同次有效設定／GUID／元件及實際派發、共同欄位、原生自療等價 |
| 其他副武器；`pistols` | 固定副武器槽位分類與局部模式非零覆寫條件 | 每類原生機制的相同欄位消費、本機獨占與有效附件／彈藥身份；前三範圍仍排除霰彈／多彈丸 |
| 普通原生武器；`native_no_shotguns` | 已見直接入口與新的函數指標／上游 chain | 各類均可在發射前設定的共同欄位，原彈數、速度、傷害等價 |
| 霰彈／多彈丸；僅 `native_weapons` 包含 | 固定分類重播通過 | 同機制本機設定、每顆原彈數／起點／方向等價、連發性能與幀時間 |
| 附件、切換彈藥及所有權生命週期 | 局部 mode 8 選擇條件、不同 manager arrays 已明確 | 完整優先序、建立／重建／切換／重生／離任／重用的世代與安全還原 |

單有 P-11 preflight／lease 摘要、metadata 註冊、分類通過或欄位名稱，均不能使共同準入 C1–C7 通過。既有 `+0x254` 晚期消費、`+0x108` 清理消費、定義 `+0xF0` 全組合、全域 RaycastTemplate、額外破片及反彈排除證據維持原有界限；本轮沒有重試原生彈丸槽位觀察。

## 驗證與未執行項

| 核對 | 結果 |
|---|---|
| 原有生成研究、reference、副武器 catalog、projectile verifier 測試 | 一般 Python **118 項通過**；`python -O` **118 項通過**。含四 scope 分類、來源 pin、欄位映射、錯誤指令與假造已驗證狀態拒絕。 |
| 破壞 source guard 的 mutation | 只在 child process 移除 exact-source gate；兩種 Python 模式的原有 regression test 均 **FAILED，exit 1**，符合故障注入預期。沒有修改正式來源或證據。 |
| 固定 FileDiver bundle 與舊 schema 3 | 重新解析原 16 檔，analysis fingerprint 相同；舊 evidence 重播與比較相同，仍未驗 gameplay。 |
| 新設定資料流 | 44 instruction bytes＋連續解碼核對通過；normal／optimized JSON byte-identical。 |
| 新 entity 路徑 | 81 instruction bytes＋邊界核對；normal／optimized 各 6 tests PASS。停用 verifier gate 後兩模式均有 3 failures、exit 1。 |
| 新間接路徑 | normal／optimized 各 7 tests PASS；改錯指令 pin 後兩模式均 exit 1。13 constructor CALL 及上游 xref 已重播。見 [間接路徑報告](indirect/INDIRECT_PATHS.zh-TW.md)；不代表實際 dispatch。 |
| 新 Mod 的所有權拒寫、物件重用與還原 | **未執行**：尚無合格欄位或 runtime writer，不能用空殼模擬冒充通過。 |
| 遊戲原行為、FPS 和幀時間 | **未執行**：尚無准入候選。沒有新的自療／性能結論。 |

[驗證摘要](verification-summary.json) 合計一般與最佳化模式各 **131 項通過**（118+6+7），另有三組刻意破壞後非零退出的測試。摘要保留兩個已處理的初次失敗：Windows GBK 解碼 UTF-8 子程序输出失敗後已修工具；舊格式 analysis 被正確拒絕後，改用規格固定的 `analysis-final`，並重新解析原 bundle 得到同一 fingerprint。測試日誌沒有刪除或改寫成成功。

將來候選准入後，必須用指紋固定的 preview.8、相同場景／武器／負載，分別記錄 P-11、其他範圍、霰彈連發的 FPS **及 frame time**；同步核對彈數、起點、方向、速度、彈藥、射速、傷害與原生治療。第 4 範圍的既有說法是「**可能**造成嚴重性能影響」；70→130 FPS 只屬 P-11 0.2.3 的歷史回報，不是 preview.8 或本輪的量測。其他追蹤 Mod 頁面的警告未納入本 Mod 性能證據。

## 下一份真正缺少的資料

1. **首次碰撞結果 flags producer 的同版靜態實作**：需要解析 API `0x3326328`／`0x3326338` 所指的函數表及相關 query 實作，找出 result `+0x20 & 0x800000` 的來源。當前無指標值，不能猜其他 DLL 的任意函數；即使找到 producer，也須連回武器設定及前段 source-unit query exclusion。
2. **函數指標表的 consumer／機制身份**：readonly `0x214D040` 所屬表如何被引用、由何種本機武器機制呼叫；可見 code chain 不代表使用者武器曾走此路線。
3. **本機武器欄位的原生讀取邊**：仍缺一個具體、可持久、發射／首次碰撞前被讀取，而且不改來源身分／彈道／彈數的欄位。`+0x23C` 的已見速度用途、`options+0x1B` 的已見清理用途都不填補此缺口。
4. **只有上述欄位證據通過後**，才設計同次、有限、唯讀的 avatar→武器／附件→設定正反映射、有效 mode／GUID、metadata／元件與實際派發核對。C2/C3/C7 還需排除共享資源、指標重用和其他 writer；這輪沒有安排新遊戲操作或新 observer。

已發布 preview.8 繼續作可用基準；preview.9 與原追蹤模組保留。本輪沒有覆寫、部署或發布既有資產。

## 重播入口

在原研究 repo 根目錄，用新的輸出目錄執行 `tools/reference_data.py analyze` 與 `tools/generation_research.py analyze/compare`；固定輸入路徑與指紋見上述「固定來源」。本次輸出在 `reference-replay/`、`replay-final/`、`compare-final/`。

在本交付目錄上層：

```powershell
python research_handoff_20260927/run_offline_checks.py --repo '<原研究 repo>' --output '<全新測試輸出目錄>'
python research_handoff_20260927/settings_findings.py --repo '<原研究 repo>' --output '<全新設定證據 JSON>'
python -O research_handoff_20260927/settings_findings.py --repo '<原研究 repo>' --output '<另一個全新 JSON>'
python research_handoff_20260927/baseline/audit_baseline.py --verify-preserved
```

entity／indirect 的命令及 Python/Capstone 依賴見各自報告。本輪使用 Python 3.14 與 Capstone 5.0.7。這些工具僅讀既有檔案；基準稽核完整模式會讀取公開網站，`--verify-preserved` 完全離線。
