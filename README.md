# 指令遵循自动评测原型

## 1. 项目简介

本项目用于评估外呼任务场景下，对话模型对任务指令的遵循情况。系统围绕“任务指令 → 结构化评测规范 → 对话评测 → 结果解释”这条链路，提供离线评测、模拟评测、规则校验、主观打分和演示页面。

当前版本定位为原型系统，重点解决以下问题：

- 将自然语言任务指令编译为可执行的 `Eval Spec`
- 对外呼对话进行结构化评测
- 输出总分、维度分、证据链和复核标记
- 支持多评委评分模式
- 支持通过页面演示评测与模拟流程

## 2. 主要能力

### 2.1 指令编译

- 输入原始任务指令
- 输出结构化 `Eval Spec`
- 支持版本化保存与查询

### 2.2 离线评测

- 输入 `Eval Spec`
- 输入完整对话转写
- 输出评测结果，包括：
  - 总分
  - 维度分
  - 规则命中结果
  - 主观打分结果
  - 证据片段
  - `needs_review` 标记

### 2.3 多评委评分机制

系统支持三档评分模式，默认模式为 `dual_arbitration`：

- `single`
  - 单评委模式
- `dual`
  - 双评委模式
  - 不启用仲裁
- `dual_arbitration`
  - 双评委 + 仲裁模式
  - 当主观评分分歧较大时触发仲裁评委

### 2.4 模拟评测

- 支持 mock 闭环模拟
- 支持通过 HTTP 接口接入真实被测模型
- 支持多类用户画像和场景分支

### 2.5 演示页面

- 支持预置案例和手动输入
- 支持评测模式与模拟模式切换
- 支持评分机制切换
- 支持查看多评委明细和仲裁记录

## 3. 项目结构

```text
app/
  api/            FastAPI 路由
  core/           配置与日志
  domain/         领域模型
  evaluators/     规则评估与 LLM 评委
  pipeline/       评测主流程
  reliability/    一致性与置信度
  reports/        结果汇总与导出
  simulators/     用户模拟与对话闭环
  spec/           指令编译器
  storage/        SQLite 存储
  web/            demo 页面静态资源

tests/            Python 与前端函数测试
docs/             设计文档与规划文档
```

## 4. 运行环境

### 4.1 Python

- 推荐版本：`Python 3.11+`

项目元数据定义见 `pyproject.toml`：

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `openai`
- `httpx`
- `python-dotenv`

开发测试依赖：

- `pytest`
- `pytest-cov`

### 4.2 可选前端运行环境

- `Node.js 18+`

用于执行 `tests/web/*.test.mjs` 这类前端函数级测试。

## 5. 安装与启动

以下示例以 PowerShell 为例。

### 5.1 创建虚拟环境

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 5.2 安装依赖

```powershell
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" pydantic openai httpx python-dotenv pytest pytest-cov
```

### 5.3 配置环境变量

复制模板文件：

```powershell
Copy-Item .env.example .env
```

然后修改 `.env`：

```env
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
DATABASE_PATH=instruction_following.db
JUDGE_RUNS=2
```

说明：

- 如果使用兼容 OpenAI API 的模型服务，可修改 `OPENAI_BASE_URL`
- 如果未配置可用模型服务，主观评分可能降级，结果更容易被标记为 `needs_review`

### 5.4 启动服务

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/health`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`
- 演示页面：`http://127.0.0.1:8000/demo`

## 6. 核心接口

### 6.1 健康检查

```http
GET /health
```

### 6.2 指令编译

```http
POST /specs/compile
```

请求示例：

```json
{
  "instruction_id": "instr_demo",
  "name": "确认收货时间",
  "raw_text": "请先确认用户身份，再确认收货时间，不要承诺一定送达。"
}
```

### 6.3 保存评测规范

```http
POST /specs
```

### 6.4 查询评测规范

```http
GET /specs/{spec_id}
```

### 6.5 单条评测

```http
POST /evaluations/run
```

请求示例：

```json
{
  "evaluation_mode": "dual_arbitration",
  "spec": {
    "spec_id": "spec_demo",
    "instruction_id": "instr_demo",
    "version": "v1",
    "task_goal": "确认收货时间",
    "required_steps": [],
    "required_slots": [],
    "soft_dimensions": [
      {
        "id": "task_focus",
        "name": "任务聚焦度",
        "weight": 1.0,
        "rubric": ["保持任务推进"]
      }
    ]
  },
  "conversation": {
    "conversation_id": "conv_demo",
    "instruction_id": "instr_demo",
    "turns": [
      { "turn_id": 1, "speaker": "agent", "text": "您好，我来确认收货时间" },
      { "turn_id": 2, "speaker": "user", "text": "明天下午可以" }
    ]
  }
}
```

返回重点字段：

- `evaluation_mode`
- `overall_score`
- `dimension_scores`
- `judge_results`
- `panel_results`
- `arbitration_records`
- `rule_results`
- `needs_review`

### 6.6 批量评测

```http
POST /evaluations/batch
```

执行后会输出批量结果，并生成 `batch_summary.csv`。

### 6.7 查询历史评测结果

```http
GET /evaluations/{run_id}
```

### 6.8 模拟评测

```http
POST /simulations/run
```

请求支持：

- `evaluation_mode`
- `adapter.type = mock | http`
- `simulation.profile_id`
- `simulation.primary_branch`
- `simulation.scenario_key`
- `simulation.batch_runs`

### 6.9 模型连通性检查

```http
POST /simulations/check-model
```

### 6.10 模型列表

```http
POST /simulations/list-models
```

## 7. 演示页面说明

访问：

```text
http://127.0.0.1:8000/demo
```

页面支持：

- 预置案例切换
- 手动输入任务指令和对话
- 评测模式 / 模拟模式切换
- 评分机制切换：
  - 单评委
  - 双评委
  - 双评委 + 仲裁
- 查看：
  - 总分
  - 评分模式
  - 主评委数
  - 仲裁次数
  - 多评委与仲裁详情

## 8. 测试

### 8.1 Python 测试

```powershell
python -m pytest -q
```

如只跑核心回归：

```powershell
python -m pytest tests/api/test_evaluations_api.py tests/evaluators/test_panel_judge.py tests/reliability/test_confidence.py -q
```

### 8.2 前端函数级测试

```powershell
node --test tests/web/*.test.mjs
```

说明：

- 某些受限环境下，Node 原生测试进程可能因为权限限制无法正常拉起子进程
- 这类问题通常是运行环境限制，不代表前端逻辑本身不可用

## 9. 数据与存储

当前默认使用 SQLite。

数据库初始化见：

- `app/storage/db.py`

当前主要表：

- `eval_spec`
- `evaluation_run`

数据库文件路径通过 `.env` 中的 `DATABASE_PATH` 配置。

## 10. 多评委模式说明

### 10.1 `single`

- 只使用 1 个主评委
- 适合快速试跑或成本敏感场景

### 10.2 `dual`

- 使用 2 个主评委
- 不启用仲裁
- 当主观场景判断冲突时，更容易走 `needs_review`

### 10.3 `dual_arbitration`

- 使用 2 个主评委
- 分歧较大时触发仲裁评委
- 当前是默认模式
- 适合强调公平性和稳健性的场景

## 11. 已知事项

- 项目当前为原型系统，不是完整生产系统
- 如果外部模型服务不可用，主观打分会降级，评测结果可能被标记为 `needs_review`
- 完整 Python 回归在本地环境中耗时可能较长
- 前端 demo 目前偏演示用途，适合内部评审、方案验证和接口联调

## 12. 后续可扩展方向

- 更细粒度的评委角色配置
- 更丰富的仲裁触发策略
- 批量评测任务管理
- 更完整的结果对比与回归面板
- 更稳定的模型服务适配与缓存机制
