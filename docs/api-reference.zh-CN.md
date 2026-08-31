# KUMA Python API 参考

简体中文 | [English](api-reference.md)

本文记录稳定的用户侧 Python API。参数类型、默认值、范围、副作用和失败语义均以当前实现为准。KUMA 的主要 API 使用仅关键字参数，调用时应保留参数名。

## `configure`

```python
from kuma import configure

credential_path = configure(api_key="dfx_your_key_here")
```

<!-- api-parameters:configure:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `api_key` | `str` | 必填 | 以 `dfx_` 开头的可打印 ASCII KUMA 凭证；编码后最多 512 字节，不允许空白或控制字符。 |

<!-- api-parameters:configure:end -->

返回原子写入的用户凭证文件绝对 `Path`，不发送网络请求。`KUMA_CONFIG_HOME` 可改变凭证目录。非法 Key 抛出 `ConfigurationError`，文件系统失败保留为真实 `OSError`。该文件含 Key，禁止打印或提交。

## `create_run`

```python
from kuma import create_run

run = create_run(repo_path=".", requirement_path="requirement.md")
```

<!-- api-parameters:create_run:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `repo_path` | `str \| os.PathLike[str]` | `"."` | Agent 可见的仓库根目录；会展开并解析成绝对路径。 |
| `requirement_path` | `str \| os.PathLike[str] \| None` | `None` | UTF-8 Requirement 文件。官方 Case 必须提供；自定义 Provider 可明确不要求。 |
| `case_provider` | `CaseProvider \| callable \| None` | `None` | 自定义 Case 来源；`None` 使用官方鉴权 Provider。 |
| `judge_provider` | `JudgeProvider \| callable \| None` | `None` | 自定义 Judge；当 `judge=True` 时，`None` 使用官方 Provider。 |
| `strategy` | `str` | `"auto"` | `"auto"` 让服务选择；其他非空值是显式策略 ID。未知策略不会被静默替换。 |
| `max_inputs` | `int \| None` | `None` | 正整数 Case Input 上限。自定义 Case Provider 必须提供；官方模式省略时遵循公开服务策略。 |
| `judge` | `bool` | `True` | 最后一次 Submission 后执行 Judge；`False` 时 `run.report` 保持 `None`。 |
| `on_failure` | `str` | `"continue"` | `"continue"` 在 failed/timeout/aborted 后继续；`"stop"` 立即结束 Run。 |
| `allow_local` | `bool` | `False` | 允许可信的非 Docker 开发运行；不会创建沙箱，也不会放松校验或隐私规则。 |
| `track_files` | `bool` | `True` | 每个 Input 前后采集有界文件元数据。 |
| `upload_diff` | `bool` | `False` | 加入有界文本 diff；要求 `track_files=True`，并可能把仓库文本交给所配置的 Judge。 |
| `save_local` | `bool` | `False` | 原子保存 Submission JSON 到 `.kuma/runs/<run_id>/`；不替代官方提交。 |
| `allow_sensitive` | `bool` | `False` | 允许普通 Evidence 中被扫描器命中的内容；绝不放宽 OTel allowlist。 |
| `timeout` | `float` | `300.0` 秒 | 单次公网 HTTP 尝试的正有限超时，不是整个 operation 的等待时间。 |
| `operation_wait_timeout` | `float` | `600.0` 秒 | 一次官方异步 Case/Judge operation 的正有限总等待上限；超时保留恢复元数据。 |
| `max_retries` | `int` | `2` | 自动瞬态重试次数，范围 0–5；幂等 POST 重试复用同一个 Key。 |
| `api_key` | `str \| None` | `None` | 本次调用的 `dfx_` Key；解析顺序为本参数、`KUMA_API_KEY`、用户凭证文件。 |
| `trace_evidence` | `TraceEvidenceCapture \| None` | `None` | `configure_trace_evidence()` 返回的显式 capture；省略时安全尝试复用全局 Provider，否则仅记录非阻断 warning。 |

<!-- api-parameters:create_run:end -->

返回处于 `ready` 状态的同步 `Run`。配置、凭证、隔离、Provider、Case 或公网服务失败会抛出具体 `KumaError` 子类，并提供稳定的 `code`、`retryable` 和可选 `request_id`。创建过程可能读取 Requirement 和有界仓库元数据、创建 `.kuma/`、获取单 active Run 锁，并在使用官方 Provider 时调用公开 Backend。

## `Run`

### `get_input`

<!-- api-parameters:get_input:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `full` | `bool` | `False` | `False` 仅返回 JSON-compatible payload；`True` 返回不可变 `KumaInput` 元数据和 payload。 |

<!-- api-parameters:get_input:end -->

返回当前 Input 且不推进状态；全部提交后返回 `None`。在 `submit()` 前重复调用返回同一个 Input。非法顺序抛出 `InputProtocolError`。

### `submit`

<!-- api-parameters:submit:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `output` | 有限 JSON-compatible 值 | 省略 | Agent 结果。显式值优先；仅当受支持 OTel instrumentation 提供最终 Agent/Workflow 输出时，completed Submission 才能省略。显式 `None` 不是成功结果。 |
| `status` | `str` | `"completed"` | 只能是 `"completed"`、`"failed"`、`"timeout"` 或 `"aborted"`。 |
| `error` | `str \| None` | `None` | 非 completed Submission 的安全摘要；不得包含 secret 或原始 traceback。 |
| `logs` | `list[str \| Path] \| None` | `None` | 采集有界新增内容的日志文件；必须启用 Evidence，且仍受目录与敏感数据校验。 |
| `wait` | `bool` | `True` | 最后一次 Submission 触发 Judge 时必须保持 `True`；公共 API 不暴露后台轮询。 |

<!-- api-parameters:submit:end -->

只有最后一次 Submission 完成 Judge 时返回 `TestReport`，其他情况返回 `None`。Submission、Evidence offset、本地记录和 Trace 字节预算按事务提交。非法输出/状态抛出 `ValidationError` 或 `InputProtocolError`；采集和 Judge 失败保留稳定 `KumaError`。

### `judge`

<!-- api-parameters:judge:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `wait` | `bool` | `True` | 必须为 `True`；官方 operation 在内部同步、有界轮询。 |

<!-- api-parameters:judge:end -->

返回验证后的 `TestReport`。失败时恢复 `completed`，重试会复用 History 和 pending operation。Run 未完成时抛出 `InputProtocolError`；`wait=False` 抛出 `ConfigurationError`。

### `cancel`

`cancel()` 没有参数并返回 `None`，会释放 Evidence 状态、临时运行文件和 active Run 锁。重复取消安全；不允许隐藏提交中/失败状态时抛出 `InputProtocolError`。

### 只读属性

| 属性 | 类型 | 含义 |
| --- | --- | --- |
| `run_id` | `str` | 当前 Run 的公开标识。 |
| `case_id` | `str` | 公开 Case 标识，不包含 Private Rubric。 |
| `state` | `RunState` | 当前生命周期状态。 |
| `history` | `tuple[HistoryItem, ...]` | 已提交的不可变 Input/Submission 对。 |
| `report` | `TestReport \| None` | `report_ready` 后的最终验证 Judgment。 |
| `runtime_warnings` | `tuple[str, ...]` | 非致命 Evidence 降级稳定代码。 |

## `KumaClient`

不创建 Run、只读取鉴权配置时使用 `KumaClient`。

<!-- api-parameters:KumaClient:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `api_key` | `str \| None` | `None` | 可选 `dfx_` Key，沿用环境变量/凭证文件回退；读取方法必须最终取得 Key。 |
| `base_url` | `str` | KUMA 公开 URL | 公开 Backend API base；远程地址必须 HTTPS，本地集成可用 loopback HTTP，拒绝 URL credentials。 |
| `timeout` | `float` | `30.0` 秒 | 每次公开配置 GET 请求的正有限超时；不控制 Run operation 的总等待时间。 |
| `transport` | 公共 transport callable \| `None` | `None` | 测试/集成 HTTP 边界；普通用户不要传。 |

<!-- api-parameters:KumaClient:end -->

`entitlements()`、`strategies()` 和 `judge_config()` 均无参数，返回验证后的公开 mapping。它们可能抛出 `KumaAuthenticationError`、`KumaPermissionError` 或 `KumaRateLimitError`，不会直连 MCP、模型或数据库。

## OpenTelemetry

导入 `kuma.otel` 前安装 `kuma-defuzex[otel]`。

<!-- api-parameters:configure_trace_evidence:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `tracer_provider` | OTel SDK Provider \| `None` | `None` | 现有且提供 `add_span_processor` 的 Provider；`None` 选择当前全局 Provider，KUMA 绝不替换它。 |
| `limits` | `TraceEvidenceLimits \| None` | `None` | 有界采集配置；`None` 使用下列默认值。 |

<!-- api-parameters:configure_trace_evidence:end -->

返回供 `create_run(trace_evidence=...)` 使用的 `TraceEvidenceCapture`；非法 Provider 或限制抛出 `ConfigurationError`。

<!-- api-parameters:TraceEvidenceLimits:start -->

| 参数 | 类型 | 必填/默认值 | 用法 |
| --- | --- | --- | --- |
| `max_spans` | 正 `int` | `200` | 单 Run 最多保留的结束 span 数。 |
| `max_attributes` | 正 `int` | `32` | 每个 span 最多保留的 allowlisted attributes 数。 |
| `max_events_per_span` | 正 `int` | `20` | 每个 span 最多保留的 allowlisted events 数。 |
| `max_text_length` | 正 `int` | `256` 字符 | 单个允许文本值最多保留的 Unicode 字符数。 |
| `max_total_bytes` | 正 `int` | `512000` 字节 | 单 Run 已提交 Trace envelope 的紧凑 JSON 总字节上限；必须能容纳最小 envelope。 |

<!-- api-parameters:TraceEvidenceLimits:end -->

## 公共结果契约

主要不可变类型从 `kuma` 导出：

| 类型 | 重要字段与含义 |
| --- | --- |
| `KumaInput` | `run_id`、`case_id`、`input_id`、从零开始的 `index`、`payload_type`、冻结的 `payload`、公开 constraints、schema version 和公开 extensions。 |
| `Submission` | 关联 ID、步骤终态 `status`、JSON output/error、采集完整性、有界 logs/file Evidence、dropped/missing 计数、schema version 和 extensions。 |
| `HistoryItem` | 一个 `KumaInput` 与 ID 完全匹配的 `Submission`。 |
| `TestReport` | `report_id`、`run_id`、`status`（`pass`、`issue` 或 `insufficient_evidence`）、confidence、stop reason、公开 issues/evidence gaps 和 extensions。 |
| `CaptureStatus` | file snapshot/diff、logs、sensitive scan、traces 的完整性；每项为 `complete`、`partial`、`failed` 或 `skipped`。 |

这些对象不包含 Private Rubric、Prompt、模型设置或 Core 记录。仅哈希上传格式见 [Runtime Evidence 合同](runtime-evidence.md)。

## 错误字段

普通 SDK 失败统一捕获 `KumaError`。`str(exc)` 是安全的用户文案；程序判断使用 `exc.code`、`exc.retryable` 和 `exc.request_id`。`exc.details` 是有界公开 mapping，也只应通过应用自己的 allowlist 记录。
