# 第五人原生接納鏈：固定 build 邊界審查

本頁只使用倉庫內保存的 Steam build `25480438` 反組譯、固定 RVA capture 與既有 ABI 註記。沒有讀取遊戲程序、寫入模組、安裝 hook、修改遊戲目錄或執行網路測試。機器可讀的完整邊界在 [`native_peer_admission_bridge_boundary_20261002.json`](native_peer_admission_bridge_boundary_20261002.json)，核對器與報告在 [`verify_native_peer_admission_bridge_boundary.py`](verify_native_peer_admission_bridge_boundary.py) 和 [`verification/native_peer_admission_bridge_boundary_verification_20261002.json`](verification/native_peer_admission_bridge_boundary_verification_20261002.json)。

## 最小必要鏈

| 階段 | 固定 RVA | 已核對的 ABI／指令邊界 | 生產改接要求 |
|---|---|---|---|
| Host join | `0x108BC70` | RDX 是含 count `+0x18` 及 qword member list `+0x08` 的 join record；root 由六段相連 unwind fragment 覆蓋 | 入口可用普通 trampoline 候選，但 stolen length、RCX owner dataflow 與 continuation 仍要由固定 site 核定 |
| Capacity | `0x108C18F` | 32-byte prefix 後在 `0x108C1B5` 執行 `mov ecx,4`；原分支 continuation 是 `0x108C1C1/0x108C1DB` | 必須保存 `r12/r13/r14/rbp/r9`、stack locals、分支與 unwind；不能只改立即數 |
| Index allocator | `0x108C3D8` | `0x108C3D8..0x108C3E5` 只掃 `host+0x100` 四個 flags；`0x108C3EE` 設旗標，`0x108C3FB` 寫 `[member+0x14]` | 以 sidecar 分配 `0..7`，保留 hole／generation 與完整 loop failure continuation |
| Confirmed sender | `0x108C760` | host `+0x20` 起、stride `0x38`、四筆；`slot+0x14` 是 32-bit player index；`0x108C923 → 0xBE4910`，event hash `0x4804FCF4` | 八槽 sidecar 必須保留本地 peer 分支與遠端 wrapper 的五欄順序 |
| Confirmed receiver | `0xBABA80 → 0xB90B20` | receiver 讀 `+8,+18,+28,+38,+48` 五欄；第四個欄位進 client append | 需先閉合 runtime hash→callback registry，再把資料送至 sidecar |
| Client append | `0xB90B20` | `client+0xC8` count、`client+0xD0` record、stride `0x20`、index `record+0x14`；第五筆從 `client+0x150` 開始，會覆蓋相鄰 live 區域 | 不能直接放大 count；必須改 append、remove、reset 及 owner-relative reader |
| Player creation | `0x1086460` | `cmp [rdx+r8+0x163AC],4`，`jae 0x108624D`；只有 `0x108646F` 路徑到 `0x10868BF/0x10868D7` resource calls | index `4..7` 需等效角色建立、handle、roster binding 與 cleanup；改 `jae` 不足 |
| Cleanup/migration | `0x108D190`, `0x1089720`, `0x1087540`, `0x10845B0` | host peer/flags/large/pending 及 client remove/reset 均有四筆或固定 `0x80` 清理範圍 | sidecar owner lifetime、回呼重入、離隊／重連／host migration 必須同一套回滾契約 |

## 目前結論

這條鏈已經足以定義第五人的最小 native bridge 工作面，但還沒有可安全套用的 production patch。最關鍵的未閉合資料是：

1. `0x108C18F` 與 `0x108C3D8` 中段 stub 的完整 register／stack／unwind／continuation 契約。
2. `0x4804FCF4` 的 runtime receiver binding；保存的 send wrapper 與 `0xBABA80` 形狀吻合，但沒有把可寫 dispatcher table 接上。
3. host/client sidecar 的真實 owner 生存期、異步回呼、清理、migration 與失敗恢復。
4. `0x1086460` 接受 `4..7` 後的 resource handle、player component、roster 與後續 cleanup。
5. 第五獨立帳號的實際 session 結果，以及同任務角色可見、移動、戰鬥、離隊與重連紀錄。

靜態核對器 **4/4 通過**，但報告仍明確是 `executable=false`、`live_ready=false`、`multiplayer_verified=false`。這些結果只確認固定資料與阻擋條件，沒有把 synthetic sidecar 或離線 fixture 當成多人成功。
