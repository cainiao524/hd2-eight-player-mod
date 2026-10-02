# Player 資源建立路徑：4–7 sidecar／搬移安全邊界

本頁只讀固定 build `25480438` 的既有 JSON 證據，沒有呼叫遊戲程序、寫入記憶體、安裝 hook 或執行多人測試。重播器是 `verify_player_resource_patch_boundary_20261003.py`，輸出為 `player_resource_patch_boundary_verification_20261003.json`。

## 可重播結果

```text
checks: 18/18
verification_passed: true
direct_gate_literal_patch_safe: false
four_to_seven_sidecar_ready: false
relocation_path_ready: false
runtime_verified: false
multiplayer_verified: false
```

`verification_passed` 只表示固定證據與下列判定一致；它不表示遊戲已載入 Mod，也不表示第五至第八名玩家能加入。

## 已接通的靜態鏈

```text
network index 4..7
  └─ 0x1086460: cmp [owner+0x163ac+i*0x20], 4
       └─ jae 0x108624d（fallback ring）
            └─ 在此 root 不會到達 0xFDC140 或 0x608B60

index 0..3
  └─ content/entities/player
       └─ component index 239
            └─ callback table +0xF0C110
                 └─ 0x540920
                      └─ roster insertion family（原始四槽 guard）
```

因此只把 `0x1086460` 的立即值 `4` 改成 `8`，仍不會建立第五至第八名角色需要的資源、元件與 roster 回呼。`content/entities/player` 的參考清單是 `[3, 33, 41, 43, 226, 238, 239, 250, 260]`；這是資源 metadata 證據，不是目前加密安裝檔已在 runtime 執行的證據。

## 為何現有 sidecar 不能直接接上

- `0x540920` 等四個插入 body 有 `count+1 <= 4` 護欄、固定 pointer／primary／auxiliary 記錄寫入，而且 `0x172F790` 的 map helper 不會配置或擴容。
- map capacity 為零、探查失敗或滿表時，helper 會把 bucket pointer 設為零後仍寫入 `[4]`；在 record/count 已變更後再發生此情況不能安全回滾。
- property 階段把 network index 寫入 roster ordinal 記錄 `+0x3B4`。network index 與 roster ordinal 不是同一欄位，不能用一個 8 槽陣列代換所有索引。
- 已保存的 `ClientSidecar` 只是隔離資料模型。它沒有真實 player-creation callback，`executable=false`、`multiplayer_verified=false`，缺少 owner lifetime、callback ABI、map、cleanup 與 unwind 接線。

## 可接受的離線範圍

目前唯一安全的行為是讓 network index `4..7` 維持 fail-closed，繼續使用八槽資料模型作為待接線 sidecar。要產生 production hook，必須先完成：

1. 綁定 `0x1086460 → 0xFDC140 → 0x581320 → 0x540920` 的實際 callback ABI。
2. 將 tracked／dense／prefix 記錄、每筆 `0x20` bytes 的 property rows、ID→ordinal map 放到同一份 owner-keyed 八槽 backing。
3. 在任何 record/count 寫入前驗證 map free slot、duplicate ID、owner 存活期，並提供 rejection、離隊、重連的 cleanup／unwind。
4. 取得第五名 peer 的實機捕捉，再依序驗證六、七、八名帳號及完整任務生命週期。

完整重播：

```powershell
& 'C:\Program Files\Python312\python.exe' `
  five_player_feasibility_20260927\verify_player_resource_patch_boundary_20261003.py `
  --output five_player_feasibility_20260927\player_resource_patch_boundary_verification_20261003.json
```

本頁沒有把離線通過、顯示八個槽位或資源名稱匹配當成多人成功。
