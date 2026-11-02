# device-api-validation-lab

## 项目简介

基于 Python、pytest、requests 和 Flask 的模拟设备 HTTP API 自动化验证项目，实践 API 测试、故障注入、状态一致性、测试证据和有限恢复策略。

DUT 是 Flask 实现的模拟设备，使用进程内存保存业务连接状态与寄存器数据，不涉及真实工业硬件。

## 技术栈

- Python：测试与进程控制。
- pytest：测试组织、参数化、fixture 和执行结果采集。
- requests：真实 HTTP 通信。
- Flask：模拟设备 HTTP 服务。
- Git：版本管理，代码托管于 GitHub。

## 核心功能

- **API 功能与边界验证**：覆盖健康检查、业务连接与断开、寄存器读写、数值边界及非法参数；写入后通过读回确认实际状态。
- **故障注入与恢复**：通过真实子进程和 HTTP 请求验证服务中断、ReadTimeout、HTTP 500，以及测试程序主动重启后的 HTTP 和业务恢复。
- **状态一致性与测试证据**：验证写入超时后的实际状态与同值赋值的幂等效果，通过 fixture 恢复原值，并生成关联 pytest 实际阶段结果的 JSON 证据。
- **有限重试策略**：仅对只读健康检查重试 HTTP 503、ConnectionError 和 ReadTimeout，遇到 HTTP 400/500 等不可重试响应立即停止。最大尝试次数包含首次请求，健康响应成功后停止，并通过服务端计数核对 HTTP 场景请求次数。
- **CI 自动化验证**：GitHub Actions 在 Ubuntu 24.04、Python 3.11 中自动准备环境、启动并检查 DUT、执行原有 49 项测试，上传 JUnit XML、JSON 故障证据和日志，并清理 DUT。

## 测试架构与目录

| 路径 | 职责 |
| --- | --- |
| `dut/` | Flask 模拟设备：健康检查、业务连接、寄存器读写 |
| `src/` | HTTP Client 与独立的健康检查重试逻辑 |
| `tests/smoke/` | 基础健康检查 |
| `tests/api/` | API 功能、参数与边界验证 |
| `tests/recovery/` | 独立 DUT 进程管理、故障注入、恢复与可靠性测试 |
| `configs/` | 测试环境地址和请求 timeout |
| `.github/workflows/ci.yml` | GitHub Actions 触发条件、执行环境和诊断文件上传 |
| `scripts/run_ci_tests.py` | CI 中的 8000 DUT 启动、就绪检查、pytest 执行与清理 |
| `reports/`、`logs/` | JSON 证据及子进程日志等运行产物，生成文件不纳入版本控制 |
| `docs/` | 详细验证与故障排查记录 |

API/Smoke 测试访问预先启动的 `127.0.0.1:8000` DUT，配置来自 `configs/test_env.json`。
Recovery 测试由 function-scope fixture 自动管理独立的 `127.0.0.1:18001` DUT，只操作自己创建的子进程，不停止 8000 服务。

## 快速开始

以下命令均在项目根目录执行。示例使用已建立的 Conda 环境 `device-api-val`：

```powershell
conda activate device-api-val
python -m pip install -r requirements.txt
```

本地 Windows 已验收 Python 3.11.17。已固定 pytest、requests、Flask 三个直接依赖版本，但尚未完整锁定传递依赖。

运行 API/Smoke 或全量回归前，在终端一启动 8000 DUT 并保持运行：

```powershell
python dut/app.py
```

在终端二进入项目根目录、激活同一环境后，按需选择测试命令：

```powershell
conda activate device-api-val

# API/Smoke 功能回归
python -m pytest -m "smoke or api"

# 全量回归
python -m pytest
```

仅运行 Recovery 时，在已激活环境的终端执行：

```powershell
python -m pytest -m recovery
```

**单独运行 Recovery 不需要启动 8000 DUT，也不要人工启动 18001 DUT。** fixture 自动启动并清理 18001 子进程，运行前该端口应空闲。

GitHub Actions 会在 push 到 `main`、针对 `main` 的 pull_request，以及手动 workflow_dispatch 时触发。
提交后可在 [Actions 页面](https://github.com/8badada7/device-api-validation-lab/actions) 查看步骤、结果及 Artifacts；CI 自动管理 8000 DUT，18001 DUT 仍由 Recovery fixture 管理。

## 最新测试结果

M1～M5 已由项目维护者完成真实验收，M5 状态为 **Completed / Verified**。以下为不同阶段和环境的实际结果，耗时不作为严格性能对比：

| 范围 | 结果 |
| --- | --- |
| Smoke/API | 29 项 |
| Recovery | 20 项 |
| Windows 本地回归（M5） | **49 passed in 40.83s** |
| GitHub Actions（M4，Ubuntu 24.04、Python 3.11） | **49 passed in 10.51s** |
| GitHub Actions（M5 合并后 main，Ubuntu 24.04、Python 3.11） | **49 passed in 8.20s** |

[查看 M5 合并后 CI 成功运行记录](https://github.com/8badada7/device-api-validation-lab/actions/runs/41446399031)

## 已知限制

- DUT 为 Flask 模拟服务，尚未覆盖真实工业硬件、真实网络丢包、设备断电与持久化验证。
- 有限重试仅用于只读健康检查，不自动重试写入、启动或校准等可能产生副作用的操作。
- 每次请求的 timeout 和尝试次数不构成整个操作严格的总耗时上限。
- 独立进程减少测试间干扰，但固定端口及共享服务不提供完整并发隔离。
- 服务恢复由测试程序主动重启，不代表生产级故障恢复或设备自主恢复。
- 尚未完整锁定传递依赖，重新安装或不同环境下的行为仍需实际验证。

## 详细记录

[查看 12 条代表性测试用例矩阵](docs/test-matrix.md)

[查看完整验证与故障排查记录](docs/validation-log.md)
