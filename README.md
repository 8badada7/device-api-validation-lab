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

## 测试架构与目录

| 路径 | 职责 |
| --- | --- |
| `dut/` | Flask 模拟设备：健康检查、业务连接、寄存器读写 |
| `src/` | HTTP Client 与独立的健康检查重试逻辑 |
| `tests/smoke/` | 基础健康检查 |
| `tests/api/` | API 功能、参数与边界验证 |
| `tests/recovery/` | 独立 DUT 进程管理、故障注入、恢复与可靠性测试 |
| `configs/` | 测试环境地址和请求 timeout |
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

已验收环境为 Python 3.11.17、pytest 9.1.1；依赖版本尚未固定。

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

## 最新测试结果

M1～M3.5 已由项目维护者完成真实运行验收，最近一次正式全量回归结果如下：

| 范围 | 结果 |
| --- | --- |
| Smoke/API | 29 项 |
| Recovery | 20 项 |
| 全量回归 | **49 passed in 40.23s** |

## 已知限制

- DUT 为 Flask 模拟服务，尚未覆盖真实工业硬件、真实网络丢包、设备断电与持久化验证。
- 有限重试仅用于只读健康检查，不自动重试写入、启动或校准等可能产生副作用的操作。
- 每次请求的 timeout 和尝试次数不构成整个操作严格的总耗时上限。
- 独立进程减少测试间干扰，但固定端口及共享服务不提供完整并发隔离。
- 服务恢复由测试程序主动重启，不代表生产级故障恢复或设备自主恢复。
- 当前尚未建立 CI 自动化流程。

## 详细记录

[查看完整验证与故障排查记录](docs/validation-log.md)
