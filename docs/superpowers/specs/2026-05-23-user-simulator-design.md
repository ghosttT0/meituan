# 用户模拟器设计：用于外呼任务对话模型的在线闭环测试

## 1. 背景

当前原型已经具备：

- 任务指令编译能力
- 离线对话评估能力
- 结构化评分输出
- Demo Web 页面展示

但仍未完成交付目标中的关键部分：

> 构建用户模拟器，能够充分有效测试对话模型在特定任务指令下的效果。

当前系统中与模拟器相关的状态是：

- `POST /simulations/run` 仍为占位接口
- 没有用户画像
- 没有场景生成器
- 没有多轮对话闭环执行器
- 没有用于模拟“忙碌 / 拒绝 / 犹豫 / 追问 / 打断”等常见阻碍的状态机

因此，本次需要为“用户模拟器”设计一个第一版可落地方案。

---

## 2. 目标

本次用户模拟器设计目标是：

1. 支持 **在线闭环测试**：用户模拟器与被测模型真实多轮对话；
2. 保留 **离线调试模式**：可单独测试用户策略和回复生成；
3. 支持 **规则控流程 + LLM 生成人味表达** 的混合方案；
4. 第一版覆盖 **主流程 + 常见阻碍**；
5. 不假设当前已有统一模型接入方式，先定义 **模型适配层**；
6. 最终对话可直接复用现有 evaluator 自动评分。

---

## 3. 非目标

本次设计不追求：

- 高拟真的开放世界用户模拟
- 无限多轮自由对话
- 完整情绪模型
- 完整业务规则执行器
- 多智能体大规模仿真平台

本次重点是：

> 做出一个**可控、可解释、可扩展**的第一版用户模拟器原型。

---

## 4. 核心结论

本次用户模拟器采用以下总体方案：

> **在线闭环为主，保留离线调试；规则控制状态流转，LLM 负责局部自然表达。**

这意味着：

- 用户模拟器不会完全随机生成回复；
- 主流程、阻碍类型、结束条件都由规则控制；
- LLM 只负责把当前“用户策略意图”表达成自然语言。

---

## 5. 已确认的设计约束

根据本轮沟通，已确定：

### 5.1 交付形态

采用 **混合型**：

- 在线闭环主链路
- 保留离线调试入口

### 5.2 模拟策略

采用 **混合型**：

- 规则控制主流程和边界
- LLM 生成人味表达

### 5.3 覆盖范围

第一版优先覆盖：

- 配合
- 犹豫
- 拒绝
- 忙碌
- 打断
- 追问

### 5.4 被测模型接入

当前没有统一接入方式，因此本次设计必须引入：

- **模型适配层（Model Adapter Layer）**

---

## 6. 总体架构

用户模拟器建议拆成 6 个模块：

1. **Scenario Builder**
2. **User Profile**
3. **User Policy Engine**
4. **User Response Generator**
5. **Model Adapter**
6. **Conversation Runner**

---

## 7. 模块设计

## 7.1 Scenario Builder

职责：

- 从 `EvalSpec` 生成一轮模拟运行的场景配置；
- 定义这次测试更偏主流程验证还是阻碍验证；
- 指定初始用户画像、目标分支、结束条件、最大轮次。

### 输入

- `EvalSpec`
- 测试配置
  - `scenario_seed`
  - `max_turns`
  - `target_outcome`
  - `coverage_mode`

### 输出

- `SimulationScenario`

建议字段：

- `scenario_id`
- `spec_id`
- `profile_id`
- `primary_branch`
- `secondary_branch`
- `max_turns`
- `termination_policy`

---

## 7.2 User Profile

职责：

- 定义不同类型用户的性格、合作程度、阻碍倾向与表达特征。

第一版不做复杂人格学建模，只做任务测试需要的行为配置。

### 第一版建议画像

1. `cooperative`
2. `hesitant`
3. `rejecting`
4. `busy`
5. `interrupting`
6. `questioning`

### 建议字段

- `profile_id`
- `name`
- `cooperation_level`
- `patience_level`
- `interruption_probability`
- `question_probability`
- `reject_probability`
- `style_prompt`

---

## 7.3 User Policy Engine

这是模拟器的核心控制器。

职责：

- 根据当前场景、用户画像、对话历史、模型行为信号，决定下一步用户策略；
- 控制状态流转；
- 决定当前用户是配合、拒绝、追问、打断还是结束。

### 输入

- `SimulationScenario`
- `UserProfile`
- `ConversationState`
- 被测模型上一轮回复分析结果

### 输出

- `UserIntent`

例如：

- `answer_slot`
- `ask_why`
- `say_busy`
- `interrupt`
- `refuse`
- `accept`
- `end_call`

### 设计原则

- 不直接输出自然语言
- 只输出结构化策略意图

---

## 7.4 User Response Generator

职责：

- 将 `UserIntent` 转换为自然语言回复。

### 两种生成方式

#### A. 模板生成

适合：

- 忙碌
- 打断
- 拒绝
- 简单确认

#### B. LLM 生成

适合：

- 追问
- 犹豫
- 模糊表达
- 更自然的场景还原

### 第一版建议

优先采用：

- 模板优先
- LLM 补自然表达

即：

- 能模板表达的优先模板
- 需要自然变化时再调用 LLM

---

## 7.5 Model Adapter

由于当前没有统一被测模型接入方式，因此必须设计适配层。

### 目标

定义统一接口，不绑定具体实现。

### 建议接口

- `start_session()`
- `send_user_message()`
- `get_model_reply()`
- `end_session()`

### 第一版建议实现

- `MockModelAdapter`
- `HttpModelAdapter`
- `SdkModelAdapter`（接口预留）

### 作用

- 让模拟器不依赖被测模型接入方式
- 让在线闭环和离线调试共用同一套 runner

---

## 7.6 Conversation Runner

职责：

- 驱动用户模拟器与被测模型多轮对话；
- 控制 session 生命周期；
- 记录完整会话；
- 对话结束后调用现有 evaluator 自动评测。

### 主流程

1. 加载 `EvalSpec`
2. 生成 `SimulationScenario`
3. 初始化 `UserProfile`
4. 启动 `ModelAdapter`
5. 按轮次循环：
   - 用户策略引擎产出 `UserIntent`
   - 回复生成器产出用户话术
   - 发送给被测模型
   - 获取模型回复
   - 更新会话状态
6. 触发结束条件
7. 将完整对话送入 evaluator
8. 输出模拟结果 + 评测结果

---

## 8. 状态机设计

## 8.1 第一版状态

建议状态集合：

- `init`
- `listening`
- `cooperative`
- `hesitant`
- `interrupting`
- `questioning`
- `busy`
- `rejecting`
- `ending`
- `terminated`

### 含义说明

#### `init`
通话刚开始，尚未完成开场识别。

#### `listening`
用户在听模型说明，等待决定如何反应。

#### `cooperative`
用户愿意配合，主流程可推进。

#### `hesitant`
用户不确定，需要模型补充解释或鼓励。

#### `interrupting`
用户打断模型，测试模型是否能恢复主线。

#### `questioning`
用户追问原因、规则、利益、后果等。

#### `busy`
用户没空、着急结束、时间不足。

#### `rejecting`
用户明确表达拒绝，不愿继续推进。

#### `ending`
用户已接近结束，需要模型体面收尾。

#### `terminated`
本轮模拟结束。

---

## 8.2 第一版覆盖分支

### 1. 配合型

- 正常回答
- 主流程顺利推进

### 2. 犹豫型

- “我不太确定”
- “我再想想”
- 测试模型是否会补充解释

### 3. 拒绝型

- “我不想参加”
- “我今天做不了”
- 测试模型是否挽留或合理结束

### 4. 忙碌型

- “我现在忙”
- “先这样吧”
- 测试模型是否能快速说明重点或结束

### 5. 打断型

- 模型未说完时插话
- 测试模型是否恢复主线

### 6. 追问型

- “为什么必须这样？”
- “这个规则是谁定的？”
- 测试模型是否用 FAQ / Knowledge Points 回答

---

## 8.3 状态转移原则

状态转移由两类信号共同决定：

### A. 规则信号

- 当前场景预设分支
- 当前阻碍是否已释放
- 当前轮是否该进入结束
- 最大轮次是否已到

### B. 模型行为信号

- 是否解释清楚
- 是否命中关键步骤
- 是否回应用户问题
- 是否触发违规承诺
- 是否忽略用户 busy / reject 信号

### 结论

用户模拟器不是随机回复器，而是：

> **根据模型当前表现动态决定下一轮用户状态与回复策略。**

---

## 9. 被测模型行为分析层

为了让状态机能根据模型表现转移，需要加入一个轻量行为分析层。

职责：

- 分析被测模型当前回复
- 判断是否：
  - 回答了问题
  - 解释了原因
  - 命中了任务流程
  - 触发了不当承诺
  - 忽略了用户阻碍

第一版可以采用：

- 规则分析优先
- 必要时可加 LLM 评分

输出：

- `ModelReplySignal`

建议字段：

- `answered_question`
- `explained_reason`
- `followed_flow_step`
- `triggered_forbidden_action`
- `ignored_user_state`

---

## 10. 模拟结果输出

单次模拟运行结束后，建议输出两部分结果：

### 10.1 模拟过程结果

- `scenario_id`
- `profile_id`
- `turns`
- `state_trace`
- `termination_reason`

### 10.2 评测结果

复用现有 evaluator 输出：

- `overall_score`
- `dimension_scores`
- `hard_fail`
- `confidence`
- `rule_results`
- `judge_results`
- `evidence_items`

这样一轮模拟就同时具备：

- 用户行为可解释性
- 模型表现可解释性
- 结果量化输出

---

## 11. 离线调试模式

虽然主形态是在线闭环，但需要保留离线调试模式。

### 作用

- 单测用户状态机
- 单测用户策略生成
- 在没接入真实模型前验证场景逻辑
- 调试阻碍分支覆盖率

### 形式

允许：

- 手动喂入模型回复
- 或用 `MockModelAdapter` 驱动一轮伪闭环

---

## 12. 第一版技术边界

### 第一版必须完成

1. 模型适配层
2. 场景生成器
3. 用户画像
4. 状态机 / 策略引擎
5. 回复生成器
6. Conversation Runner
7. `/simulations/run` 从占位变为可运行
8. 与现有 evaluator 打通

### 第一版可以不做

1. 多人格细腻情绪模拟
2. 复杂开放闲聊
3. 无限轮上下文记忆
4. 海量并发仿真
5. 强化学习式用户策略优化

---

## 13. 测试策略

### 13.1 单元测试

- 用户状态机
- 策略引擎
- 回复生成器
- 模型适配层

### 13.2 集成测试

- MockModelAdapter 下的完整闭环
- 模拟结果 → evaluator 链路

### 13.3 覆盖测试

至少验证：

- 配合
- 犹豫
- 忙碌
- 拒绝
- 打断
- 追问

均能进入对应状态并完成退出。

---

## 14. 关键决策总结

1. 用户模拟器采用 **在线闭环为主，保留离线调试**。
2. 回复生成采用 **规则控流程 + LLM 生成自然表达**。
3. 第一版优先覆盖 **主流程 + 常见阻碍**。
4. 被测模型通过 **模型适配层** 接入，不绑定具体方式。
5. Conversation Runner 结束后直接复用现有 evaluator 自动评分。

