# GameSession underlying vtable bounded observation

這個候選把固定 build `25480438` 的 underlying GameSession object 只讀契約保存成可合成驗證的 C++ header。它和公開 `GameSessionCApi` wrapper table 分開處理，使用保存的固定函式前綴作版本門控：

- slot `0x70` → `helldivers2.exe` 固定 RVA `0x292BE0`，讀取 object `+0x138` 的 bounded count。
- slot `0x78` → `helldivers2.exe` RVA `0x292BF0`，確認 record table `+0x140`、每筆 `0x30` bytes 的 stride。
- slot `0x98` → `helldivers2.exe` RVA `0x292CC0`，讀取 object `+0x130` 的 opaque owner pointer。

`ep_session_vtable_snapshot.h` 不呼叫任何 vtable function；caller 提供 bounded reader，模組只核對 function pointer、保存的 code prefix、count `<=8`、record pointer 唯一性，並複製最多八筆 `0x30` bytes opaque record。兩次讀取不一致、版本漂移、空表、超過八筆或重複 record 都 fail-closed。

```powershell
cmd /c build_vtable_snapshot_x64.bat
```

`session_vtable_snapshot_synthetic_passed` 只證明合成映像的版本門控和 bounded copy。opaque record 尚未解碼成 PeerId、network index、玩家或 Party member；沒有呼叫 `add_peer`、`remove_peer`、`create_game_object`，也沒有接到 player creation 或 client replication。正式狀態仍為 `installable=false`、`multiplayer_verified=false`。
