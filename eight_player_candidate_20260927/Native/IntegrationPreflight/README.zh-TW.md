# 八人跨元件 preflight 契約

`ep_eight_preflight.dll` 是 Bridge、ClientSidecar、PlayerResource、ClientReplication、PlayerCreationGate、SessionMembers 與 OfficialPlugin 之間的離線一致性閘門。它只接收各元件已經完成的容量與 callback 狀態，不解析遊戲位址、不呼叫 `game.dll`、不寫入程序，也不宣稱多人成功。

通過條件固定為：

- Steam build `25480438` 與契約版本一致；
- 所有七個容量回報都是 `8`；
- 各元件的 native callback provider 都已準備；
- network index 來自權威 Session/Party allocator；
- compact roster ordinal 與 stable network index 分開保存；
- remove/reconnect 保留洞位；
- Host 與 client 使用同一 build。

任一條件失敗都返回具體 status 並設置 `failure_mask`，不會產生可安裝 patch。這讓 Bridge 在接近 native callback 前先拒絕「某一側仍是四槽」或「把 ordinal 當 index」的部分配置。

建置：

```powershell
cmd /c build_x64.bat
```

`ep_eight_preflight_synthetic_passed` 只代表離線一致性檢查通過；`runtime_verified=false`、`installable=false`、`multiplayer_verified=false`。
