# device-api-validation-lab

用于学习和实践 System Test / Validation，对一个模拟工业设备 HTTP API 进行真实 HTTP 自动化测试。

## 当前技术栈

- Python
- pytest
- requests
- Flask

## 当前里程碑与状态

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M1 — HTTP Baseline | HTTP 健康检查 | **Completed / Verified** |
| M2.1 | 设备连接 | **Completed / Verified** |
| M2.2 | 寄存器读取 | **Completed / Verified** |
| M2.3 | 寄存器写入、读回验证及寄存器状态恢复 | **Completed / Verified** |
| M2.4 | 设备业务断开连接、连接状态隔离及对应自动化测试 | **Completed / Verified** |
| M3.1 | HTTP 服务中断与恢复的自动化验证 | **Completed / Verified** |
| M3.2 | HTTP 请求读取超时、正常慢响应及异常响应验证 | **Completed / Verified** |

验收依据：以上阶段均由项目维护者完成真实 HTTP 验收。M1 的正向、故障、恢复记录以及 M2.4、M3.1、M3.2 的验收证据见下文。

## 目录结构与职责

```text
device-api-validation-lab/
├── configs/
│   └── test_env.json          # 本地 DUT 地址和请求 timeout
├── dut/
│   └── app.py                 # Flask DUT，进程内存中模拟业务连接与寄存器
├── src/
│   ├── __init__.py
│   └── device_api_client.py   # 发送真实 HTTP 请求，返回原始 Response
├── tests/
│   ├── conftest.py            # 配置校验、Client 创建及 Session 清理
│   ├── smoke/
│   │   └── test_health.py     # /health 状态码和 JSON 内容断言
│   ├── api/
│   │   ├── conftest.py        # 连接状态前置条件、业务断开及寄存器原值恢复
│   │   ├── test_connect.py    # 连接、重复连接及连接后的健康检查
│   │   ├── test_disconnect.py # 断开、重复断开及断开后的接口行为
│   │   ├── test_read.py       # 寄存器读取、参数校验及地址不存在场景
│   │   └── test_write.py      # 写入读回、边界值及非法写入不改变原值
│   └── recovery/
│       ├── conftest.py        # 独立 18001 DUT 子进程的启动、就绪判断与清理
│       ├── test_response_timeout.py # 读取超时、正常慢响应、超时后业务及 HTTP 500
│       └── test_service_recovery.py # 真实服务中断、HTTP 恢复及业务重新连接
├── reports/
│   └── .gitkeep              # 报告输出预留目录，当前不自动生成报告
├── logs/                    # Recovery 运行时生成子进程 stdout/stderr 日志
│   └── .gitkeep              # 保留目录，生成的 *.log 由 .gitignore 排除
├── pytest.ini                # 测试发现路径、输出选项和 markers
├── requirements.txt          # 直接依赖，当前未固定版本
├── .gitignore                # 缓存、虚拟环境及生成文件忽略规则
└── README.md
```

Smoke/API 功能测试的 HTTP 配置统一读取自 `configs/test_env.json`，当前 `base_url` 为 `http://127.0.0.1:8000`，`timeout` 为 2 秒。配置路径根据 `tests/conftest.py` 自身位置定位；具体功能测试不硬编码地址或 timeout。

Recovery 测试使用独立的 `127.0.0.1:18001` DUT，由 `tests/recovery/conftest.py` 管理端口、有限的请求 timeout 和启动等待上限，不使用功能测试配置中的 8000 服务执行中断与慢响应实验。测试专用模拟接口仅注册在 18001 子进程的启动脚本中，不修改正式的 `dut/app.py` 或 8000 DUT。

## 安装依赖

以下命令均在项目根目录执行，使用已存在的 Conda 环境：

```powershell
conda activate device-api-val
python -m pip install -r requirements.txt
```

项目维护者已确认该环境可用，验收时 Python 为 3.11.17，pytest 为 9.1.1。`requirements.txt` 当前仅列出 pytest、requests 和 Flask，尚未固定版本；重新安装依赖不保证得到与验收环境完全相同的版本。

## 启动 DUT

在第一个终端激活上述环境后执行：

```powershell
python dut/app.py
```

DUT 监听 `127.0.0.1:8000`，启动参数为 `debug=False`、`use_reloader=False`。

## 执行 Smoke Test

保持 DUT 运行，在第二个终端进入项目根目录、激活同一环境后执行：

```powershell
python -m pytest -m smoke
```

测试通过 fixture 获取 Client，发送真实 HTTP 请求，不使用 mock，不自动重试，也不因 DUT 未启动而跳过。Client 负责发送请求；测试负责判断响应是否符合契约。

## 执行功能、Recovery 与全量回归

以下命令均在项目根目录、同一环境中执行：

| 命令 | 测试范围 | DUT 准备条件 |
| --- | --- | --- |
| `python -m pytest -m "smoke or api"` | 原有 29 条功能测试 | 需要提前通过 `python dut/app.py` 启动 8000 端口 DUT |
| `python -m pytest -m recovery` | 6 条 Recovery 测试 | fixture 自动启动、停止并清理独立 18001 DUT；启动前该端口应空闲 |
| `python -m pytest` | 全部 35 条测试 | 需要提前启动 8000 端口 DUT；Recovery fixture 自行管理 18001 DUT |

当前正式测试共 35 项，由 29 项 Smoke/API 功能测试和 6 项 Recovery 测试组成；Recovery 包含 M3.1 的 2 项及 M3.2 新增的 4 项。Recovery fixture 只清理自己创建的子进程，不停止原有 8000 服务。各阶段实际运行结果见下文。

## /health 接口契约

- 请求：`GET /health`
- 正常响应：HTTP `200`
- JSON 响应：`{"status": "ok"}`

测试保留两个断言：`response.status_code == 200` 和 `response.json()["status"] == "ok"`。

## M1 实测记录

以下记录来自项目维护者已完成的人工验收。

Flask DUT 正常监听时，使用 curl 请求 `GET /health`，已确认返回 HTTP `200` 和 `{"status":"ok"}`。

三个阶段均使用同一命令：`python -m pytest -m smoke`。

| 阶段 | 人工操作与 DUT 状态 | 实测结果 | 结论 |
| --- | --- | --- | --- |
| 正向 | 启动 DUT，服务正常运行 | `1 passed` | /health 的真实 HTTP 响应符合断言 |
| 故障 | 故意停止 DUT，再次执行测试 | `1 failed`，异常为 `requests.exceptions.ConnectTimeout` | 测试检测到服务不可达，符合故障实验预期 |
| 恢复 | 人工重新启动 DUT，再次执行测试 | `1 passed` | 服务恢复后，同一测试重新通过 |

故障阶段出现 FAILED 是故意停止 DUT 后的预期检测结果；正常测试场景要求 DUT 运行并且测试通过。M1 的恢复阶段由人工重启服务，当时尚未实现由测试程序控制的服务重启与恢复验证；后续 M3.1 补充了这部分自动化测试。上述 ConnectTimeout 是本次实际观察到的异常，不保证所有环境下服务不可达时都产生同一种连接异常。

## M2.4 实测记录

以下结果均来自项目维护者完成的真实验收，记录的是实际观察结果。

| 步骤 | 操作与条件 | 实测结果 |
| --- | --- | --- |
| 1 | 调用 `/connect` | HTTP `200`，业务连接成功 |
| 2 | 已连接状态下读取寄存器 100 | HTTP `200` |
| 3 | 调用 `/disconnect` | HTTP `200`，业务断开成功 |
| 4 | 断开后读取 | HTTP `409`，`{"error":"not_connected"}` |
| 5 | 断开后调用 `/health` | HTTP `200` |
| 6 | 执行 `python -m pytest -m "smoke or api"` | `29 passed in 2.74s` |
| 7 | 回归结束后，不重启 DUT，读取寄存器 100 | HTTP `409`，处于未连接状态 |
| 8 | 人工重新连接后读取寄存器 100 | 得到原值 `1234` |

这些结果确认了本次回归结束后的业务连接状态和寄存器 100 的恢复结果，不代表所有异常情况下都能保证清理成功。

## M3.1 实测记录

M3.1 在 `tests/recovery/` 中实现 function-scope 的 `recovery_dut` fixture，使用 `subprocess.Popen` 和 `sys.executable` 启动监听 `127.0.0.1:18001` 的独立 Flask DUT。启动后轮询 `/health` 判断服务就绪，并核对本次子进程的身份标记，区分测试 DUT 与其他服务。

两条测试通过真实 HTTP 请求验证服务中断与恢复：停止受管子进程并确认退出后，使用 `pytest.raises(requests.exceptions.ConnectionError)` 检测连接故障；重新启动子进程后，依次验证 HTTP 服务恢复、业务尚未连接、显式调用 `/connect` 后读取恢复。所有请求设置有限 timeout。

以下结果来自项目维护者已完成的真实验收：

| 验证项目 | 实测结果 |
| --- | --- |
| 人工停止 Flask | curl 无法连接，requests 出现 `ConnectionError` |
| 人工重启 Flask | `/health` 恢复 HTTP `200`；未连接读取返回 `409`；重新连接后读取返回 `200` |
| `python -m pytest -m recovery` | `2 passed, 29 deselected` |
| Recovery 结束后的 18001 端口检查 | Listen 状态检查无输出，当次检查未发现该端口处于监听状态 |
| 原有 Smoke/API 回归 | `29 passed` |
| `python -m pytest` 完整回归 | `31 passed in 8.00s`，无 FAILED 或 ERROR |

验收过程中曾出现 API fixture 连续 ERROR。排查确认原因是 8000 端口 DUT 未启动；启动 Flask 后回归恢复正常，这是已解决的测试环境问题。运行功能测试或全量回归前仍需提前启动 8000 DUT。

## M3.2 实测记录

M3.2 在独立 18001 DUT 的启动脚本中新增 `/__test__/slow` 和 `/__test__/server-error`，保留原有进程身份标记与清理机制。慢接口在返回响应前执行 1 秒 `sleep`；错误接口直接返回 HTTP 500，不终止 Flask。子进程使用 `threaded=True`，慢请求处理期间其他请求仍可并发处理。

本阶段新增四条真实 HTTP 测试，均使用有限 timeout、关闭环境代理并清理 Session：

| 场景 | 验证内容 |
| --- | --- |
| ReadTimeout | 服务已就绪时，以 0.2 秒 timeout 请求慢接口，精确检查 `requests.exceptions.ReadTimeout` |
| 正常慢响应 | 对同一慢接口使用 3 秒 timeout，检查 HTTP `200` 和 `{"status":"ok","delay_seconds":1.0}` |
| 超时后业务仍可用 | 确认同一子进程仍运行，使用新 Session 检查 health、连接、读取寄存器 100 为 1234 及断开，全程不重启 DUT |
| HTTP 500 原始响应 | 检查原始 Response、HTTP `500` 和 `{"error":"simulated_internal_error"}`，不使用 `raise_for_status()`，随后确认 health 返回 `200` |

以下结果来自项目维护者已完成的真实验收：

| 验证项目 | 实测结果 |
| --- | --- |
| M3.2 新增四条测试 | `4 passed` |
| 全部 Recovery 测试 | `6 passed` |
| 18001 端口检查 | 未发现遗留 Listen 状态 |
| `python -m pytest` 完整回归 | `35 passed in 13.54s` |

这些模拟接口仅存在于独立的 18001 测试 DUT，不改变正式 8000 DUT 的接口。固定 1 秒延迟模拟的是服务端处理缓慢，并非真实网络丢包；客户端超时后，服务端可能继续处理原请求。测试区分了读取超时异常与已经收到的 HTTP 500 响应，没有加入自动重试。

## 测试状态管理

Smoke/API 功能测试使用 pytest 的 setup / call / teardown 管理状态：

- setup：创建 HTTP Client；按测试需要建立已连接或未连接前置条件。写入测试额外读取并保存寄存器 100 的实际原值。
- call：执行测试函数，验证 HTTP 响应和业务行为；写入成功后再通过 `/read` 验证实际值。
- teardown：按 fixture 依赖关系的逆序执行清理，并检查清理响应。测试函数发生 AssertionError 后，已进入 yield 的 fixture 仍会尝试清理；清理失败会明确暴露。

写入测试的 fixture 依赖为：

```text
config → api_client → connected_client → preserved_register100 → test_write
```

对应的 teardown 顺序必须是：

```text
恢复寄存器 100 的原值并读回确认
→ 断开设备业务连接并确认
→ 关闭 HTTP Session
```

寄存器恢复使用测试开始前实际读取的原值，而非固定写入 1234。`connected_client` 和 `disconnected_client` 都在 teardown 中通过 `/disconnect` 清理业务状态；Session 统一由上一级 `api_client` fixture 关闭。

`disconnect()` 改变 DUT 中的业务连接状态，不重置寄存器，也不停止 Flask 服务；`close()` 释放本地 HTTP Session，不能代替业务断开。

Recovery 测试独立管理进程生命周期：测试调用 fixture 提供的启动、停止和重启方法，fixture 使用 yield/finally 在 teardown 中清理自己创建的子进程。停止时先 `terminate()` 并等待退出，超时后 `kill()` 再等待；HTTP Client 通过上下文清理。子进程 stdout/stderr 写入 `logs/recovery_dut_*.log`，启动失败时报告日志路径和诊断内容。该流程不操作 8000 DUT。

## 已验证能力与尚未实现的功能

M1～M3.2 已验证：

- 最小 Flask DUT 提供 /health HTTP 接口。
- Smoke/API 的 requests Client 通过配置地址发送请求，并显式传递 timeout。
- pytest fixture 提供配置、Client 及 Session 清理机制；Smoke Test 对真实响应进行断言。
- 在人工故障实验中检测 DUT 不可达，并在人工重启 DUT 后重新通过测试。
- `/connect` 建立业务连接，`/read` 读取寄存器并校验地址。
- `/write` 校验地址和数值，支持 0～65535 的边界值；通过读回验证写入结果，并检查非法写入未改变原值。
- 写入测试逐项保存、恢复寄存器 100 的原值；M2.3 的故意 AssertionError 实验中，teardown 未报告 ERROR，不重启 DUT 人工读回为 1234。本次恢复成功，临时实验文件已删除。
- `/disconnect` 具有重复调用的幂等行为；断开后读写返回 409，健康检查保持可用，重新连接后可以读取。
- 通过 fixture 在各 API 测试中设置业务连接前置条件并清理状态，寄存器恢复先于业务断开，业务断开先于 Session 关闭。
- 通过独立 18001 DUT 子进程执行真实服务中断实验，确认连接故障，并在测试程序主动重启后分别验证 HTTP 恢复和业务重新连接。
- Recovery fixture 管理子进程清理；本次验收结束后的 18001 Listen 检查无输出，原有功能测试和全量回归均通过。
- 在真实 HTTP 请求中区分 ReadTimeout、等待时间足够时的正常慢响应与 HTTP 500 原始响应；单次读取超时后，同一 DUT 进程的健康检查和业务仍可用。

尚未实现：

- Client 自动重试、自动重连以及 DUT 自主故障检测与自动恢复。
- 数据持久化及其验证；当前业务状态和寄存器仍在进程内存中，重启后重新初始化。
- 真实网络丢包、网络层延迟注入及连接建立超时验证。
- CI 集成及自动测试报告生成。
- 完整的系统级状态隔离及多进程并发隔离。

M3.1 的服务恢复由测试程序按步骤主动重启 DUT，并显式调用 `/connect`，不代表自动重连、设备自主恢复、数据持久化或真实网络丢包测试已经实现。启动时的 health 轮询仅用于判断进程就绪，不是业务请求的自动重试。

M3.2 已验证响应返回前等待过久导致的读取超时，不代表连接建立超时、真实网络丢包或数据持久化验证已经实现；当前仍未加入自动重试。

M2.4 的 `/disconnect` 只改变业务连接状态；M3.1 则实际停止并重启受管子进程。原有 8000 功能测试仍共享 DUT 进程，Recovery 使用逐项管理的独立 18001 进程，但固定端口并不提供多进程并发隔离。其他进程同时操作 DUT 时仍可能产生竞争；进程异常或网络中断时，teardown 不能保证所有状态都恢复成功。

已完成的中断与恢复验证以及 fixture 清理，不代表上述尚未实现的能力已具备。
