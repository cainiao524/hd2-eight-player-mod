# 605950 移除前清理 root 與 606820 必要 reader

## 固定來源及重核範圍

本輪只讀 Steam build `25480438` 的保存 capture，未接觸遊戲程序、掃描全碼或安裝 hook。capture report SHA-256 為 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`，captured data 為 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`，capture identity 為 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`。

| 完整 body | chained fragments | bytes／指令 | body SHA-256 |
| --- | ---: | ---: | --- |
| `605950..605F2F` | 13 | 1503／346 | `4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681` |
| `606820..6068E5` | 3 | 197／51 | `0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce` |

必要 callee `606820` 由 root 的 `6059EE` 直接呼叫，故一併固定完整 body。本份 **root replay** 對其餘 callee 僅列入口邊界；另份[有限直接 helper 前提](roster_departure_native_prerequisites.zh-TW.md)獨立核查了三個 primary registration helper、關聯 ID helper、`FDC310`、`60C2A0` 和 `94C9C0` 的指定片段，並未展開任意 callee tree。[evidence](roster_departure_native_evidence.json) 使用 `bodies['0x605950']`／`bodies['0x606820']`，各有 `bytes_hex`、逐條 RVA／bytes／SHA／encoding、所有 fragments／unwind、完整 CFG、內部分支、外部 relocation、間接控制與陣列 sites。兩 body 全部指令在靜態 CFG 中可由各自入口到達，所有直接分支均落於同一完整 body 的指令邊界。root 有 24 個 RIP reference（其中 2 個是 LEA 地址）、21 個直接 rel32 call、`605AC8 call RAX`、`605F28` 間接 tail jump；`606820` 有 1 個 RIP global，無 call。

以工作目錄為目前目錄，在 PowerShell 重跑至尚不存在的輸出路徑：

```powershell
$cap = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
$env:PYTHONPATH = 'eight_player_candidate_20260927/.native-test-deps'
py -3.12 -B five_player_feasibility_20260927/roster_departure_native_replay.py --evidence $cap --output NEW-roster-departure-native.json
```

[replay](roster_departure_native_replay.py) SHA-256 為 `4675da78f253be7bbec626dc91806b8e33ffa052f30ac20e3723e760f84392b6`；[evidence](roster_departure_native_evidence.json) 與 [recheck](roster_departure_native_recheck.json) 逐 byte 相同，SHA-256 均為 `0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609`。replay 另直接核對 `22473B8` 的 `disconnected\0` 與 `22473C8` 的 `player_count\0` 字面 bytes／SHA。

## Root 實際 ABI 與 roster 地址

入口 RDX 是 target entity pointer；`605975` 保存為 R14，`605978` 讀 ID=`[R14+8]`。入口 RCX 只在 prologue 保存至 home space，並非 roster base。`605962` 從 global `3326468` 取得 S 至 R13，之後 inline 用 `S+D0/D8/DC/E0` 做 target ID→ordinal 查找。初次查找 miss／零容量／invalid ID 令 ordinal 為 `FFFFFFFFh`，**沒有因此離開函式**。root 直接指令沒有更改 roster T/D/P、map value 或四陣列 bytes；外部 call 可能有其自身副作用，不能從 root 的無直接 store 推定整條流程無變更。

| root 直接讀取 | RVA | 原地址／衍生方式 | 八格 sidecar 對應 |
| --- | --- | --- | --- |
| pointer `8` bytes | `605A0D`、`605B96` | `S+E8h+ordinal*8` | `B+ordinal*8` |
| primary 首 DWORD | `605A26/3A/4E` | `605A22 imul RDI,ordinal,70h`；`[RDI+S+108h]` | `B+40h+ordinal*70h` |
| property 首 DWORD | `605A5B` | `605A01/03` 令 RSI=`ordinal*20h`；`[RSI+S+3A8h]` | `B+580h+ordinal*20h` |

aux `38h` 沒有 root 直接讀寫。上述六個 sites 已在 evidence 固定其 SIB／REX、base/index、寬度與 displacement offset；只改 `605A5B` 會漏 pointer、primary 及 `606820` 的兩次 property network-index 讀取。`605A5B` 的 **property 首 DWORD 是關聯 entity ID**，傳至 `FD9C80` 解析關聯物件；它與同記錄 `+0Ch` 的 network index 不同。

`606820` 收 **RCX=explicit S、EDX=target ID**，R10 保存 S。其 `60683A`／`6068CE` 均從 `S+3B4h+ordinal*20h` 讀 network-index DWORD（sidecar 為 `B+58Ch+ordinal*20h`）。它不同於已完成的 `606AD0` getter：invalid ID、capacity 0、map miss 或 map value `FFFFFFFFh` 都可能把 ordinal `FFFFFFFFh` 乘 `20h` 後照樣讀 property，沒有安全的 `-1` 返回。故 `6059EE` 的 callee 應一起改接／替換，並在任何外部通知前建立 ID、map、ordinal、storage 的有效前提。

## 已固定的通知與關聯 ID 順序

以下是 body 內的**條件式**先後，不把外部 callee 名稱等同已觀察的真實網路事件：

1. 初次 map 查得有效 ordinal 後，`605B96` 可讀該 slot pointer 並測 entity `+14h` bit 0；另需 global `347CE18` 指向物件的 `+31276` 非零。條件成立時 `605BBF/605BC9` 以固定字串 `disconnected`、R8B=1、R9D=0 呼叫 `13462C0`。此呼叫在以下 `6059DB` 路徑之前。
2. `6059DB` 另比 target ID 與 global `3483C34`。若不同，`6059EE` 以 RCX=S、EDX=target ID 呼叫 `606820`，隨即 `6059FC` 把其 EAX 作 EDX，配 global `347CE60` 呼叫 `139C360`。若相等，跳過此二 call。
3. `605A0D/15` 再讀 pointer[ordinal] 並測 bit 0；條件成立時，`605A26/3A/4E` 三次讀 primary[ordinal] 首 DWORD，配 RDX=S、R8D=target ID，依序呼叫 `B0B020`、`B11C20`、`B0F820`。此三次讀值與呼叫是獨立指令，不是把整個 70h primary record 交換或清零。有限直接 helper 核查顯示它們以 S 作 registration tuple owner 比對，實際會移除 24-byte registration，某些路徑釋放 backing；改接陣列時必須保留 RDX=S 與原呼叫順序。
4. 不論三個 primary call 是否執行，`605A5B` 讀 property[ordinal] 首 DWORD，`605A68` 呼叫 `FD9C80`，RAX 作關聯物件 RBP。後面依 RBP 是否存在、其 bit 0、RBP+Ch、owner 狀態與 target flag 等條件，可能經另一個以 RBP ID 查找的 map、`A747D0/A74700/A77800`、`BE21A0/BE16F0` 等外部 call，或對 RBP 與其他關聯物件 ID 呼叫 `FDC310`。這些 callee 的副作用及外部資源生命週期未在本輪閉合。
5. `605EDE` 的條件式 `94C9C0` 呼叫接收較早從當時 global S 取的 `D−1`；該 callee 的固定指令會把這個 unsigned 值 clamp 至 `[1,4]`，用於 `num_players` 通知並傳給 `94BE10`。尾段 `605EF1` 從 held R13 的 S 讀 `S+84h`、`605EF8` 減一，`605EFA` 以該值作 EDX 呼叫 `60C2A0`；其四種 hash 資源分支只涵蓋 1..4，其他值仍進數值通知 `Multiplayer_NumberOfActiveTeammates`。其後 `605F0D` **再次**讀 `S+84h`，`605F06` 指向固定字串 `player_count`，`605F28` 經全域介面 `+480h` 間接 tail jump 派發。外部 callback 的更深層效果未閉合，不能假定第二次讀到的 D 與第一次相同。

先前固定 [roster_property_apply_findings.zh-TW.md](roster_property_apply_findings.zh-TW.md)／`roster_property_apply_evidence_v3.json`（SHA-256 `d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22`）另證 `FDC820` 刪除流程先經 `540B20→605950` 清理回呼，之後另一張 callback 表才派 `540A40` 實際 roster 移除。因此此 root 應定性為**移除前清理／通知階段**；其完整 body 沒有直接 `60CEA0` 或 `540A40` call，不可用它代替原移除本體。

上述直接 helper 與下游 count 指令的來源／範圍另列於[有限前提](roster_departure_native_prerequisites.zh-TW.md)（SHA-256 `7048a6853045410a0d5d4770bdfd9e8a5ca54c22580d3005d6fd74a10ed99eac`）。其七個指定 body 的 bytes、逐條指令與三組字串另由獨立[callee evidence](roster_departure_callee_evidence.json)及相同 bytes 的[recheck](roster_departure_callee_evidence_recheck.json)固定，兩者 SHA-256 均為 `04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0`；[callee replay](roster_departure_callee_replay.py) SHA-256 `c2d7720386430b9022b3f0285a6d99c9dc74b28706627389d26b46fd0e19d0ad`。這組證據與本份只含 `605950/606820` 的 root evidence 分開。`60C2A0..60C33F` body SHA-256 `66ce04f430d2fc2d46c023d5d7cff18bb19cca43a0f43eaf72fa842b01f066d6`；`94C9C0..94D308` SHA-256 `7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2`，其尾部含 jump table，並非全段指令。`94C9C0` 傳給 `94BE10` 的 clamped EBP 用途尚未展開，所以單把四上限改八不構成已驗證的八人 count 路徑。

## 固定原碼 probe：通知參數與後續移除 D

[離線 probe v2](roster_departure_native_probe_v2.py)（SHA-256 `961d96575dd07987cc96fc9675faf34df0d0a992aa1af6885551be2837f222a4`）從上述 root、callee 與既有 remove evidence 重建並執行**原** `605950`、`606820`、`FD9C80`、`540A40`、`172F8A0` 機器碼。先跑 pre-removal root，然後由 synthetic harness 另啟動 remove；此先後符合已存 FDC820 table 次序，但 probe 沒有執行 FDC820。fixture 將 property 首 DWORD 設為 `7FFFh`，真實 `FD9C80` 走 `FD9C80/C84/C87/C8D/D2C/D2E/D32` 七條指令的直接 null 分支，並在 `605A6D` 實際觀察 RAX=0；這些指令與 body SHA `0533fa336a0f696021412e722716c7de8ee2096439a98f7e8671a9ea44487eae` 已從固定 capture 獨立核對。外部 network／UI／count／tail 通知仍是保留 nonstack fixture 的受控 stub；`60C2A0` 與 `94C9C0` body **沒有**在 probe 執行。三個移除均是各 segment 末筆，因此此 probe 不執行原 mover。其[保存結果 v2](roster_departure_native_probe_results_v2.json)與獨立重跑逐 byte 相同，SHA-256 `13c45a80d7657548d92142663dbab278f08eeffe026e32e30ba379f7e45b1874`。

| 原四格 fixture | `T/D/P` | target ordinal | UI 參數與 `60C2A0` EDX | tail `player_count` EDX | 後續原 remove 的 D |
| --- | --- | ---: | ---: | ---: | ---: |
| dense | `1/1/0` | 0 | 0 | 1 | 0 |
| pending，另有 dense | `2/1/0` | 1 | 0 | 1 | 1 |
| pending，無 dense | `1/0/0` | 0 | `FFFFFFFFh` | 0 | 0 |

probe 的 nonstack snapshot 與 callback 時 counts 保持不變，因而在**該受控條件**下量到兩個 pending count 參數與後續 D 不一致，D=0 時有 unsigned 減一下溢。這是原碼數值資料流的反例，不能推定 pending target 在真實 caller 可達，亦不能從後續 D 反推通知本應採何語義。v1 曾以 `FFFFFFFFh` property 加上強制 `FD9C80` null stub；該 null 不由保存指令證成，故 v2 改用已證 `7FFFh` 直接 null 分支並保留 v1 作審查歷史。真實外部 callback 可能改 S、map、counts 或重入，故整條生命週期仍未閉合。

[獨立 probe 複核](roster_departure_native_probe_review.zh-TW.md)已核五個原 body、空值分支、三個結果及替身邊界；其重跑輸出與 v2 保存結果完全一致。

## 原碼風險與候選界限

當初次查找給 `FFFFFFFFh`，`605A01/03` 仍將 ordinal 乘 `20h`，`605A5B` 會以此錯位讀 property；在此之前某條件路徑還可能呼叫 `606820`，其本身也會錯位讀 network-index。其他 external call／`disconnected` 通知亦可能已發出。若做八格 sidecar 候選，guard 必須早於首次外部 call／通知及所有 roster array 存取，驗 target ID、map backing/probe、`ordinal<8`、sidecar 四陣列有效性與 S binding；拒絕不能讓此較大 wrapper 的後續外部流程當成成功。此時仍有實際 caller／外部 side effects、間接 tail target、同步、Windows unwind 與回復設計待整合，固定 body 不能證明可安裝或多人功能已完成。
