# CChusky/hd2-tools Hook 與 Trampoline 靜態評估

日期：2026-10-02  
來源：`CChusky/hd2-tools`，tag `v1.0.3`，commit `5d509fad01ce4d16465d991363d30cb4a4f47dfe`  
範圍：只讀檢查公開原始碼；未存取遊戲程序、未注入、未修改遊戲根目錄。

## 結論

目前程式只能作為 Lua 呼叫觀察的研究參考，不能直接作為固定 build `25480438` 的 production bridge，也不能支撐第五至第八名 peer 的加入。

它沒有 `game.dll`、PlayFab、Party、peer、roster 或 player-index 入口。Hook 的目標是 `lua51.dll` 匯出的 `lua_pcall`，而不是遊戲的 session 或網路函式。倉庫內也沒有 build 指紋、模組 SHA-256 或 `lua_pcall` 前導位元組的固定版本核對。

## 實際入口與呼叫約定

`hook/hd2_raycast_hook.c` 的 `DllMain`（約 3785–3877 行）執行：

1. `GetModuleHandleA("lua51.dll")`。
2. `GetProcAddress(lua_dll, "lua_pcall")` 取得目標位址。
3. 以 `GetProcAddress` 取得部分 Lua 5.1 API。
4. 對 `lua_pcall` 寫入 inline jump。

宣告為：

```c
typedef int (*lua_pcall_t)(lua_State *L, int nargs, int nresults, int errfunc);
static int __fastcall hk_lua_pcall(lua_State *L, int nargs, int nresults, int errfunc);
```

在 Windows x64 上，`__fastcall` 不提供額外的替代 ABI；參數使用 Microsoft x64 calling convention：`RCX=L`、`RDX=nargs`、`R8=nresults`、`R9=errfunc`，整數返回值在 `RAX`。如果目標確實是相同 Lua 5.1 C API，這個原型相符。這只能證明呼叫介面，不能證明匯出實作、前導位元組或模組版本相符。

## Trampoline 的機器碼行為

`JMP_STUB_SIZE` 宣告為 14，但實際跳轉序列只寫入 12 bytes：

```asm
48 B8 <8-byte absolute address>  ; mov rax, imm64
FF E0                             ; jmp rax
```

`install_hook`（約 463–495 行）會：

- 用 `calc_hook_size(target, 14)` 依自寫的 `x64_instr_len` 累加完整指令。
- `VirtualAlloc(..., PAGE_EXECUTE_READWRITE)` 建立 256-byte trampoline。
- 直接 `memcpy` 被覆蓋的前 N bytes。
- 在 trampoline 尾端寫 `mov rax, original+N; jmp rax`。
- 以同一個 12-byte jump 覆蓋原函式，剩餘 bytes 寫 `CC`。

Trampoline 沒有做指令重定位。以下任何指令若落在前 N bytes，直接複製到新位址後都可能改變語意：

- `E8 rel32`、`E9 rel32`、`EB rel8`、`70–7F rel8`、`0F 80–8F rel32`：相對分支的基準變成 trampoline 位址。
- `ModRM mod=00, rm=101` 或等效 SIB：RIP-relative `disp32` 的基準變成 trampoline 位址。

具體反例：

- `48 8B 05 xx xx xx xx` 是 7-byte `mov rax,[rip+disp32]`；長度可能算對，但複製後必須重算 `disp32`。
- `E8 xx xx xx xx` 是 5-byte `call rel32`；複製後必須把目標轉成 trampoline 位置的相對位移。
- `48 81 EC 28 01 00 00` 實際為 7-byte `sub rsp,imm32`，decoder 把 `REX.W+0x81` 的立即數當成 8 bytes，回傳 11，可能把下一條指令的一部分一併複製。
- `48 F7 C1 00 00 00 80` 實際為 7-byte `test rcx,imm32`，decoder 以 `REX.W+0xF7` 回傳 11。
- `0F 3A` 類三字節 opcode 的立即數沒有完整處理；VEX/EVEX (`C4`、`C5`、`62`) 未支援。

因此，沒有 `25480438` 對應 `lua51.dll` 的實際前 32 bytes 及 relocation 檢查，就不能判定這個 trampoline 可以工作。即使某次前導剛好沒有上述指令，也不能推廣到下一個版本。

## 其他執行期風險

- 寫入前沒有暫停可能正在執行目標函式的其他執行緒，也沒有原子 patch 或 transaction rollback。
- 沒有檢查目標是否已被另一個 hook 改寫。
- 保護頁範圍固定為目標所在頁起始後 `0x2000` bytes，沒有依實際跨頁範圍保存和還原權限。
- `DLL_PROCESS_DETACH` 只呼叫 `hd2_addon_detach()`；沒有恢復原始 `lua_pcall`，卸載 DLL 後目標仍可能跳到已卸載的 `hk_lua_pcall`。
- trampoline 使用 `PAGE_EXECUTE_READWRITE`，沒有建立後改成 RX，也沒有處理 CFG/CET 或其他控制流程保護。
- `hk_lua_pcall` 每次 Lua 呼叫都做計數、日誌、Lua API、`exec_lua`、GUI 與共享記憶體處理；沒有 thread-local recursion guard。
- `__try/__except` 把 native fault 轉為 `-1`，但不能保證 Lua stack 或 Stingray 狀態在異常後仍然一致。
- `DllMain` 內做檔案日誌、shared memory、addon attach、模組查找與 inline patch，超出 loader-lock 下應保持最小的初始化範圍。

## 觀察能力與八人需求的差距

`overlay/shm_proto.h` 的資料通道主要是 hit、box、GUI projection 和 component explorer。結構中雖有 `cmd_addr`、`cmd_type`、`cmd_val32/cmd_valf` 欄位，但沒有權限驗證；這是任意目標位址寫入介面的風險，不是 session API。原始碼沒有：

- PlayFab lobby 或 Party network 呼叫。
- peer admission、confirmed-peer 或 host migration。
- roster insertion/removal 或 player index assignment。
- Player Clone 建立、NetworkOverride 或 entity replication 寫入。

所以即使 Lua 觀察 hook 能在固定版本穩定執行，也只能觀察 Lua 層可見資料，不能使第 5–8 名玩家被 session 接受。

## 若只做固定版本唯讀觀察，必須先重寫的契約

在任何執行期驗證前，至少需要：

1. 核對 `helldivers2.exe`、`lua51.dll`、`game.dll` 的 PE timestamp、`SizeOfImage` 和完整 SHA-256。
2. 核對 `lua_pcall` 所屬模組、匯出位址與前 32 bytes；不符時 fail-closed。
3. 使用完整 x64 decoder，對 RIP-relative 和所有相對分支做 relocation；無法重定位時拒絕安裝。
4. 保存原始 bytes、頁面權限與 hook 狀態；以安全的執行緒協調方式 patch，並提供可靠 unhook/cleanup。
5. Hook 熱路徑只寫入固定大小的 TLS/ring-buffer event，加入 recursion guard；由非遊戲執行緒消費事件。
6. 不使用 anti-cheat bypass、遠端執行緒注入或任意 raw-address write 作為正式介面。

完成這些條件後仍只能達到「固定 build 的 Lua 觀察器」級別，不能當成八人聯機完成證據。

## 授權與來源風險

倉庫使用 PolyForm Noncommercial License 1.0.0，允許個人、研究、測試與非商業用途；修改和再分發必須保留授權條款及 `Required Notice: Copyright CChusky (https://github.com/CChusky)`。`watcher.c` 的注入、`OpenProcess`、`WriteProcessMemory`、`CreateRemoteThread` 及 direct syscall 路徑另有反作弊和服務條款風險，不應放入 production bridge。

