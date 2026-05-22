# 履约数字人外呼指令遵循自动评估系统设计

## 1. 背景

在履约数字人外呼场景中，系统会自动向用户发起通话，并要求对话模型按照预设任务指令完成特定目标，例如信息确认、状态核验、异常处理与结束引导。现有人工评估方式存在以下问题：

- 任务流程复杂，人工逐条核查成本高。
- 评估标准不统一，跨标注员一致性弱。
- 结果常停留在“好/不好”的主观判断，难以复盘。
- 难以支持模型迭代后的批量回归评测。

本项目需要构建一套自动化评估原型，用于评估对话模型在外呼任务中的指令遵循效果，并满足“可解释、可量化、可复现、可扩展”的要求。

---

## 2. 目标与非目标

### 2.1 目标

第一版原型目标：

1. 支持离线评估：输入任务指令与完整对话文本/转写，输出结构化评估结果。
2. 支持混合评估：同时使用规则引擎与 LLM Judge。
3. 支持可解释输出：每个结论都能追溯到规则、轮次与证据文本。
4. 支持可量化输出：提供总分、维度分、硬性失败项、置信度。
5. 支持可靠性控制：提供一致性检查、低置信拦截、人工复核标记。
6. 为后续在线模拟评估预留接口，但第一版不实现完整用户模拟闭环。

### 2.2 非目标

第一版不追求：

- 全自动零人工配置地理解所有任务指令。
- 高拟真用户模拟器。
- 线上实时质检大屏。
- 大规模分布式评测调度。
- 仅凭单次 LLM 打分即作为最终权威结果。

---

## 3. 核心设计原则

### 3.1 Eval Spec 作为核心中间层

系统不直接用原始自然语言任务指令进行评分，而是先将其编译为结构化评估规范 `Eval Spec`。  
`Eval Spec` 是后续规则判断、LLM 评审、结果解释、版本回归的唯一评估依据。

这样做的原因：

- 将模糊指令转化为稳定的检查对象。
- 将“评什么”与“怎么评”从运行时对话样本中解耦。
- 让评估标准可审阅、可编辑、可版本化。
- 降低 LLM 评估过程的漂移和主观性。

### 3.2 硬约束与软约束分治

- **硬约束**：流程是否执行、槽位是否收集、禁用话术是否触发、步骤顺序是否正确。使用规则引擎判定。
- **软约束**：解释是否充分、追问是否合理、异议处理是否得体。使用 LLM Judge 判定。

### 3.3 证据优先

任何得分或扣分都必须绑定证据：

- 命中的规则或评审维度
- 对话轮次编号
- 证据片段
- 结论理由

### 3.4 低置信不强判

当样本存在解析失败、模型评审分歧大或证据不足时，系统应输出 `needs_review=true`，而不是给出看似确定但不可靠的结论。

---

## 4. 评估对象与范围

第一版按“离线优先、在线预留”设计。

### 4.1 当前范围

- 输入任务指令
- 输入外呼对话转写
- 支持 2~3 类代表性任务模板
  - 单一确认类
  - 多步骤流程类
  - 混合收集/核验类

### 4.2 未来扩展范围

- 在线模拟用户与模型对话
- 多轮任务树探索
- 多策略用户画像覆盖
- 回归集自动跑批

---

## 5. 总体架构

系统采用六层架构：

1. **任务规范层**
2. **对话理解层**
3. **评估执行层**
4. **聚合评分层**
5. **可解释输出层**
6. **可靠性控制层**

对应主流程：

1. 输入原始任务指令
2. 编译或加载 `Eval Spec`
3. 输入对话转写
4. 提取对话事实表示
5. 规则引擎执行硬约束评估
6. LLM Judge 执行软约束评估
7. 聚合为总分与维度结果
8. 输出评分卡、证据链、置信度与复核建议

---

## 6. 领域模型

### 6.1 TaskInstruction

表示原始任务指令。

建议字段：

- `instruction_id`
- `name`
- `business_scene`
- `raw_text`
- `version`
- `created_at`

### 6.2 EvalSpec

表示结构化评估规范，是核心领域对象。

建议字段：

- `spec_id`
- `instruction_id`
- `version`
- `task_goal`
- `preconditions`
- `required_steps`
- `optional_steps`
- `forbidden_actions`
- `required_slots`
- `completion_conditions`
- `hard_fail_conditions`
- `soft_dimensions`
- `scoring_policy`
- `evidence_policy`
- `review_status`

### 6.3 Conversation

表示待评估对话。

建议字段：

- `conversation_id`
- `instruction_id`
- `source`
- `turns`
- `metadata`
  - 通话时间
  - 渠道
  - ASR 质量信息
  - 业务标签

其中 `turns` 至少包括：

- `turn_id`
- `speaker`（agent/user/system）
- `text`
- `timestamp_start`
- `timestamp_end`

### 6.4 FactTimeline

表示从对话中抽取出的结构化事实时间线。

建议包含：

- 动作事件
- 槽位填写事件
- 状态转移事件
- 证据引用

### 6.5 EvaluationResult

表示一次完整评估输出。

建议字段：

- `run_id`
- `conversation_id`
- `spec_id`
- `overall_score`
- `dimension_scores`
- `hard_fail`
- `confidence`
- `needs_review`
- `rule_results`
- `judge_results`
- `evidence_items`
- `summary`

---

## 7. Eval Spec 设计

`Eval Spec` 是该系统最关键的设计对象。第一版采用“LLM 草拟 + 人工确认 + 版本入库”的模式。

### 7.1 Eval Spec 结构建议

```json
{
  "spec_id": "spec_xxx",
  "instruction_id": "instr_xxx",
  "version": "v1",
  "task_goal": "完成收货时间确认并在无法确认时收集替代方案",
  "required_steps": [
    {
      "id": "step_identity_check",
      "name": "确认用户身份",
      "order": 1,
      "required": true,
      "evidence_requirement": "需要明确身份确认话术或等价表达"
    }
  ],
  "required_slots": [
    {
      "name": "delivery_time",
      "required": true,
      "accepted_values": ["今天", "明天", "具体时间段"]
    }
  ],
  "forbidden_actions": [
    {
      "id": "forbid_false_promise",
      "description": "禁止承诺无法保证的配送时效"
    }
  ],
  "completion_conditions": [
    "已确认关键槽位或已明确记录失败原因",
    "以合规结束语收尾"
  ],
  "hard_fail_conditions": [
    "未确认身份直接询问隐私信息",
    "触发禁用承诺"
  ],
  "soft_dimensions": [
    {
      "id": "soft_explanation_quality",
      "name": "解释充分性",
      "weight": 0.2,
      "rubric": [
        "是否说明来电目的",
        "是否解释追问原因",
        "是否减少用户困惑"
      ]
    }
  ],
  "scoring_policy": {
    "hard_rules_weight": 0.7,
    "soft_rules_weight": 0.3,
    "hard_fail_zero_out": true
  }
}
```

### 7.2 Eval Spec 生成流程

1. 输入原始任务指令
2. 通过 Spec Compiler 生成结构化草案
3. 输出待审阅 Spec
4. 人工修订并确认
5. 以版本化形式保存

### 7.3 Eval Spec 维护原则

- 同一任务允许多版本并存
- 评估结果必须记录所使用的 Spec 版本
- 修改评分标准时不覆盖历史版本

---

## 8. 对话理解层设计

该层的目标不是直接评分，而是将原始对话转为可检查事实。

### 8.1 输入

- `Eval Spec`
- 对话转写文本
- 可选元信息（ASR 分段、时间戳、角色标签）

### 8.2 输出

- 标准化轮次列表
- 角色识别结果
- 动作事件列表
- 槽位提取结果
- 状态流转结果
- 异议/拒绝/确认等对话信号

### 8.3 关键子模块

#### 8.3.1 预处理器

职责：

- 清洗无效空白
- 标准化标点和特殊词
- 修正明显格式问题
- 合并/切分异常轮次

#### 8.3.2 Dialogue Parser

职责：

- 轮次切分
- 说话方归一化
- 时间线整理

#### 8.3.3 Fact Extractor

职责：

- 识别对话动作
- 提取槽位
- 识别显式确认、拒绝、反问、结束
- 将结果组织为 `FactTimeline`

### 8.4 动作类型建议

第一版建议至少支持：

- `greet`
- `identity_check`
- `state_explanation`
- `slot_ask`
- `slot_confirm`
- `clarification`
- `objection_handle`
- `promise`
- `end_call`

---

## 9. 评估执行层设计

### 9.1 Rule Engine

用于执行硬约束判断。

规则类型建议：

1. **流程规则**
   - 是否执行必做步骤
   - 是否满足顺序约束
   - 是否触发结束条件

2. **槽位规则**
   - 是否收集必要槽位
   - 槽位是否有效
   - 槽位确认是否闭环

3. **禁用规则**
   - 是否出现禁止行为
   - 是否触发一票否决

4. **一致性规则**
   - 前后说法是否冲突
   - 是否在未满足前提时执行后续动作

规则结果结构建议：

- `rule_id`
- `passed`
- `score_delta`
- `severity`
- `evidence_turn_ids`
- `reason`

### 9.2 LLM Judge

用于执行软约束评审。

评审维度建议：

- 解释充分性
- 追问合理性
- 异议处理质量
- 对任务目标的聚焦程度
- 结束方式自然性与完整性

LLM Judge 输出必须严格结构化：

- `dimension_id`
- `score`
- `confidence`
- `reason`
- `evidence_turn_ids`

### 9.3 LLM Judge 使用原则

- 不直接裁决硬规则
- 必须绑定证据轮次
- 必须使用 rubric 进行维度评分
- 对证据不足的项输出低置信而非强判

---

## 10. 聚合评分层设计

### 10.1 输出目标

输出统一评分卡：

- 总分
- 硬规则分
- 软规则分
- 各维度子分
- 致命失败项
- 置信度
- 是否建议人工复核

### 10.2 推荐评分策略

第一版采用“硬优先、软补充”的策略：

```text
总分 = 硬规则得分 * 0.7 + 软规则得分 * 0.3
```

同时支持：

- 若命中 `hard_fail_conditions`，则 `hard_fail=true`
- 一票否决任务可直接将总分压到 0 或限制上限

### 10.3 置信度计算建议

综合以下因素：

- 对话解析完整度
- 证据覆盖率
- LLM 多次评审一致性
- 关键维度是否存在冲突

---

## 11. 可解释输出层设计

该层负责将机器判断转化为业务可读报告。

### 11.1 输出形式

1. **评分卡**
   - 总分
   - 子项分
   - 风险标记

2. **证据链**
   - 每条规则的命中/未命中情况
   - 对应轮次与证据文本

3. **失败树**
   - 从最终扣分回溯到规则与对话证据

4. **摘要说明**
   - 简短解释这次评估好在哪里、差在哪里

### 11.2 证据项结构建议

- `evidence_id`
- `source_type`（rule/judge/parser）
- `turn_ids`
- `quote`
- `linked_decision`
- `note`

---

## 12. 可靠性控制层设计

可解释不等于可靠，第一版必须引入基础可靠性机制。

### 12.1 结构化输出约束

所有 LLM 输出都必须受 schema 约束，禁止自由文本直接进入最终结果。

### 12.2 一致性检查

同一样本可重复评审 2~3 次，比较：

- 维度分波动
- 证据轮次是否一致
- 最终结论是否一致

若波动超阈值，则标记低置信。

### 12.3 低置信拦截

以下情况建议 `needs_review=true`：

- 对话轮次解析失败率高
- 关键槽位证据不足
- 规则结果与 LLM 评审严重冲突
- LLM 多次评审一致性低

### 12.4 人工标注校准集

建立一个小规模高质量标注集，用于：

- 校准评分阈值
- 对比人机一致性
- 评估各维度稳定性

---

## 13. 存储设计

原型阶段使用 SQLite 即可。

建议表：

### 13.1 `task_instruction`

- 存原始任务指令

### 13.2 `eval_spec`

- 存版本化的结构化评估规范

### 13.3 `conversation`

- 存原始对话样本与元数据

### 13.4 `evaluation_run`

- 存一次完整评估结果

### 13.5 `evaluation_evidence`

- 存证据项，支持按 run 回溯

### 13.6 `calibration_label`

- 存人工标注与校准信息

---

## 14. API 设计

第一版采用 FastAPI，优先提供离线评估接口，并为在线模拟预留路由。

### 14.1 Spec 相关

#### `POST /specs/compile`

输入：原始任务指令  
输出：`Eval Spec` 草案

#### `POST /specs`

输入：人工确认后的 `Eval Spec`  
输出：保存结果与版本号

#### `GET /specs/{spec_id}`

获取指定版本 Spec

### 14.2 评估相关

#### `POST /evaluations/run`

输入：

- `spec_id` 或原始任务指令
- 对话文本/转写

输出：

- 评分卡
- 规则结果
- LLM 结果
- 证据链
- 置信度

#### `POST /evaluations/batch`

输入：批量样本  
输出：批量评估任务结果

#### `GET /evaluations/{run_id}`

查询单次评估详情

### 14.3 在线模拟预留

#### `POST /simulations/run`

当前第一版只预留接口定义，不实现复杂逻辑。

未来输入：

- `spec_id`
- 被测模型配置
- 用户画像或场景模板

未来输出：

- 对话过程
- 评估结果

---

## 15. 异常处理与降级策略

第一版原型需要明确“评不出来时怎么办”，否则容易出现伪确定性输出。

### 15.1 Spec 缺失或未审核

- 若输入原始任务指令但未能成功编译出 `Eval Spec`，则拒绝进入正式评估。
- 若 `Eval Spec` 处于未审核状态，可允许进入“试运行模式”，但结果必须打上 `spec_unapproved=true`。

### 15.2 对话解析失败

- 若轮次切分失败或角色识别失败达到阈值，则直接输出 `needs_review=true`。
- 若仅局部轮次异常，则允许继续评估，但需要在结果中记录 `parse_warnings`。

### 15.3 规则执行异常

- 单条规则执行失败不应中断整次评估。
- 失败规则应输出 `status=error`，并写明错误原因。
- 聚合器在汇总时应区分“未通过”和“未成功执行”。

### 15.4 LLM 调用异常或超时

- 若 LLM Judge 超时或返回非结构化结果，系统应自动重试有限次数。
- 若重试后仍失败，则降级为“仅规则评估”模式。
- 降级结果必须显式标记 `soft_eval_skipped=true`，且降低整体置信度。

### 15.5 证据不足

- 当结论无法绑定足够证据时，不允许输出高置信判断。
- 若关键维度证据缺失，应将该维度标记为 `insufficient_evidence`。

### 15.6 输出策略

- 系统优先输出“部分可用且带风险标记”的结果，而不是直接返回空结果。
- 只有在 `Eval Spec` 缺失或输入不可解析时，才返回不可评估状态。

---

## 16. 代码组织建议

```text
app/
  api/
    routes_eval.py
    routes_simulation.py

  core/
    config.py
    logging.py
    models.py

  domain/
    task_instruction.py
    eval_spec.py
    conversation.py
    evaluation_result.py

  spec/
    compiler.py
    templates/
    schemas/

  pipeline/
    preprocess.py
    dialogue_parser.py
    fact_extractor.py
    evaluation_runner.py
    aggregator.py

  evaluators/
    rules/
      base.py
      flow_rules.py
      slot_rules.py
      forbidden_rules.py
    judge/
      llm_adapter.py
      rubric_judge.py
      consistency_judge.py

  reliability/
    confidence.py
    agreement.py
    calibration.py

  reports/
    scorecard.py
    evidence_trace.py
    exporter.py

  simulators/
    scenario_generator.py
    user_simulator.py
    conversation_runner.py

  storage/
    repo_task.py
    repo_eval.py
    repo_dataset.py

  main.py
```

---

## 17. 第一版交付边界

### 16.1 必做

1. 支持任务指令到 `Eval Spec` 的草案生成
2. 支持 2~3 类任务模板
3. 支持单条与批量离线评估
4. 支持规则评估与 LLM 评估混合执行
5. 支持结构化证据输出
6. 支持基础一致性与低置信标记

### 16.2 可延后

1. 完整在线用户模拟
2. 复杂场景树自动生成
3. 大规模回归平台化
4. 高级仪表盘与 BI 展示

---

## 18. 测试与验收建议

### 17.1 单元测试

- Spec 编译器
- 规则引擎
- 槽位提取
- 聚合器
- 置信度计算

### 17.2 集成测试

- 从原始指令到评估结果的完整链路
- 批量评估链路
- 错误输入与空输入处理

### 17.3 校准测试

- 使用人工标注样本验证人机一致性
- 检查重复运行波动范围
- 检查低置信样本是否被正确拦截

### 17.4 验收标准

第一版可视为达到验收条件，当且仅当：

1. 能稳定输出结构化评估结果；
2. 每个结论均可回溯到具体证据；
3. 至少支持 2~3 类任务模板；
4. 对低置信样本能明确标记人工复核；
5. 能支持后续接入在线模拟评估。

---

## 19. 关键决策汇总

1. **采用 Python + FastAPI + Pydantic + SQLite 作为原型技术底座。**
2. **采用混合架构：规则引擎负责硬约束，LLM Judge 负责软约束。**
3. **采用 `Eval Spec` 作为评估核心中间层。**
4. **第一版采用离线优先设计，并为在线模拟预留接口。**
5. **第一版采用“LLM 草拟 Spec + 人工确认 + 版本化管理”的机制。**

---

## 20. 后续实现建议

下一步进入实现计划时，应优先拆出以下实施顺序：

1. 建立基础项目骨架与领域模型
2. 定义 `Eval Spec` schema 与编译接口
3. 打通离线单条评估主链路
4. 接入基础规则引擎
5. 接入 LLM Judge 与结构化输出
6. 增加证据链与可靠性模块
7. 补齐批量评估与在线模拟接口占位

该顺序可以保证尽早得到一个可运行、可解释、可演示的原型。
