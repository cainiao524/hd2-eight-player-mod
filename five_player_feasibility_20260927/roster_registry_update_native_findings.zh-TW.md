# `B54E00` registry 更新、`606520` 必要 reader 與 `FD9BA0` 測試 helper

## 固定來源及有限範圍

本輪只讀 Steam build `25480438` 已保存的 `existing-code-evidence-25480438` capture 與既有 [`roster_property_consumers_native_inventory.json`](roster_property_consumers_native_inventory.json)；inventory SHA-256 為 `0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2`。沒有查詢遊戲程序、重擷取、外網、泛掃其他函式或安裝程式。

| 完整 body | unwind fragments | bytes／指令 | body SHA-256 |
| --- | ---: | ---: | --- |
| `B54E00..B55169` | 3 | 873／203 | `8f679d31841a3cce6ee1f4d66ec47bc89aa9a347b68939bc4264ec25bf8bd783` |
| `606520..60662F` | 1 | 271／72 | `ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e` |
| `FD9BA0..FD9C7C` | 3 | 220／59 | `d81d3d8b8d73c6301dae0432dbb840658fe113ba8a356c084da5c6d28ab51ad7` |

[`roster_registry_update_native_replay.py`](roster_registry_update_native_replay.py)固定每個 fragment 的起迄、unwind RVA、SHA、完整 body bytes、逐條指令 encoding、所有局部分支與可達 CFG、RIP／direct-call 重定位、間接 call、返回點及下列每一陣列 operand。[evidence](roster_registry_update_native_evidence.json)與獨立[recheck](roster_registry_update_native_recheck.json)逐 byte 相同，兩者 SHA-256 均為 `7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1`。`B54E00` 有 40 個局部分支、7 個 RIP reference、6 個直接 call、2 個間接 call；`606520` 有 11 個局部分支、3 個 RIP reference，沒有 call。`FD9BA0` 為供真指令測試的原封 helper，有 6 個局部分支、3 個 RIP reference，無 call 或 roster 陣列位點。三個 body 的全部指令均可由入口沿固定 CFG 到達，局部分支全落在本 body 的指令邊界。

以 workspace 根目錄為目前目錄，重跑至尚不存在的輸出路徑：

```powershell
$cap = 'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
$env:PYTHONPATH = 'eight_player_candidate_20260927/.native-test-deps'
py -3.12 -B five_player_feasibility_20260927/roster_registry_update_native_replay.py --evidence $cap --output NEW-roster-registry-update.json
```

## Registry／S 身分與動作次序

`B54E00` 入口 ECX 是輸入 entity ID，`B54E14` 保存於 EBX；入口 RCX **不是** roster S。`B54E0A` 從 global `3326E68` 取得 registry 至 R13，外迴圈讀 `registry+10F0` count 與 `+1100+index*16` tag。它依 tag `115h`、`73h`、`69h`、`2Eh` 選擇不同支線，最後由 `B55168` 返回。tag `115h` 的 `FD9AF0`／兩個間接 call、tag `2Eh` 的 `7B5760` 及 tag `73h` 的 `1731A60` 呼叫仍屬完整原 body 的既有流程；本輪沒有展開其資源樹。

tag `69h` 在 `B55003` 由 `registry+10F8+index*16` 載入 **R14=S_registry**，以 `[R14+84h]` 的 D 作 property loop 上界。`B5501C` 導出 `RDI=S_registry+3A8h`；每次 `B55030` 讀首 DWORD（關聯 ID），`B5503A` 把該值交給 `FD9BA0`，用 `[rsp+88h]` 的結果與入口 EBX 比較，不相等才在 `B5504A` 將 RDI 加 `20h`。這個首 DWORD 不是 network index，也不是 map ordinal。

匹配後，`B55057` 以 loop ordinal ESI 讀 `S_registry+E8h+ESI*8` 的 entity pointer。`B5505F` **另從 global `3326468` 載入 R11=S_global**，按所讀 entity ID 在 `S_global+D0/D8/DC/E0` map 查找；`B5510A` 的 map value EAX 才是 **aux ordinal n**。`B550CD` 比較、`B550D8` 寫入的都是 `S_global+2E0h+n*38h` 的 aux DWORD，值非 2 時寫為 1。隨後 `B550E9` 仍以 **ESI** 從 `S_registry` 讀 pointer，若其 `+14h` bit 0 非零，`B550F7/B550FB` 清除 `S_registry+3ACh+ESI*20h` DWORD 的 bit 0。原指令沒有證明 `S_registry == S_global`，亦沒有檢查 n 等於 ESI；改接不可把兩個下標偷換。

特別是 map 無容量、miss 或 value `FFFFFFFFh` 時，原路可把 EAX 設成 `FFFFFFFFh`，`B550C7` 將其零擴成 RCX，`B550C9` 乘 `38h` 後仍到 `B550CD/D8`。這是原生錯位 aux 存取風險；改接八格須在首次 aux 讀寫前驗 map 實際命中、n 在有效 tracked 範圍，並維持 S、map、entity 的穩定性。tag `69h` 的 D 也需有八格上界與 property／pointer 儲存有效性。

tag `73h` 在 `B54F19` 把 **S_global** 放入 RCX，`B54F23` 直接呼叫 `606520`，RDX 指向 caller stack out-DWORD，R8D 是輸入 ID。`606520` 不是已完成的 `606AD0` network-index getter：它以 `[RCX+84h]` 的 D 逐筆讀 property 首 DWORD，經關聯 context map 比較 ID，命中時再讀該 ordinal 的 roster pointer 並輸出 entity ID；未命中輸出 global sentinel。這使它成為 `B54E00` 改接時**同一個必須處理的直接 callee**。

## 八格 sidecar 位點與有限 patch 前提

以下 B 使用既有共同布局：pointer `B+0`、primary `B+40h`、aux `B+3C0h`、property `B+580h`，每格 stride 分別為 `8/70h/38h/20h`。來源 `S+84h` dense count 與原 map header 仍留在 S。

| 函式與位點 | 原址／衍生指標 | 同一 B 的目標 |
| --- | --- | --- |
| `B5501C → B55030 → B5504A` | `S_registry+3A8h+ESI*20h` property 首 DWORD | `B+580h+ESI*20h` |
| `B55057`、`B550E9` | `S_registry+E8h+ESI*8` pointer | `B+ESI*8` |
| `B550CD`、`B550D8` | `S_global+2E0h+n*38h` aux DWORD | `B+3C0h+n*38h` |
| `B550FB` | `S_registry+3ACh+ESI*20h` property flag DWORD | `B+584h+ESI*20h` |
| `606559 → 606560 → 6065EA` | explicit `S+3A8h+RBX*20h` property 首 DWORD | `B+580h+RBX*20h` |
| `606622` | explicit `S+E8h+RBX*8` pointer | `B+RBX*8` |

完整 `606520` 原碼無直接 roster aux 存取。其關聯 context map 仍可能在容量零／查找耗盡時走到 `6065C3 cmp [RCX]` 的 null pointer；本輪沒有把任意 malformed map 宣稱可安全處理。

另固定的 `FD9BA0` 接 **RCX=caller out-DWORD、EDX=property 關聯 ID**。`7FFFh` 直接把 global `348456C` sentinel 寫出；其他 ID 以 global `346BF98` context 的 `F22EC8/D0/D4/D8` reverse-map 查找，再取 `F32F20+ordinal*18h` 首 DWORD 寫出，EAX 返回 out 指標。其完整 59 條原指令無 call、不解參 roster 四陣列，故只供後續真 helper 測試，**不需發射成 sidecar 改接候選**。容量零／probe 耗盡會走 `FD9C44 cmp [null]`，任意 malformed reverse-map 不在安全契約內。pool 的另一次有限核對確認 tag `115h` 的 `FD9AF0` 也不讀 roster；其他外部 callback 的資源、配置與重入效果仍未證。

若另做 emitter，必須保留外層 tag 順序及副作用，並使 `S_registry`、`S_global` 與 B binding 一致；若要將 aux 更新與 property bit 清除認定為同一 roster slot，還需有效 map 對 entity 的 `n==ESI` 一致性契約。入口或 tag 分支內 guard 只能在其執行點拒絕；先前 tag／helper 已造成的外部效果不能因此回滾。這份 replay 只證明固定原指令、布局與必要改接集合，不證明完整可安裝計畫、真實 registry 所有權、回呼同步或八人任務。
