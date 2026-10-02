# 第四次 EXE `0x1AE380` 限定擷取

## 授權與範圍

本檔記錄使用者在 2026-10-02 明確允許後完成的第四次唯讀擷取。操作只讀取一个已核对的 Helldivers 2 进程：

- Steam build：`25480438`
- 进程：`helldivers2.exe`，PID `40552`
- EXE：`F:\Game\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe`
- `game.dll`：`F:\Game\Steam\steamapps\common\Helldivers 2\data\game\game.dll`
- 没有注入、函数调用、内存写入、文件修改、Mod 安装或多人测试。

读取范围由既有 `spawn_callee_probe.py` 固定：EXE `0x1AE380` 起始的 `4096` bytes，前后各读一次；并核对已保存的 wrapper caller、PE 身份、EXE／`game.dll` 文件杂凑及模块清单。总读取量为 `24,868` bytes。

首次直接启动 EXE 的短暂进程（PID `43132`）在模块枚举前退出，限定脚本返回 `Expected exactly one loaded game.dll`，没有产生输出文件。随后通过 Steam `-applaunch 553850` 启动并得到稳定进程 PID `40552`，第二次执行才完成本报告所列擷取。

## 原始证据

原始 JSON：[spawn_callee_live_20261002_4.json](spawn_callee_live_20261002_4.json)

| 项目 | 值 |
| --- | --- |
| 文件 SHA-256 | `7dcdfb277c84ec72d02ff8b23c6acf3f5a0756ea9f83b6b3e3f4ffb48fe9812f` |
| 文件大小 | `10,927` bytes |
| EXE SHA-256 | `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06` |
| `game.dll` SHA-256 | `2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e` |
| loaded address | `0x7ff666eee380` |
| module RVA | `0x1AE380` |
| 4 KiB bytes SHA-256 | `68505f365c5d244182982cb26d688f45ab7fa436948def62b34c72b63b38f93d` |
| 重读结果 | 相同 |

## `6054F0`／`1277920` 入口核对

离线分析：[spawn_callee_live_20261002_4_analysis.json](spawn_callee_live_20261002_4_analysis.json)

对捕捉到的 4096 bytes 解码得到 1067 条指令、34 个直接 call 和 96 个直接跳转。没有发现直接 call、跳转或立即数引用指向 game.dll 的 `0x6054F0` 或 `0x1277920`。

相关既有证据仍保持独立：

- `6054F0` body SHA-256：`6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a`
- `1277920` body SHA-256：`aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca`

因此这次擷取确认了 EXE `0x1AE380` 的加载后代码身份，缩小了资料缺口，但没有证明它会调用 roster 的 `6054F0` 或 mask reader 的 `1277920`，也没有证明它是玩家分配器。

## 限制

- 4096 bytes 是固定范围的 code prefix，不是经异常表或完整控制流证明的函数边界。
- 间接调用、异常路径、运行时函数指针、跨模块 callback 和返回对象没有追踪。
- `runtime_capture=true` 只表示完成限定读取；`atomic_snapshot=false`。
- `eight_player_verified=false`；不能把本次证据当作五至八人联机成功。
