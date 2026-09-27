# 四範圍生成與碰撞離線研究

結論：目前**沒有**通過四範圍共同條件的本機武器實例候選；此結果限於已識別的 13 個直接生成呼叫與現有離線資料。
研究狀態：證據不足。未修改 Mod，未驗證玩法、FPS 或自療。

## 路徑矩陣

| 範圍 | P-11 | 霰彈／多彈丸 | 普通生成 | entity | 本機生成前覆寫 |
|---|---|---|---|---|---|
| `p11` | 包含 | 排除 | 普通槍械入口已定位；原追蹤 P-11 飛鏢是否走此路徑未知 | 未知 | 未知 |
| `pistols` | 包含 | 排除 | 固定 options+0x18=1 的普通槍械路徑已確認；該 scope 的完整武器覆蓋未知 | 未知 | 未知 |
| `native_no_shotguns` | 包含 | 排除 | 固定 options+0x18=1 的普通槍械路徑已確認；該 scope 的完整武器覆蓋未知 | 未知 | 未知 |
| `native_weapons` | 包含 | 包含（維持嚴重性能提示） | 固定 options+0x18=1 的普通槍械路徑已確認；該 scope 的完整武器覆蓋未知 | 未知 | 未知 |

## 13 個已識別的直接呼叫

| RVA | options+0x18 | 選項來源 | 彈頭定義來源／綁定位置 | 機制 | 所有權來源 |
|---|---:|---|---|---|---|
| `0x5f5e3d` | `1` | stack-local literal at 0x5f5e15 | global default or indexed projectile table at 0x5f574e..0x5f5775; R13 carried to descriptor；`0x5f5dba` | mechanism unclassified | both IDs selected-object+8 |
| `0x616612` | `1` | stack-local literal at 0x6165c2 | indexed projectile table or default at 0x616515..0x61652a；`0x6165b7` | ordinary native gun | entity-like weaponObject+8; unit-like caller EBX |
| `0x64625c` | `1` | stack-local literal at 0x6461b8 | indexed projectile table at 0x64617c..0x6461a1；`0x6461a1` | component 196 related; runtime participation unproved | entity-like input EDX; unit-like input [RBP+0x77] |
| `0x681816` | `1` | stack-local literal at 0x6817aa | stack definition [RBP+0xB0]；`0x681776` | mechanism unclassified | entity-like [RDI+8]; unit-like EBX |
| `0x681835` | `1` | stack-local literal at 0x6817aa | stack definition [RBP+0xB0]；`0x681776` | mechanism unclassified | entity-like [RDI+8]; unit-like EBX |
| `0x6cb742` | `1` | stack-local literal at 0x6cb6d4 | definition returned by 0x11ec7c0；`0x6cb65d` | mechanism unclassified | both IDs [R15+8] |
| `0x852e14` | `1` | stack-local literal at 0x852d12 | state-selected type via global default or projectile table at 0x852591..0x8525ba；`0x852c64` | mechanism unclassified | entity-like selected-object+8; unit-like via 0x9ef080 |
| `0x8a4d83` | `1` | stack-local literal at 0x8a4d54 | stack definition [RBP+0x220]；`0x8a4cfa` | mechanism unclassified | entity-like [R13+8]; unit-like via 0x9ef080 |
| `0x8a57eb` | `1` | stack-local literal at 0x8a57be | stack definition [RBP+0x330]；`0x8a5767` | mechanism unclassified | entity-like [R13+8]; unit-like via 0x9ef080 |
| `0xb871be` | `1` | stack-local literal at 0xb87102 | global default or indexed projectile table at 0xb87085..0xb870bc；`0xb870bc` | mechanism unclassified | IDs EBX/R14D |
| `0x12a9e80` | `1` | stack-local literal at 0x12a9e27 | global definition pointer loaded to R14 at 0x12a9ccb；`0x12a9e07` | mechanism unclassified | entity-like global dword; unit-like [R12] |
| `0x13a9796` | `1` | stack-local literal at 0x13a977a | global default or indexed projectile table；`0x13a9722` | mechanism unclassified | both IDs EBX |
| `0x13c2314` | `0` | stack-local literal at 0x13c2306 | explosion settings+0x54 via projectile table/default；`0x13c2130` | secondary-projectile/shrapnel loop | IDs input [RSI+0x10/+0x14] |

各列綁定位置將定義指標放入生成描述結構 `+0x10`；生成器於 `0x13a9bde` 讀該定義的 `+0xF0` 旗標。綁定不證明定義為本機武器實例獨占。
此表只覆蓋已識別的直接 CALL；未列舉間接呼叫，也未證明每個呼叫在四範圍的實際執行。

## 判定

- **已排除／`ordinary_gun_fixed_option`**：普通原生槍械入口以常數 1 建立選項，無本機設定讀取邊；本結論只限此已識別路徑。 原生位置：0x6165c2, 0x13a9bbf, 0x13a9bcb。缺口：其他直接／間接入口的完整資料來源和本機武器身份鏈。
- **證據不足／`private_settings_other_fields`**：已見按武器 ID 取設定（無登記時回退資源）：+0x28 及模式覆寫選擇彈種或 entity；+0x254 與 +0x108 進入其他描述／選項欄位。這些已見讀取沒有流入 options+0x18；其餘碰撞語義尚未證明。 原生位置：0x515100, 0x615b15, 0x615b23, 0x615b30, 0x616573, 0x6165f1, 0x13aaa2b, 0x13aaaf3。缺口：本機玩家對該設定記錄的獨占所有權和重用世代；+0x254 與 +0x108 的完整碰撞語義及附件／切換彈藥優先序。
- **已排除／`private_setting_254_first_exclusion`**：此已見欄位流入 state+0x14；來源 entity/unit 排除在 0x13ac68f 與 0x13ac6a1..0x13ac710 先發生，0x13acfa1 才讀 state+0x14 並進入浮點表查詢及 0x6489d0 呼叫。因此它不能在已見路徑改變首次來源排除。0x13aaac4 寫的是另一個 aux+0x14，不能混同。 原生位置：0x616573, 0x61657a, 0x13aaa2b, 0x13aaa2f, 0x13ac68f, 0x13ac6a1, 0x13acfa1, 0x13acfb9, 0x13acff0。缺口：晚期浮點表與 0x6489d0 的確切玩法語義；其他未識別入口是否另讀此欄及本機設定的獨占身份。
- **已排除／`private_setting_108_first_exclusion`**：此已見欄位流入 aux+0x30；原生消費位於清理路徑，先測非零，再作資源索引與間接呼叫，最後清理旗標。它不是已見生成或首次碰撞前的來源排除讀取。 原生位置：0x6165f1, 0x616600, 0x13aaaf3, 0x13aaaf7, 0x13a8c1f, 0x13a8cf7, 0x13a8d01, 0x13a8d20, 0x13a8f09。缺口：清理路徑資源索引與間接呼叫的確切副作用；其他未識別入口是否另讀此欄及本機設定的獨占身份。
- **已排除／`projectile_definition_f0_only`**：65,536 個定義旗標重放均無法清除由非零／缺席選項加入的初始 0x20。 原生位置：0x13a9bde, 0x13a9c45。缺口：其他不同於 +0xF0 的可持久本機欄位讀取證據。
- **已排除／`secondary_zero_option`**：選項為零的生成發生在次級迴圈，另增投射物並計算方向，無法保持原射擊數量、時點與方向。 原生位置：0x13c1c18, 0x13c1ef7, 0x13c2306, 0x13c2314。缺口：爆炸設定到本機武器的獨占控制鏈；此缺口即使補齊也不能消除額外生成語義；固定表 Type 1..422、typelib 列舉 0..423 與原生 <0x1A7 數值對齊；同提交 Go enum Count=356，仍缺原生指標表身份與安裝版本對應。
- **已排除／`raycast_template_global_lookup`**：碰撞查詢依槽位類型重新取全域彈頭定義；runtime 0x800 未設時讀其 +0xF4 作查詢範本。僅向生成器提供本機定義副本不能改變這次全域讀取；來源 unit 排除另由 0x20 控制。此判定只排除該本機副本路線，不否定範本的其他碰撞效果。 原生位置：0x13abcb1, 0x13abcc5, 0x13abccc, 0x13abd6d, 0x13abdad, 0x13abdb4。缺口：其他查詢分支及模板語義；固定參考與安裝版本的對應；四範圍本機實例到查詢定義的獨占身份鏈。
- **已排除／`ricochet_flag_clear`**：清除 0x20 發生於已接受碰撞及反射運動之後，改變軌跡和首次碰撞時點。 原生位置：0x13ae395, 0x13ae580, 0x13ae71a。缺口：本機 P-11 原生路徑身份與實際碰撞證據。
- **證據不足／`entity_branch`**：非零值轉入 entity 生成，模式欄位 +0x248 可覆寫資源；元件 metadata 經間接派發。component-196 相關支線可到原生生成器，但未證 P-11 GUID 實際派發到它，也未建立後續碰撞／治療鏈。 原生位置：0x615b15, 0x615b30, 0x615bbf, 0x6164d4, 0x581377, 0x581421, 0x64625c。缺口：P-11 GUID 的 heap metadata 與實際元件派發結果；entity 實例到原生彈頭、來源 ID、首次碰撞和本機所有權的資料流。
- **證據不足／`local_weapon_lifecycle`**：已見按武器 ID 解析的設定記錄；尚無四範圍共用的可持久排除覆寫欄位與生命週期身份證據。 原生位置：尚未定位。缺口：建立、切換、重生、離開任務、重用時的獨占性和安全還原證據；附件與切換彈藥的原生讀取及覆寫優先序。

## 更新後重查

分開核對結構、武器與附件／彈藥關聯、生成選項來源、碰撞處理。任一來源或指令不符，即撤銷相應舊結論並保留缺口；不得只換雜湊或相似地址啟用新版。
原始遊戲表、程式碼捕捉及私人診斷只留本機。
