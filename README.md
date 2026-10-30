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
| M3.3 | 写入超时后的状态一致性与幂等性验证 | **Completed / Verified** |
| M3.4 | 故障证据记录与诊断 | **Completed / Verified** |
| M3.5 | 只读健康检查的有限重试与恢复策略验证 | **Completed / Verified** |

验收依据：以上阶段均由项目维护者完成真实 HTTP 验收。M1 的正向、故障、恢复记录以及 M2.4、M3.1、M3.2、M3.3、M3.4、M3.5 的验收与实验记录见下文。

M3.5 已完成验收及 README 同步，M3.3～M3.5 的第二次里程碑 Git 提交待项目维护者亲自统一进行，当前尚未提交。

## 目录结构与职责

```text
device-api-validation-lab/
├── configs/
│   └── test_env.json          # 本地 DUT 地址和请求 timeout
├── dut/
│   └── app.py                 # Flask DUT，进程内存中模拟业务连接与寄存器
├── src/
│   ├── __init__.py
│   ├── device_api_client.py   # 发送真实 HTTP 请求，返回原始 Response
│   └── health_retry.py        # 独立的只读健康检查有限重试函数
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
│       ├── conftest.py        # 独立 DUT、寄存器保护及证据 fixture/hook
│       ├── evidence.py        # 结构化 JSON、异常摘要及真实阶段结果汇总
│       ├── test_fault_evidence.py # ReadTimeout、HTTP 500 和 ConnectionError 证据
│       ├── test_health_retry.py # 有限重试、停止条件、实际请求次数与证据
│       ├── test_response_timeout.py # 读取超时、正常慢响应、超时后业务及 HTTP 500
│       ├── test_service_recovery.py # 真实服务中断、HTTP 恢复及业务重新连接
│       └── test_write_consistency.py # 写入超时后的实际状态、同值赋值幂等及读回
├── reports/
│   ├── .gitkeep              # 保留报告输出目录
│   └── evidence/             # 运行生成的 JSON 证据，由 .gitignore 排除
├── logs/                    # Recovery 运行时生成子进程 stdout/stderr 日志
│   └── .gitkeep              # 保留目录，生成的 *.log 由 .gitignore 排除
├── pytest.ini                # 测试发现路径、输出选项和 markers
├── requirements.txt          # 直接依赖，当前未固定版本
├── .gitignore                # 缓存、虚拟环境及生成文件忽略规则
└── README.md
```

Smoke/API 功能测试的 HTTP 配置统一读取自 `configs/test_env.json`，当前 `base_url` 为 `http://127.0.0.1:8000`，`timeout` 为 2 秒。配置路径根据 `tests/conftest.py` 自身位置定位；具体功能测试不硬编码地址或 timeout。

Recovery 测试使用独立的 `127.0.0.1:18001` DUT，由 `tests/recovery/conftest.py` 管理端口、有限的请求 timeout 和启动等待上限，不使用功能测试配置中的 8000 服务执行中断、慢响应、延迟写入响应与有限重试实验。测试专用模拟接口仅注册在 18001 子进程的启动脚本中，不修改正式的 `dut/app.py` 或 8000 DUT；重试场景的实际请求次数通过测试专用统计接口核对。

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
| `python -m pytest -m recovery` | 20 条 Recovery 测试 | fixture 自动启动、停止并清理独立 18001 DUT；启动前该端口应空闲 |
| `python -m pytest` | 全部 49 条测试 | 需要提前启动 8000 端口 DUT；Recovery fixture 自行管理 18001 DUT |

当前正式测试共 49 项，由 29 项 Smoke/API 功能测试和 20 项 Recovery 测试组成；Recovery 包含 M3.1 的 2 项、M3.2 的 4 项、M3.3 的 4 项、M3.4 的 3 项及 M3.5 新增的 7 项。故意失败实验的临时文件已删除，不计入正式测试。Recovery fixture 只清理自己创建的子进程，不停止原有 8000 服务。各阶段实际运行结果见下文。

单独运行 M3.5 的 7 项测试：`python -m pytest -v tests/recovery/test_health_retry.py`。这些测试由 fixture 管理独立 18001 DUT，不需要提前启动 8000 服务。

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

## M3.3 实测记录

M3.3 仅在独立的 18001 Recovery DUT 中新增测试专用 `POST /__test__/write-delayed`，不改变正式 8000 DUT 的业务代码。该接口直接复用 `dut.app.write()` 的参数校验与实际寄存器写入逻辑，使用同一子进程内的寄存器状态；成功写入后再延迟 1 秒返回原响应，写入失败则直接返回原错误响应。

本阶段四条真实 HTTP 测试验证以下场景：

| 场景 | 验证内容 |
| --- | --- |
| 延迟写入触发读取超时 | 初始值为 1234，写入 4321，使用 0.2 秒 timeout 精确检查 `requests.exceptions.ReadTimeout` |
| 超时后实际写入已生效 | 不重启 DUT，通过另一次正常 `/read` 请求确认寄存器 100 为 4321，并确认同一子进程仍在运行 |
| 重复同值赋值的最终状态效果 | 首次延迟写入超时后读回 4321，再显式通过正常 `/write` 写入相同值，读回仍为 4321 |
| 等待时间足够时成功返回 | 使用 3 秒 timeout，检查 HTTP `200`、正确的写入 JSON，并读回确认值为 4321 |

以下结果来自项目维护者已完成的真实验收：

| 验证项目 | 实测结果 |
| --- | --- |
| M3.3 新增四条测试 | 全部通过 |
| `python -m pytest` 完整回归 | `39 passed in 19.80s` |
| 18001 端口检查 | 没有遗留监听 |
| M3.3 综合知识检查 | 通过 |

`ReadTimeout` 不代表设备操作一定失败，也不能单独证明写入是否发生。在本次受控场景中，写入先于响应延迟完成，另一次读取确认了当前状态已达到目标值 4321。重复同值写入仅验证当前寄存器赋值操作的最终状态幂等效果，不能推广为所有真实设备指令都允许重试，也不构成通用的真实设备重试策略。

## M3.4 实测记录

M3.4 新增 `tests/recovery/evidence.py`，通过 `EvidenceRecorder` 为显式使用 `fault_evidence` fixture 的测试记录结构化 JSON。证据包含测试 nodeid、唯一 run_id、带时区的 UTC 开始和结束时间、故障事件、预期与实际观察值、设备前后状态、清理结果、pytest 阶段结果及最终综合状态。

pytest hook 收集 setup、call、teardown 的实际报告，在 teardown 报告生成后写出最终证据，确保清理结果已知。测试函数只记录事件和断言，不自行写死最终 PASSED/FAILED。预期的 ReadTimeout、ConnectionError 或 HTTP 500 可以作为故障事件记录，但不会仅因出现这些事件而将用例标为 FAILED。

生成文件保存在 `reports/evidence/`，使用时间戳与 UUID 避免覆盖，采用 UTF-8 和缩进 JSON，运行产物由 `.gitignore` 排除。记录只包含选定的状态与安全异常摘要，不保存密码、Token、完整敏感请求头、代理凭据或原始异常消息。

新增三条真实 HTTP 证据测试，分别覆盖写入 ReadTimeout 后的状态与恢复、HTTP 500 后的健康检查、服务停止后的 ConnectionError 与重启恢复。寄存器保护 fixture 保存实际原值；恢复请求的成功响应与恢复后的实际读回分别记录，只有读回确认原值后才标记恢复成功。

以下结果来自项目维护者完成的真实运行、人工证据检查和故意失败实验：

| 验证项目 | 实测结果 |
| --- | --- |
| M3.4 新增三条测试 | `3 passed` |
| 全部 Recovery 测试 | `13 passed` |
| 完整回归（其中一次） | `42 passed in 26.03s` |
| 18001 端口检查 | 没有遗留 Listen |
| 三轮证据测试运行 | 产生 9 份 JSON 证据 |
| 人工检查 HTTP 500 证据 | 收到 HTTP `500`，后续 health 返回 `200`，最终 `PASSED` |
| 人工检查写入超时证据 | `ReadTimeout` 后读回 4321；清理后实际读回 1234；业务断开与子进程清理成功 |
| 临时 AssertionError 实验 | `setup=passed`、`call=failed`、`teardown=passed`、`final_status=FAILED`、`reports_complete=true`，清理成功 |
| 删除临时实验后的正式全量回归 | 临时故意失败测试文件已删除，重新执行得到 `42 passed` |
| M3.4 综合知识检查 | 通过 |

故意失败实验验证了测试函数失败时，JSON 能准确记录 FAILED，同时保留成功的清理结果；该实验不是正式回归套件应失败的要求。`reports_complete=true` 表示必需阶段报告已收齐，不代表测试通过。

实现会分别保留各阶段结果：仅 call 失败时最终为 FAILED，setup 或 teardown 失败时最终为 ERROR；若 call 与 teardown 同时失败，两阶段失败信息都保留，最终为 ERROR。三阶段实际通过才可得到 PASSED，缺少必需报告时不能补造 PASSED。本阶段已实测验证正常场景与测试函数 AssertionError 场景，尚未专门注入 teardown ERROR、call 失败与 teardown 错误组合或 pytest 进程强制终止等场景，不能将这些处理分支写成已通过实测验收。

## M3.5 实测记录

M3.5 新增 `src/health_retry.py`，实现与 pytest、EvidenceRecorder 解耦的只读 HTTP 健康检查有限重试函数。函数复用调用者提供的 Session，每次 GET 请求均设置有限 timeout、不跟随重定向；只有 HTTP `200` 且 JSON 恰为 `{"status":"ok"}` 才算成功并立即停止。正式 `DeviceApiClient`、8000 DUT 业务接口及原有测试的请求行为保持不变。

`max_attempts` 是包含首次请求的总尝试次数，必须为正整数且不能是布尔值。timeout 必须为有限正数，retry_interval 必须为有限非负数。仅 HTTP `503`、`ConnectionError` 和 `ReadTimeout` 允许继续尝试，且只有仍有剩余次数时才等待重试间隔；HTTP `400`、`500`、其他未允许的响应，以及 HTTP 200 但健康 JSON 不符合契约时立即停止。耗尽次数后返回明确的失败结果，不无限重试、不重启 DUT。

独立 18001 Recovery DUT 新增 `/__test__/retry-health?scenario=...` 和只读的 `/__test__/retry-stats?scenario=...`。各场景的计数保存在本次子进程内，使用锁保护；统计查询不增加场景计数。每条测试启动独立进程，正式 `/health` 与原有测试专用接口不变。

`tests/recovery/test_health_retry.py` 新增 7 个真实 HTTP 测试项：

| 场景 | 验证内容 |
| --- | --- |
| 首次成功 | HTTP 200、健康 JSON 正确，立即停止；实际场景请求数为 1 |
| 503 后恢复 | 依次为 503、503、200；第三次成功后停止，实际场景请求数为 3 |
| 连续 503 | 三次后停止，success=false、stop_reason=attempts_exhausted；实际场景请求数为 3 |
| HTTP 400 | 参数化独立测试项；首次响应后停止，实际场景请求数为 1 |
| HTTP 500 | 参数化独立测试项；首次响应后停止，实际场景请求数为 1 |
| 连接异常耗尽 | 确认受管子进程退出后请求原健康地址，连接异常尝试三次后停止；无响应时 http_status 为 null |
| ReadTimeout 耗尽 | 对原有 1 秒慢接口使用单次 0.2 秒 timeout，精确区分 ReadTimeout，三次后停止并清理子进程 |

通过 `on_attempt` 回调复用 M3.4 的 EvidenceRecorder，记录每次实际结果、序号、HTTP 状态码或实际异常类型、是否允许重试及继续决策。`will_retry` 表示当次继续决策，后续实际完成的尝试事件、完整 history 和适用场景的服务端计数用于核对实际次数；最终业务结果记录 success、attempts_used 和 stop_reason。pytest 最终状态仍由现有 hook 根据真实 setup、call、teardown 报告产生，预期的异常或 503 不等于用例失败。回调出错会暴露错误，不静默继续。

以下结果来自项目维护者完成的真实运行、JSON 证据检查和综合知识检查：

| 验证项目 | 实测结果 |
| --- | --- |
| M3.5 首轮执行 | `6 passed, 1 failed`；失败项为 `test_health_retry_connection_error_attempts_exhausted` |
| 失败项 JSON 诊断 | 实际尝试 3 次，均为 `ConnectTimeout`；retryable 均为 true，will_retry 为 true、true、false，stop_reason 为 attempts_exhausted |
| 首轮失败的阶段结果 | call=failed、teardown=passed，最终 FAILED；证据如实反映断言失败 |
| 修正范围 | 仅修正测试的异常名称断言，允许 `ConnectionError` 或 `ConnectTimeout`；其他断言和重试功能保持不变 |
| 修正后 `python -m pytest` 完整回归 | `49 passed in 40.23s` |
| 正式测试数量 | Smoke/API 29 项，Recovery 20 项，共 49 项 |
| JSON 重试证据检查 | 项目维护者确认正常 |
| 18001 端口清理检查 | 项目维护者确认正常 |
| M3.5 综合知识检查 | 通过 |

首轮失败的根因是测试只接受异常名称字符串 `ConnectionError`，遗漏了其合法子类 `ConnectTimeout`。重试函数已正确捕获实际连接异常、完成三次尝试并按上限停止；本次修正的是测试预期，并未改变重试策略，也没有放宽为接受 ReadTimeout 或其他无关异常。

当前策略仅适用于本项目的只读健康检查，不自动重试写入、设备启动或校准等可能产生副作用的操作，也不代表生产级故障恢复、真实网络丢包或设备自动重启已经实现。调用者应保持 Session adapter 的额外自动重试关闭，避免底层再次重试；每次请求的 timeout、尝试次数与重试间隔不构成整个操作严格的总耗时上限。客户端 ReadTimeout 后，服务端仍可能继续处理原请求。

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

M3.3 的 function-scope `preserved_recovery_register100` fixture 依赖 `recovery_dut`，为每条测试启动独立 DUT、建立连接并保存寄存器 100 的实际原值，然后通过 yield 提供 Client 和原值。正常 teardown 顺序为：

```text
恢复寄存器 100 的实际原值
→ 读回确认
→ 断开业务连接
→ 关闭 Session
→ 清理独立 DUT 进程
```

恢复使用测试前实际读取的原值，不固定写入 1234。嵌套 finally 覆盖 setup、测试与清理阶段：原值已保存时尝试恢复并读回；即使恢复失败，也继续尝试断开，随后关闭 Session，外层 fixture 最后清理子进程。未能保存原值时不伪造恢复，清理失败会明确暴露。所有请求设置有限 timeout，Client 设置 `trust_env=False`。

M3.4 在不削弱原有断言及清理顺序的前提下，收集恢复、读回、业务断开和进程停止的实际事实，再由 pytest 的真实 teardown 报告确定清理阶段结果。证据记录动作放在相应清理操作之后，记录错误不会阻止外层继续尝试资源清理。

M3.5 的重试函数关闭每次收到的 Response，Session 仍由调用者持有；新增测试使用 Session 上下文并设置 `trust_env=False`，在测试结束或断言失败时关闭 Session，外层 `recovery_dut` fixture 再清理独立进程。健康检查重试不写寄存器、不建立业务连接，也不自动重启设备。

## 已验证能力与尚未实现的功能

M1～M3.5 已验证：

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
- 在“先完成写入、后延迟响应”的受控场景中，客户端出现 ReadTimeout 后，通过正常读取确认写入已达到目标值；等待时间足够时可收到 HTTP 200。
- 显式重复相同数值的寄存器赋值，验证最终目标状态保持不变；通过专用 fixture 保存与恢复实际原值，并清理连接、Session 和独立进程。
- 对显式启用证据的测试生成结构化 JSON，关联故障事件、UTC 时间、状态、实际恢复结果和 pytest 的真实阶段报告。
- 区分预期故障事件与 pytest 用例失败；在故意 AssertionError 实验中，正确记录 call 失败、teardown 通过、最终 FAILED 且阶段记录完整。
- 只读健康检查在首次成功、503 后恢复、次数耗尽及不可重试响应时按规则停止；连接异常与 ReadTimeout 均保留实际异常类型，不伪造 HTTP 状态码。
- 通过服务端实际计数核对 HTTP 场景请求次数，利用结构化证据关联每次重试决策、实际尝试与停止原因；首轮 ConnectTimeout 测试预期问题修正后，全量回归为 `49 passed in 40.23s`。

尚未实现：

- 写入、设备启动、校准等可能产生副作用操作的自动重试；自动业务重连以及 DUT 自主故障检测与自动恢复。当前仅实现独立的只读健康检查有限重试函数。
- 非幂等控制指令验证、真实设备断电及数据持久化验证；当前业务状态和寄存器仍在进程内存中，尚未实现持久化存储。
- 真实网络丢包、网络层延迟注入及受控的连接建立超时故障注入；M3.5 实际观察到 ConnectTimeout 并验证有限重试，不代表已能受控复现所有连接阶段故障。
- CI 集成及通用 HTML/XML 测试报告生成流程；当前已实现选定 Recovery 测试的自动 JSON 证据记录。
- 完整的系统级状态隔离及多进程并发隔离。

M3.1 的服务恢复由测试程序按步骤主动重启 DUT，并显式调用 `/connect`，不代表自动重连、设备自主恢复、数据持久化或真实网络丢包测试已经实现。启动时的 health 轮询仅用于判断进程就绪，不是业务请求的自动重试。

M3.2 已验证响应返回前等待过久导致的读取超时，不代表连接建立超时、真实网络丢包或数据持久化验证已经实现；该阶段未加入自动重试，后续 M3.5 的有限重试仅适用于只读健康检查。

M3.3 未实现自动重试、非幂等控制指令验证、真实网络丢包、设备断电及持久化验证。读回目标值证明当前状态达到目标，不能证明所有真实设备操作都可安全重复执行。

M3.4 的故意失败实验证明了测试函数失败时的证据记录，尚未专门验证 teardown ERROR 或 pytest 进程被强制终止时的行为。recorder 创建前发生导入、收集或 setup 故障时，无法保证完整证据；进程强制终止、磁盘或权限故障也可能导致 JSON 未写出或不完整。不能仅凭文件存在判断证据完整，仍需检查阶段结果、清理事实与最终状态。

M2.4 的 `/disconnect` 只改变业务连接状态；M3.1 则实际停止并重启受管子进程。原有 8000 功能测试仍共享 DUT 进程，Recovery 使用逐项管理的独立 18001 进程，但固定端口并不提供多进程并发隔离。其他进程同时操作 DUT 时仍可能产生竞争；进程异常或网络中断时，teardown 不能保证所有状态都恢复成功。

已完成的中断与恢复验证以及 fixture 清理，不代表上述尚未实现的能力已具备。
