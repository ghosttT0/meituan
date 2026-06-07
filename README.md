# DialEval · 多轮对话指令遵循评测系统

针对外呼任务场景，对对话模型的**指令遵循能力**进行可解释、可量化的自动评测。

---

## 核心功能

| 模块 | 说明 |
|---|---|
| 用户模拟器 | 7种用户画像 + 情绪状态机，模拟真实外呼场景 |
| 硬规则引擎 | 必需步骤、必需槽位、禁止行为、场景规则（语义感知） |
| 多评委软评分 | 双评委 + 仲裁机制，对主观维度打分 |
| 聚合评分 | 硬软双轨加权，支持按任务类型调整权重 |
| 可解释报告 | 证据链、失效模式分类、改进建议 |

---

## 评分公式

### 总分

```
总分 = hard_score × w_h + soft_score × w_s
```

默认 `w_h = 0.7`，`w_s = 0.3`，可通过 `EvalSpec.scoring_policy` 按任务调整。  
触发 `fatal` 级硬规则（违规承诺）时总分强制归零。

---

### 硬规则得分

```
hard_score = Σ(δ_i × w_i) / Σ(w_i) × 100

  δ_i ∈ {0,1}  规则 i 是否通过
  w_i           规则权重（RuleResult.weight）
```

| 规则 | 权重 | 失败影响 |
|---|---|---|
| `required_steps` | 1.0 | 扣分 |
| `required_slots` | 1.0 | 扣分 |
| `forbidden_actions` | 1.0 | fatal → 总分归零 |
| `scenario_faq_grounding` | 2.0 | 扣分 |
| `scenario_busy_focus` | 1.8 | 扣分 |
| `scenario_scope_fallback` | 2.2 | 扣分 |
| `scenario_hesitant_clarity` | 1.9 | 扣分 |

场景规则使用 **embedding 语义匹配**，不可用时退回关键词匹配。

---

### 软评分得分

```
soft_score = Σ(s_j × w_j) / Σ(w_j) × 100

  s_j ∈ [0,1]  评委对维度 j 的最终共识分
  w_j           维度权重（SoftDimension.weight）
```

**多评委流程：**

```
judge_a (task_alignment)  ──┐
                             ├── 分歧 ≥ 0.25 ──> judge_c (arbitrator)
judge_b (experience_risk) ──┘
```

分歧小于阈值取两个主评委平均分，否则使用仲裁评委结果。

---

### 维度权重（按任务类型）

| task_type | 任务完成度 | 对话效率 | 用户体验 | 鲁棒性 |
|---|---|---|---|---|
| `outbound_sign` 催收/签约 | 50% | 20% | 20% | 10% |
| `survey` 满意度回访 | 20% | 15% | 50% | 15% |
| `faq_service` FAQ解答 | 35% | 30% | 25% | 10% |
| `general` 默认 | 40% | 20% | 30% | 10% |

---

### 鲁棒性得分

```
robustness = 100 - n × 20    （n = 场景规则失败数）
           = 0               （触发违规承诺）
```

---

### 置信度

```
confidence = 0.9
           - min(|warnings| × 0.1,  0.3)
           - (1 - agreement)       × 0.4
           - max(0, 0.7 - c̄_j)    × 0.5
           - 0.2  （soft_eval_skipped 时）

agreement   = 1 - score_span
score_span  = 各维度评委评分最大差值的均值
c̄_j        = 评委自身平均置信度
```

---

## 用户画像

| 画像 | 特征 | 情绪起点 |
|---|---|---|
| `cooperative` 配合型 | 随和，愿意配合 | neutral |
| `hesitant` 犹豫型 | 担心费用/风险，需解释 | skeptical |
| `questioning` 追问型 | 连续追问细节 | skeptical |
| `interrupting` 打断型 | 频繁插话，跳跃 | skeptical |
| `busy` 忙碌型 | 耐心极低，要求说重点 | resistant |
| `rejecting` 拒绝型 | 强硬拒绝 | resistant |
| `uninformed` 信息不对称型 | 记不清签约情况，容易困惑 | neutral |

**情绪演变：** `neutral → skeptical → resistant → rejecting`

- 触发违规承诺 → 直接跳到 `rejecting`
- 未解释原因 → 按 `patience_level` 概率恶化
- 充分解释 → 情绪改善

---

## 对话失效模式

| 模式 | 含义 |
|---|---|
| `SLOT_ABANDONMENT` | 槽位收集中断 |
| `FORBIDDEN_PROMISE` | 违规承诺 |
| `MISSING_FLOW` | 必需步骤缺失 |
| `TOPIC_DRIFT` | 未回应场景关键信息 |
| `LOOP_STUTTER` | 同一状态循环超过 2 次 |
| `ABRUPT_END` | 任务未完成时强制终止 |

---

## 快速开始

```bash
pip install -e ".[dev]"
cp .env.example .env   # 见下方配置说明
uvicorn app.main:app --reload
pytest tests/
```

### 环境变量配置

`.env` 文件需要填写以下配置：

```env
# 评委 LLM（用于软评分和场景规则复核）
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# 用户模拟器 LLM（未配置时降级使用上面的配置）
SIMULATOR_API_KEY=your_key
SIMULATOR_BASE_URL=https://api.deepseek.com/v1
SIMULATOR_MODEL=deepseek-chat
```

> **注意：** 评委 LLM 和用户模拟器是系统内部使用的，与**被测模型**完全分开。
>
> 被测模型需要在**前端页面**里单独配置：
> - 打开 Demo 页面后，在「模型接入」区域填写被测模型的 **API Endpoint**、**API Key** 和 **Model Name**
> - 被测模型可以是任何兼容 OpenAI Chat Completions 协议的服务
> - 每次运行模拟前确认被测模型地址可访问，否则对话会回退到 Mock 演示模式

### 任务指令占位符

任务指令文本支持以下占位符，系统会在模拟启动时自动替换：

| 占位符 | 说明 |
|---|---|
| `${rider_name}` | 随机生成中文骑手姓名 |

---

## 项目结构

```
app/
├── domain/        数据模型（EvalSpec, Conversation, EvaluationResult）
├── pipeline/      评估流水线（DialogueParser → Rules → Panel → Aggregator）
├── evaluators/
│   ├── rules/     硬规则（flow, slot, forbidden, scenario + 语义匹配）
│   └── judge/     软评分（LLM适配层, PanelJudge）
├── simulators/    用户模拟器（画像, 情绪引擎, 问题池, 策略引擎）
├── reliability/   置信度与评委一致性
├── reports/       评测报告（证据链, 失效模式分类, 摘要）
└── api/           FastAPI 路由
```
