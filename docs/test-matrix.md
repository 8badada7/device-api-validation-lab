# 代表性测试用例矩阵

从现有 49 个 pytest test item 中选取 12 个代表场景；参数化输入合并展示，不新增测试，也不将本文视为一次新的运行报告。

## 前置与清理约定

- **API**：8000 DUT 已启动，地址与 timeout 来自配置；`connected_client` / `disconnected_client` 通过 HTTP 设置连接状态。合法读取还要求寄存器 100=1234、101=5678，连接 fixture 不重置寄存器。
- **P**：`preserved_register100`，依赖已连接 Client；保存寄存器 100 的实际原值，teardown 写回并读回确认，再由上层 fixture 断开业务连接、关闭 Session。
- **R**：`preserved_recovery_register100`，启动独立 18001 DUT、连接并保存实际原值；所选测试断言初值为 1234。teardown 恢复并读回确认 → 断开 → 关闭 Session → 停止子进程。
- **Recovery**：`recovery_dut` 管理独立 18001 子进程并最终清理；测试通过上下文关闭 Session。TC-09～11 使用真实 Session、`trust_env=False`、`max_attempts=3`（含首次）、timeout=1 秒、retry_interval=0.2 秒。

## 用例矩阵

| 编号 | 测试目的 | 设计方法 | 前置条件 | 操作或输入 | 预期结果（按现有断言） | 对应真实 pytest 函数 |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | 合法寄存器可读取 | 等价类：有效地址 | API；已连接；寄存器为上述基线值 | `GET /read`，参数组 `(address, expected)=(100,1234)/(101,5678)` | HTTP 200；响应 address、value 分别等于请求地址和预期数值 | [test_read_valid_register](../tests/api/test_read.py#L13) |
| TC-02 | 拒绝非法读取地址 | 等价类：缺失、非整数、负数 | API；已连接 | `GET /read`，address 为 `None`、`"abc"`、`-1`；None 表示不传查询参数 | HTTP 400；JSON 的 error 为 `invalid_address` | [test_read_invalid_address](../tests/api/test_read.py#L28) |
| TC-03 | 写入边界与正常值后可读回 | 边界值＋有效等价类 | API；P | `POST /write`，address=100，value 为 `0/1/4321/65535`；随后 `GET /read` | 写入、读取均为 200；写入响应 address/value 正确，读回 JSON 等于目标地址和值；P 在测试后恢复原值并读回确认 | [test_write_readback](../tests/api/test_write.py#L15) |
| TC-04 | 非法数值不改变寄存器 100 | 无效等价类＋越界值 | API；P | 先读取 100 作快照；写入 value=`None/-1/65536/"abc"/True`；再读 100。None 表示 JSON 缺少 value，True 为布尔值 | 写入 400、JSON 为 `{"error":"invalid_value"}`；读回 200 且完整 JSON 等于快照；P 仍执行恢复与读回 | [test_write_invalid_value](../tests/api/test_write.py#L34) |
| TC-05 | 未连接状态拒绝读取 | 等价类：无效业务状态 | API；`disconnected_client` 确认 connected=false | `GET /read?address=100` | HTTP 409；JSON 为 `{"error":"not_connected"}` | [test_read_when_disconnected](../tests/api/test_disconnect.py#L32) |
| TC-06 | 断开操作改变读取行为 | 状态转换：已连接 → 未连接 | API；`connected_client` | 读取 100 → `POST /disconnect` → 再读 100 | 首次读取 200；断开 200、connected=false；随后读取 409，JSON 为 `{"error":"not_connected"}` | [test_disconnect_changes_read_behavior](../tests/api/test_disconnect.py#L48) |
| TC-07 | 写入读取超时后核对实际状态 | 异常及恢复：超时后状态确认 | R；原值 1234 | `POST /__test__/write-delayed` 写 `{"address":100,"value":4321}`，timeout=0.2 秒；随后正常读取 100，不重启 | 精确捕获 `requests.exceptions.ReadTimeout`；读回 200、JSON 为 `{"address":100,"value":4321}`；确认同一进程仍运行；R 恢复实际原值并读回 | [test_write_takes_effect_despite_read_timeout](../tests/recovery/test_write_consistency.py#L19) |
| TC-08 | 重复同值赋值保持最终状态 | 异常及恢复：幂等状态效果 | R；原值 1234 | `POST /__test__/write-delayed` 写 100=4321，timeout=0.2 秒并触发 ReadTimeout → 读回 → 正常 `/write` 再写相同值 → 再读回 | 两次读回和正常写入均为 200、JSON 均为 `{"address":100,"value":4321}`；R 在 teardown 恢复原值并读回 | [test_repeated_same_value_is_idempotent](../tests/recovery/test_write_consistency.py#L41) |
| TC-09 | 临时 503 后有限重试成功 | 异常及恢复：服务响应恢复 | 独立 Recovery DUT 已就绪；场景计数从 0 开始 | `GET /__test__/retry-health?scenario=recover_after_two_503`，最多 3 次 | history 为 503、503、200；success=true、attempts_used=3、stop_reason=`recovered`；will_retry 为 true、true、false；服务端实际计数为 3 | [test_health_retry_recovers_after_two_503](../tests/recovery/test_health_retry.py#L100) |
| TC-10 | 连续 503 达上限后停止 | 异常及恢复：重试耗尽 | 独立 Recovery DUT 已就绪；场景计数从 0 开始 | 同一重试入口，scenario=`always_503`，最多 3 次 | 三次均为 HTTP 503；success=false、attempts_used=3、stop_reason=`attempts_exhausted`；will_retry 为 true、true、false；服务端计数为 3 | [test_health_retry_stops_when_503_attempts_exhausted](../tests/recovery/test_health_retry.py#L124) |
| TC-11 | 不可重试响应立即停止 | 等价类：不可重试 HTTP 响应 | 独立 Recovery DUT 已就绪；场景计数从 0 开始 | 参数组 `(scenario,status)=(always_400,400)/(always_500,500)`，max_attempts=3 | 只请求 1 次；对应 HTTP 400/500；success=false、stop_reason=`non_retryable_response`；retryable=false、will_retry=false、exception_type=None；服务端计数为 1 | [test_health_retry_stops_on_non_retryable_response](../tests/recovery/test_health_retry.py#L151) |
| TC-12 | 验证 HTTP 500 是可接收的错误响应，且服务仍可响应健康检查。 | 异常及恢复：错误响应后健康确认 | 独立 Recovery DUT 已就绪 | `GET /__test__/server-error`，随后 `GET /health` | 收到原始 `requests.Response`，状态 500、JSON 为 `{"error":"simulated_internal_error"}`；后续 health 为 200、JSON 为 `{"status":"ok"}`；不把 500 当成超时异常 | [test_http_500_is_response_not_timeout](../tests/recovery/test_response_timeout.py#L87) |

## 测试文件索引

| 用例 | 测试文件 |
| --- | --- |
| TC-01～02 | [tests/api/test_read.py](../tests/api/test_read.py) |
| TC-03～04 | [tests/api/test_write.py](../tests/api/test_write.py) |
| TC-05～06 | [tests/api/test_disconnect.py](../tests/api/test_disconnect.py) |
| TC-07～08 | [tests/recovery/test_write_consistency.py](../tests/recovery/test_write_consistency.py) |
| TC-09～11 | [tests/recovery/test_health_retry.py](../tests/recovery/test_health_retry.py) |
| TC-12 | [tests/recovery/test_response_timeout.py](../tests/recovery/test_response_timeout.py) |

清理依据：[API fixtures](../tests/api/conftest.py)、[Recovery fixtures 与测试专用路由](../tests/recovery/conftest.py)。

## 断言边界

- TC-06 断开前只检查读取状态码 200，没有断言当时值为 1234，也没有验证重新连接；TC-04 只证明寄存器 100 未变，不证明所有寄存器均未变。
- TC-03 的参数不是全取值域覆盖；TC-08 只证明当前寄存器赋值的最终状态幂等效果，不证明恰好执行一次，也不支持将重试推广至所有真实设备指令。
- ReadTimeout 是客户端异常，不是 HTTP 500/503 响应，也不代表服务端取消写入；`/__test__/slow` 仅模拟慢响应，不是 TC-07～08 使用的写入接口。
- TC-10～11 的 success=false 是预期业务结果，不等于 pytest FAILED。fixture 在测试失败后会尝试清理，但不保证进程崩溃、外部并发等情况下总能恢复成功。
