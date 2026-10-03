# 2026-10-03 live capture rerun

本次只读重读针对固定 build 25480438、PID 36536。dispatcher 与 session snapshot 的镜像哈希、事件命中签名和只读标志均与既有证据一致；实时上下文仍是单一 peer，文档化 roster 仍只有 4 个槽位，槽位 4..7 继续保持合约外。

私有内存 registry 扫描在进程消失后没有产生输出文件，已保存为 `live_private_registry_20261003_rerun.failure.json`。该结果按 fail-closed 处理，不推断 registry 阴性，也不推断 peer admission、player creation、安装或八人联机成功。

收据：`live_capture_rerun_verification_20261003.json`。
