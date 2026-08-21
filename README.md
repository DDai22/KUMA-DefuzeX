# DefuzeX Python SDK

DefuzeX Python SDK v4 是 Agent 行为测试的公开 Python 客户端。它负责解析测试要求、生成最小化仓库元数据、驱动同步 Run、采集 Evidence，并通过 Website Backend 的公开 HTTPS API 获取官方 Case 和 Judgment。

SDK 的联网边界固定为：

```text
SDK -> Website Backend public API -> private Core MCP -> model/core database
```

SDK 不直连 MCP、模型或数据库，也不包含 Private Rubric、hidden answer、模型配置或服务端凭据。详细依赖方向见 [架构文档](docs/architecture.md)，公开 HTTP 契约摘要见 [API Contract](docs/api-contract.md)。

它也不是 Agent runner、容器编排器或服务端 SDK。用户代码负责执行被测 Agent、管理其工具权限与进程，并把真实 output 或标准 OTel span 交给 Run；DefuzeX SDK 只负责测试协议和可验证 Evidence。Website Backend 负责公开鉴权、scope、配额、计费和安全错误映射，Core MCP 负责 Case、Private Rubric、Judge、模型调用与核心数据。

## 适用场景与核心概念

DefuzeX 适合验证会读写仓库、调用工具或执行工作流的 Agent：官方 Provider 可使用服务端 Case/Judge，自定义 Provider 可用于本地测试、固定回归或私有评估逻辑。SDK 评估的是 Agent 在一个受控任务中的真实行为，不负责启动 Agent、选择模型或提供沙箱。

- **Case**：一次完整测试的公开输入序列；官方 Case 的私有 Rubric 始终留在服务端。
- **Input**：Case 中当前交给 Agent 的一个任务。
- **Run**：严格执行 `get_input()` → Agent → `submit()` 握手的单 Case 状态机。
- **Submission/History**：Agent 的结果及其与 Input 对齐的不可变历史。
- **Evidence**：文件变化、显式日志和可选同进程 OTel spans；采集和提交保持事务语义。
- **Judgment/TestReport**：Judge 对完整 Run 的公开结果。
- **Provider**：Case 或 Judge 的边界实现；可以是官方 HTTPS Provider，也可以是本地自定义实现。

## 安装

Python 3.10 或更高版本：

从 GitHub 获取当前正式版本：

```bash
git clone https://github.com/DefuzeX-company/defuzex-python-sdk.git
cd defuzex-python-sdk
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Linux/macOS：

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

如果 `defuzex` 已发布到你使用的 Python 包源，也可以直接安装：

```bash
python -m pip install defuzex
```

从本仓库开发时使用 editable install：

```bash
python -m pip install -e ".[dev]"
```

`[dev]` 只包含 Ruff、build 和 twine 等开发工具。用户仅需 Trace Evidence 时安装 `[otel]`；核心安装不强制引入 OTel。

OpenTelemetry 是可选能力，不属于核心依赖：

```bash
python -m pip install "defuzex[otel]"
# 或从源码安装
python -m pip install -e ".[otel]"
```

仓库中的版本号不代表某个公共包索引已经发布了同版本；请以你实际使用的包源或本仓库提交为准。

## 无账号的本地首次运行

安装后直接运行：

```bash
defuzex quickstart
```

该命令不需要账号、API Key、Docker 或 `allow_local=True`。它不会读取当前目录或用户仓库，也不会访问 Backend、Core、模型或网络；SDK 只在操作系统临时目录中创建一个隔离仓库。内置的确定性 fake Agent 对固定 Input 返回 `defuzex-ready`，公开 evaluator 只执行一条可解释规则：输出必须与该文本完全一致。

预期摘要类似：

```text
Local check: PASS
Score: 100/100
Reason: Output exactly matched the published rule.
Artifact: <absolute temporary path>/result.json
```

结果文件包含固定 Input、其 SHA-256、fake output、分数和原因，不包含凭证或用户文件。使用 `defuzex quickstart --fail-demo` 可查看确定性的失败评分和非零退出码。该 quickstart 不是 LLM Judge 或生产 Agent；接入真实框架使用 [Single Agent Template](examples/single_agent_template/README.md)，官方 Case/Judge 仍需显式使用正式 `create_run()` 配置。

## 无需 API Key 的可运行示例

安装本仓库后，在仓库根目录运行：

```bash
python examples/minimal_local.py
```

[完整示例源码](examples/minimal_local.py)使用临时仓库、自定义 Case Provider、`judge=False` 和 `allow_local=True`。它不读取 API Key、不访问公网，也不会修改运行命令所在的真实仓库；临时目录会在结束时自动删除。

预期输出：

```text
input=Return a bounded maintenance result.
state=completed
submissions=1
```

该示例演示 SDK 的最短完整链路：创建 Run、取得 Input、提交 Agent output、检查 History。要使用官方 Case/Judge，再按下一节配置公开 API Key。

## 官方服务 Quickstart

### 1. 准备 API Key

官方 Case 或官方 Judge 需要 `dfx_` 开头的 API Key。推荐只放在环境变量中：

```powershell
$env:DEFUZEX_API_KEY = "dfx_<public-id>.<secret>"
```

也可以写入当前用户的凭证文件；该操作只写本地文件，不发起网络请求：

```python
from defuzex import configure

credential_path = configure(api_key="dfx_<public-id>.<secret>")
print(credential_path)
```

凭证解析优先级为：`create_run(api_key=...)` 或 `DefuzeClient(api_key=...)`、`DEFUZEX_API_KEY`、用户凭证文件。不要把 Key 写入源码、Notebook 输出或 Git。

可先验证公开身份、scope 和额度：

```bash
defuzex whoami
```

### 2. 写 requirement 文件

官方 Case Provider 需要显式的 UTF-8 requirement 文件。例如 `requirement.md`：

```markdown
---
agent_description: A repository maintenance agent
input_type: text
---

## Production Use Scenario

Maintain a Python repository without changing its public interface.

## Behaviors to Test

Diagnose the requested defect, apply a bounded fix, and run relevant tests.

## Known Limitations or Prohibited Behaviors

Do not read credentials, modify tests, or access paths outside the repository.
```

三个二级标题也接受仓库测试中使用的中文别名。结构化输入还需要本地 JSON Schema，但当前官方 Case 服务只接受 `input_type: text`；结构化输入仅适用于自定义 Case Provider。

### 3. 执行 Run

```python
from typing import Any

from defuzex import create_run


def execute_agent(test_input: Any) -> dict[str, Any]:
    """Replace this body with the Agent invocation being evaluated."""
    return {"result": str(test_input)}


run = create_run(
    repo_path=".",
    requirement_path="requirement.md",
    allow_local=True,  # 仅本地开发；正式模式默认要求同容器运行
)

while (test_input := run.get_input()) is not None:
    output = execute_agent(test_input)
    report = run.submit(output)

print(run.state)
print(run.report)
```

`get_input()` 默认返回 payload；使用 `get_input(full=True)` 可获得不可变的 `DefuzeXInput`，其中包含 `run_id`、`case_id`、`input_id`、索引、payload 类型和 public constraints。`submit(output)` 接受有限值 JSON 可序列化数据；若 Agent 的 OTel `invoke_agent`/`invoke_workflow` span 已提供标准 `gen_ai.output.messages`，也可直接调用 `submit()`。

## 公开 API 速查

优先从稳定公开模块导入；以下划线开头的模块和名称属于内部实现：

| 导入位置 | 公开用途 |
|---|---|
| `defuzex.configure` | 验证并原子保存 API Key，不访问网络 |
| `defuzex.create_run` | 创建一个同步 Python `Run` |
| `defuzex.DefuzeClient` | 读取 entitlements、strategy catalog 和 Judge 动态配置 |
| `defuzex.Case`、`DefuzeXInput`、`Submission`、`HistoryItem`、`TestReport` | 不可变公开协议对象 |
| `defuzex.errors` | `DefuzeError` 及稳定错误子类 |
| `defuzex.providers` | 自定义 Provider Protocol/context、normalizer 和官方 Provider |
| `defuzex.otel` | 可选 `[otel]` extra 的显式 Trace Evidence attach API |

`create_run()` 返回的 `Run` 提供 `get_input()`、`submit()`、`judge()`、`cancel()`，以及只读的 `state`、`history`、`report` 和 `runtime_warnings`。单 Case/单 Judge 的 v2 operation、轮询和恢复元数据是官方 Provider 的内部 transport 行为，不会把 Python API 改成后台 job API。

## 配置

公开入口是 `defuzex.create_run()`。常用参数如下：

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `repo_path` | `"."` | 被测仓库；必须是可读目录 |
| `requirement_path` | `None` | requirement 文件；官方 Provider 和默认自定义 Provider 要求显式提供 |
| `case_provider` | `None` | `None` 使用官方 Case；也可传实现 `CaseProvider` 的对象或 callable |
| `judge_provider` | `None` | `None` 且 `judge=True` 时使用官方 Judge |
| `strategy` | `"auto"` | SDK 发送纯 `agent_description` 与结构化 `behavior_spec`；显式模式只指定 strategy ID。实际策略和 version 均由 Backend/Core 权威解析 |
| `max_inputs` | `None` | 自定义 Case 必填；限制归一化后的 Input 数量 |
| `judge` | `True` | 最后一次提交后是否执行 Judge |
| `on_failure` | `"continue"` | 非 completed 提交后继续下一 Input，或使用 `"stop"` 停止 |
| `allow_local` | `False` | 显式允许非 Docker 的开发运行 |
| `track_files` | `True` | 为每个 Input 采集前后文件快照和变化元数据 |
| `upload_diff` | `False` | 在文件 Evidence 中加入文本 diff；开启前应评估敏感内容 |
| `save_local` | `False` | 将每步结构化记录保存在 `.defuzex/runs/<run_id>/submissions/` |
| `allow_sensitive` | `False` | 显式允许普通 Evidence 中命中的敏感内容；不会放宽 OTel allowlist |
| `timeout` | `300.0` | 每次公开 Backend 请求的秒级超时 |
| `operation_wait_timeout` | `600.0` | 官方单 Case/Judge 从 POST 到终态的独立总等待上限；超时保留恢复元数据 |
| `max_retries` | `2` | 0–5；仅对 Backend 标记为瞬态且可重试的失败做指数退避重试 |
| `api_key` | `None` | 本次调用的 API Key，优先于环境和用户凭证文件 |
| `trace_evidence` | `None` | `configure_trace_evidence()` 返回的同进程 Trace capture |

公开服务默认地址是 `https://defuzex.ai/api/agentdefuze`。`DEFUZEX_BASE_URL` 可覆盖 `create_run()` 的地址；明文 HTTP 只允许 loopback 地址。`DefuzeClient` 也支持显式 `base_url` 和 `timeout`：

```python
from defuzex import DefuzeClient

client = DefuzeClient(timeout=10.0)
entitlements = client.entitlements()
strategies = client.strategies()
judge_limits = client.judge_config()
```

这些读取返回 Backend 的公开动态配置。SDK 不缓存或推断服务端 scope、配额、计费或上传限制。

### 环境变量

| 变量 | 作用 |
|---|---|
| `DEFUZEX_API_KEY` | 官方 Provider 使用的 `dfx_` Bearer Key；优先级低于函数参数，高于凭证文件 |
| `DEFUZEX_BASE_URL` | 覆盖 `create_run()` 使用的 Website Backend public API base URL |
| `DEFUZEX_CONFIG_HOME` | 覆盖 `configure()`/凭证读取的用户级目录，适合隔离开发和测试环境 |

不要设置 MCP URL、模型 Key 或数据库地址；它们不是 SDK 配置。非 loopback 的 `DEFUZEX_BASE_URL` 必须使用 HTTPS，URL 中也不能包含 credentials。

## Provider 组合

是否传入 Provider 决定联网范围：

| Case | Judge | 行为 |
|---|---|---|
| 省略 | 省略 | 官方 Case + 官方 Judge；需要 API Key |
| 省略 | 自定义 | 官方 Case + 本地自定义 Judge；需要 API Key |
| 自定义 | 省略 | 本地自定义 Case + 官方 Judge；需要 API Key |
| 自定义 | 自定义 | 完全本地；自定义 Case 必须提供固定公开 rubric |
| 任意 | `judge=False` | 不创建 Judge Provider，Run 在最后一次提交后结束 |

自定义 Provider 可以是实现 Protocol 的对象，也可以是 callable：

```python
from defuzex import create_run
from defuzex.providers import CaseGenerationContext, JudgeContext


def make_case(context: CaseGenerationContext) -> dict[str, object]:
    return {
        "inputs": ["Inspect the repository safely."],
        "rubric": {"criteria": ["The result stays within the repository."]},
    }


def judge_locally(context: JudgeContext) -> dict[str, object]:
    return {"status": "pass", "confidence": 1.0}


run = create_run(
    repo_path=".",
    requirement_path="requirement.md",
    case_provider=make_case,
    judge_provider=judge_locally,
    max_inputs=1,
    allow_local=True,
)
```

所有 Case 和 Judgment 结果都会先归一化并验证，再进入 Run。官方 Provider 还会拒绝包含 Private Rubric、hidden answer、provider key、MCP 地址或模型配置的畸形响应。

## Run 生命周期

一个 `Run` 只对应一个完整 `Case`，并执行严格握手：

1. `create_run()` 完成离线预检、Provider 选择、Case 生成和归一化，返回 `state == "ready"` 的 Run。
2. `get_input()` 交付当前 Input 并开始本步 Evidence；重复调用会返回同一个 Input，不会前进。
3. 用户 Agent 执行任务。
4. `submit()` 验证 output/status，准备 Evidence，创建 `Submission`，原子记录 History 后才提交日志 offset 和 Trace 预算。
5. 还有 Input 时回到 `ready`；最后一步进入 `completed`。
6. `judge=True` 时最后一次 `submit()` 保持同步用户体验：Official Provider 在内部提交 v2 operation 并有界轮询，终态 Judgment 归一化为 `TestReport`，状态变为 `report_ready`。

在没有已交付 Input 时调用 `submit()`，或在错误状态调用 `get_input()`/`judge()`，会抛出 `InputProtocolError`。`wait=False` 不受支持，SDK 不启动后台队列。Judge 失败时已提交的 History 不会伪装回滚，Run 回到 `completed`，可以调用 `run.judge()` 重试。官方 Case/Judge 会复用已保存的幂等键；已取得 `operation_id` 时只继续 GET。`operation_wait_timeout` 会抛出可重试的 `DefuzeTimeoutError(code="operation_wait_timeout")`，不会删除恢复元数据。当前高层 API 不能在整个 Python 进程丢失 `Run` 对象后仅凭 `run_id` 重建该 Run；Judge 的恢复要求原 `Run` 对象及其 History 仍可用。

`run.cancel()` 会释放运行锁、取消当前 Evidence 事务并阻止迟到 Trace 进入其他 Run。建议在用户代码提前退出且尚未完成时显式调用它。

可观察属性：

- `run.run_id`、`run.case_id`、`run.strategy`、`run.max_inputs`
- `run.state`
- `run.history`：不可变的 `HistoryItem` tuple
- `run.report`：Judge 完成前为 `None`
- `run.runtime_warnings`：Evidence/Trace 降级，不包含伪造成功

## 用户 Agent、Docker 与 SDK 的责任边界

SDK 不启动 Agent，也不替用户选择模型、执行工具或赋予文件/网络权限。用户集成需要：

1. 将 SDK 和被测 Agent 安装在同一个 Docker 容器中；正式模式由 SDK 检查这一点。
2. 以 `get_input()` 取得测试输入，调用真实 Agent，再用 `submit()` 提交结果；不要让多个线程同时推进同一个 Run 的协议状态。
3. 为 Agent 设置符合自身风险模型的文件、命令、网络和 secret 权限。SDK 的 Evidence 扫描不能替代容器隔离或最小权限。
4. 在提前停止、异常退出或放弃当前 Run 时调用 `cancel()`，让运行锁和 Evidence 关联及时释放。

`allow_local=True` 只用于明确的本地开发/测试。它放宽“必须在 Docker 中”的检查，但不会提供沙箱，也不会改变公开网络、敏感扫描、协议顺序或单 active Run 限制。SDK 仓库不启动 Backend、Core 或模型服务；服务端部署与本地服务编排不是普通 SDK 调用的前置条件。

## Case、Submission 与 Judgment

公开契约位于 `defuzex.contracts`，并从顶层包导出常用类型：

- `DefuzeXInput`：一个已验证的 text 或 structured 输入。
- `Case`：至少包含一个 Input；官方 Case 不向 SDK 暴露私有 rubric。
- `Submission`：状态为 `completed`、`failed`、`timeout` 或 `aborted`，包含 output/error 和 Evidence 摘要。
- `HistoryItem`：强制 Input 与 Submission 的 run/case/input 标识一致。
- `TestReport`：状态为 `pass`、`issue` 或 `insufficient_evidence`；confidence 接受 Core 的 `low`/`medium`/`high`，自定义 Judge 也可返回 0–1 数值。
- `JudgeBatchResult`：官方同步批量 Judge 的单项 report 或稳定 error。

这些 dataclass 是不可变、深层 JSON 兼容的边界对象；未知主 schema 版本会被拒绝。高层 `Run` 使用单 Run Judge；高级调用者可通过 `OfficialJudgeProvider.judge_batch()` 同步提交最多由 Backend 动态配置允许的多个 `JudgeContext`。批量结果保持输入顺序，并隔离每项错误。

## Evidence

每次 `get_input()` 到 `submit()` 构成一个 Evidence 事务：

- Repo Meta 只收集相对路径、entry 类型、文件大小和基于这些字段的 SHA-256 fingerprint；不读取源码、README、Git 内容、绝对主机路径或 symlink 目标。
- 文件追踪记录前后 hash/size/mode 和 created/modified/deleted/renamed；默认不上传文本 diff。
- `logs=[...]` 只采集显式传入文件的增量；只有提交成功后才推进 offset。
- `CaptureStatus` 分别报告 snapshot、diff、logs、sensitive scan 和 traces 的 `complete/partial/failed/skipped`。
- `missing`、`dropped_count` 和 `runtime_warnings` 明确记录不完整证据。
- `save_local=True` 使用 pending file + rename 保存结构化步骤记录；它不替代服务端提交，也不会让失败请求看起来成功。

启动 Run 会创建被排除的 `.defuzex/` 目录，并在需要时向仓库 `.gitignore` 幂等加入 `/.defuzex/`。正式模式要求 SDK 与 Agent 在同一个 Docker 容器内，并通过 OS lock 限制每个容器一个 active Run；`allow_local=True` 仅显式放宽开发环境检查。

## OpenTelemetry Trace Evidence

DefuzeX 使用官方 OpenTelemetry `SpanProcessor`/`SpanExporter` 扩展点，不替换或重置用户已有的 `TracerProvider`：

```python
import json

from opentelemetry.sdk.trace import TracerProvider

from defuzex import create_run
from defuzex.otel import TraceEvidenceLimits, configure_trace_evidence

provider = TracerProvider()
trace_evidence = configure_trace_evidence(
    provider,
    limits=TraceEvidenceLimits(max_spans=100, max_total_bytes=256_000),
)
tracer = provider.get_tracer("my-agent")

run = create_run(
    repo_path=".",
    requirement_path="requirement.md",
    allow_local=True,
    trace_evidence=trace_evidence,
)

while (test_input := run.get_input()) is not None:
    with tracer.start_as_current_span("invoke_agent my-agent") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.request.model", "instrumented-model-name")
        output_messages = [
            {
                "role": "assistant",
                "parts": [{"type": "text", "content": str(test_input)}],
            }
        ]
        span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))
    report = run.submit()
```

成熟 Agent 的 instrumentation 通常负责写入这些 span 属性。SDK 只会自动采用 Agent/Workflow span attribute 或 event 中的标准输出，不会把普通 `chat` 模型调用误判为最终 Agent 结果。同一 span 的最后一个有效 event 优先于 attribute；多个候选按结束时间选择，时间相同时 Workflow 优先于 Agent，再以 span ID 稳定打破平局，重复值只保留一个候选。instrumentation 已明确记录最终输出时，即使 span 因通用控制流异常被 OTel 标为 `error`，该输出仍可提交，而 Trace 继续如实保留 `error` 状态。未提供标准字段、字段无效或超出 Trace 字节上限时，`submit()` 安全失败并要求兼容路径 `run.submit(output)`；显式 output 始终优先。

capture 只接收同一进程中，在当前 Input 已关联后开始并结束的 span；线程池 worker span 会在 start 时关联，cancel/finish 后结束的迟到 span 会被丢弃。它不提供 OTLP receiver、跨进程采集、Trace UI 或存储平台。

Trace Evidence 保留 trace/span/parent ID、name、kind、status、开始/结束/时长、受控 events、resource 和 instrumentation scope。普通 span attribute 默认拒绝，只允许必要的 `gen_ai` 模型、usage 和 latency 字段；resource 仅允许 service、deployment environment 和 OTel SDK 元数据。自动提交只在内存中读取最终 Agent 输出，原文不会复制进 Trace Evidence。prompt、completion、源码、文件内容、原始日志、token/API key 和 Private Rubric 永远不会因 `allow_sensitive=True` 被放行。

`TraceEvidenceLimits` 对 span 数、attribute 数、每 span event 数、文本长度和整个 Run 的紧凑 JSON 字节数设置硬上限。截断和丢弃通过 `truncated`、`dropped_count`、`reasons`、`capture_status.traces`、`missing` 与 `runtime_warnings` 暴露。Exporter、序列化或 flush 失败只降低 Trace Evidence，不破坏 `get_input()`、`submit()` 或 Judge。

成功捕获时，canonical 公共扩展为：

```text
Submission.extensions["trace_evidence"]
-> history[].submission.trace_evidence
-> schema_version == "defuzex.trace_evidence.v1"
```

## 错误处理

新代码应捕获 `defuzex.errors.DefuzeError` 或其稳定子类：

```python
from defuzex.errors import DefuzeError

try:
    report = run.judge()
except DefuzeError as exc:
    print(exc.code, exc.retryable, exc.request_id)
```

常用类型包括 `ConfigurationError`、`AuthenticationError`、`PermissionDeniedError`、`ValidationError`、`SensitiveDataError`、`LimitExceededError`、`InputProtocolError`、`ProviderError`、`DefuzeTimeoutError`、`ServiceBusyError` 和 `ServiceError`。`code` 与 `retryable` 用于程序判断；`details` 不会进入异常显示文本。Backend 内部错误详情不会透传，避免泄漏服务端上下文。`defuzex.exceptions` 只保留旧客户端异常名的兼容性。

POST 请求自动带 Bearer `dfx_` 凭证和幂等键。仅 Backend 明确标记为可重试的瞬态失败会在 `max_retries` 范围内做有上限的指数退避重试，且每次 POST 重试复用同一 body 和幂等键；operation GET 的网络瞬断可在总等待预算内继续。所有 `ServiceBusyError` 都不会自动重试。公网响应超过 8 MiB 会在解析前被拒绝。

## 隐私与边界

- SDK 只访问 Website Backend 的 `/sdk/` 公开路径，绝不接受 URL credentials，也不直接探测 Core MCP。
- 官方上传前扫描 output、error、log、diff、custom Case 和 repo path；默认发现高置信敏感内容即阻止提交。
- `allow_sensitive=True` 是普通 Evidence 的显式覆盖，不影响 OTel 的拒绝式 allowlist，也不允许协议出现私有字段。
- API Key 只用于 `Authorization` header，不进入 body、`repr()`、Repo Meta 或 Evidence。
- SDK 不拥有 API Key 策略、scope、配额、计费、Private Rubric、模型执行、Prompt、模型配置或数据库；这些是服务端职责。

## 深入文档与示例

- [SDK v4 架构](docs/architecture.md)：模块职责、依赖方向、Run 状态机、Evidence 事务和 OTel 适配。
- [公开 API Contract](docs/api-contract.md)：Website Backend base URL、鉴权、错误与公开服务摘要。
- [离线最小示例](examples/minimal_local.py)：无需凭证、网络或外部服务的单 Input 完整 Run。
- [Single Agent Template](examples/single_agent_template/README.md)：框架无关的单 Agent 接入骨架、官方模式占位与确定性成功/失败 smoke。
- [用户接入指南](examples/full_stack/USER_GUIDE.md)：从 GitHub 安装、API Key、requirement、用户 Agent 适配、Evidence 与结果检查。
- [真实用户流程 Notebook](examples/full_stack/defuzex_v4_real_user_flow.ipynb)：通过环境变量读取凭据，在用户选择的安全工作目录中运行官方 Case → Agent → Evidence → Judge 流程。
- 本 README 的自定义 Provider 示例不需要官方服务，但仍会创建 Run 工作目录；开发机需使用 `allow_local=True`。

## 目录结构

```text
src/defuzex/              Python 包与公开入口
  providers/              official/custom Case 与 Judge Provider 边界
  tracking/               snapshot、diff、log 与 Evidence 事务
docs/                     架构和公开 API contract
examples/full_stack/      用户侧 Docker、Notebook 与接入指南
examples/minimal_local.py 无凭证、无网络的最小公开示例
examples/single_agent_template/ 框架无关的单 Agent 接入模板
pyproject.toml            包元数据、可选依赖及 Ruff 配置
```

关键入口是 `src/defuzex/api.py` 的 `create_run()`、`src/defuzex/run.py` 的同步状态机，以及 `src/defuzex/backend.py` 的唯一公网 transport。业务代码应优先从 `defuzex` 和 `defuzex.providers` 的公开导出导入，而不是依赖以下划线开头的内部模块。

## 开发与验证

开发安装：

```bash
python -m pip install -e ".[dev]"
```

公开仓库质量门禁：

```bash
python -m ruff check --exclude "*.ipynb" .
python -m ruff format --check --exclude "*.ipynb" .
python -m compileall -q src examples
defuzex quickstart
python examples/minimal_local.py
```

公开 CI 验证静态质量、跨 Python 安装与导入、CLI、离线示例和发行物。维护者在接收发布前另行运行私有安全、协议和跨仓回归；公开镜像不包含内部验收资产或完整私有测试套件。

构建与包元数据验证使用 `[dev]` 已安装的 `build` 和 `twine`；它们不是 SDK runtime dependency：

```bash
python -m build
python -m twine check dist/*
```

CI 在 Ubuntu 上覆盖 Python 3.10–3.14 的安装、导入、CLI 与离线示例，并在 Windows/macOS 3.13 上复核相同用户路径。Docker 门只验证公开用户镜像可构建，不启动 Agent、不读取凭据：

```bash
docker build -f examples/full_stack/Dockerfile.user-flow -t defuzex-user-flow .
```

### 分支、验收与发布规范

- `main` 只保存经本仓明确负责人验收的正式代码；禁止直接在 `main` 开发或提交。
- 每位会修改仓库的人使用独立的 `dev/<owner>` 分支。不得多人共用一个开发分支，也不得把未经负责人验收的代码合入 `main`。
- 本仓负责人审查需求到代码/测试的映射和实际门禁证据，解决合并冲突，并且是把各 `dev/<owner>` 合入 `main` 的唯一明确责任人。作者不能自我批准。
- 正常 SDK 发布顺序是：`dev/<owner>` → 负责人验收并合入 `main` → 从 `main` 的确定 commit 构建并验证发行物 → 发布该发行物。仓库版本号本身不证明发行物已经发布。
- 热修复仍从独立 `dev/<owner>` 完成修复和回归测试，经负责人验收后合入 `main`；回滚应恢复到已验证 commit/发行物，不得直接修改已安装包后把结果反推为源码事实。
- `deploy` 只适用于实际部署到服务器的仓库，用来精确指向当前 EC2 运行代码。本仓是 Python 客户端库，不代表 EC2 运行服务，因此不需要 `deploy` 分支。对于需要服务器部署的兄弟仓库，顺序必须是：负责人验收合入 `main` → 从 `main` 的确定 commit 部署 EC2 → 线上验收通过后让 `deploy` 指向同一 commit；回滚后 `deploy` 也必须指向 EC2 实际运行的回滚 commit。
- 禁止在服务器直接改代码后只更新 `deploy`，也禁止把运行时配置、secret、凭证或数据库内容放入任何分支。

## FAQ

### 没有 API Key 可以使用 SDK 吗？

可以。使用自定义 Case Provider，并传入自定义 Judge 或 `judge=False`，即可完全本地运行；官方 Case 或官方 Judge 才需要 API Key。参见[离线最小示例](examples/minimal_local.py)。

### 为什么本地运行报 `DockerRequiredError`？

正式模式默认要求 SDK 与 Agent 同处一个 Docker 容器。仅在明确的本地开发或测试中设置 `allow_local=True`；它不会创建沙箱或降低其他安全校验。

### 为什么 `submit()` 返回 `None`？

非最后一个 Input、`judge=False`，或一次非 completed 提交尚未触发最终 Judge 时，`submit()` 可以返回 `None`。检查 `run.state` 和 `run.history`；Judge 成功后也可读取 `run.report`。

### OTel 是必需的吗？

不是。没有标准 Agent/Workflow span 输出时，直接调用 `run.submit(output)`。只有需要同进程 Trace Evidence 或自动提取最终输出时才安装 `[otel]` extra。

### operation 超时后会怎样？

SDK 抛出可重试的 `DefuzeTimeoutError(code="operation_wait_timeout")` 并保留有限恢复元数据。同一 Case 请求可复用请求身份；Judge 需要原 `Run` 对象和 History 才能从高层 API 重试。进程丢失整个 `Run` 后，当前不能只凭 `run_id` 重建。

### SDK 能直接连接 Core MCP、模型或数据库吗？

不能。SDK 唯一网络边界是 Website Backend 的公开 API；不要向 SDK 配置 MCP 地址、模型 Key、Prompt、Private Rubric 或数据库连接。

## 贡献、安全与许可证

- 贡献流程和本地门禁见 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 漏洞请按 [SECURITY.md](SECURITY.md) 私下报告，不要创建公开 issue。
- 本项目使用 [Apache License 2.0](LICENSE)。

## 当前限制

- Python Run API 仍是同步的；官方单 Case/Judge 内部使用 Backend v2 operation 有界轮询。批量 Judge 保持既有同步接口；SDK 不运行 Celery 或后台结果队列。
- 官方 Case 当前只生成文本 Input；结构化 Input 只能来自自定义 Provider。
- 正式 Run 默认必须与 Agent 同处一个 Docker 容器；本地运行必须显式 `allow_local=True`。
- 每个容器只有一个 active Run；一个 `Run` 也只允许一个当前 Input。
- OTel 仅采集同进程 span，不接收远程 OTLP，也不跨进程关联。
- SDK 不提供 Agent runner、服务端部署、UI、模型调用或数据库。
