# SpecCompiler 升级设计：面向复杂外呼任务指令的结构化编译

## 1. 背景

当前评估原型已经具备完整可运行链路：

- 输入任务指令
- 编译 `EvalSpec`
- 对话抽事件
- 规则评估
- 软评估
- 聚合打分

但当前 `SpecCompiler` 仍处于极简版本，其逻辑主要依赖少量关键词：

- 含“身份” → 增加身份确认要求
- 含“时间” → 增加时间槽位
- 含“不要承诺/不要保证” → 增加禁止承诺

这种方式只能覆盖非常简单的任务，不足以支撑 Excel 中这类复杂外呼任务指令样本。

已有样例（`命题二：外呼任务对话模型指令示例.xlsx`）说明，真实任务指令通常包含以下结构：

- `Role`
- `Task`
- `Opening Line`
- `Conversation Flow / Step 1..N`
- `FAQ / Knowledge Points`
- `Constraints`

因此，系统下一阶段的核心工作，不是继续优化展示层，而是升级 `SpecCompiler`，让它能够把复杂任务指令稳定地编译为结构化评估规范。

---

## 2. 目标

本次升级目标是：

1. 支持从复杂外呼任务指令中抽取显式结构；
2. 支持把这些结构映射成更完整的 `EvalSpec`；
3. 保持可解释性，编译结果可展示、可审阅、可追溯；
4. 采用 **规则优先 + LLM 辅助** 的方式，兼顾稳定性与泛化性；
5. 为 Demo 页面提供“评测逻辑可见性”的数据基础。

---

## 3. 非目标

本次升级不追求：

- 完整自然语言理解所有任意格式 prompt；
- 直接把任务指令编译成完整状态机执行引擎；
- 一步到位实现通用任务 DSL；
- 直接改写全部对话评测逻辑。

本次重点是：**让编译结果足够结构化、足够可展示、足够支撑下一步评测升级。**

---

## 4. 核心结论

本次 `SpecCompiler` 升级采用以下总体方案：

> **轻量中间表示 + 规则优先抽结构 + LLM 只补缺 + 输出增强版 EvalSpec**

这意味着系统不再直接从原始任务指令跳到 `EvalSpec`，而是先经过一个中间结构层。

---

## 5. 总体架构

升级后的编译链路如下：

1. 输入原始任务指令文本
2. 规则解析器拆分结构化章节
3. 生成中间表示 `InstructionIR`
4. LLM 对缺失项进行补全、归一化、分类
5. 合并规则结果与 LLM 结果
6. 编译为增强版 `EvalSpec`

---

## 6. 方案对比结论

本轮设计对比过三类方案：

### 6.1 纯规则解析

优点：

- 稳定
- 可控
- 易解释

缺点：

- 对格式变化敏感
- 泛化弱

### 6.2 规则优先 + LLM 辅助

优点：

- 稳定性与泛化性平衡最好
- 可解释性仍可保留
- 适合现阶段复杂 prompt 编译

缺点：

- 比纯规则复杂
- 需要设计清晰的 merge 策略

### 6.3 主要依赖 LLM

优点：

- 泛化强

缺点：

- 稳定性弱
- 不易审计
- 对可解释性不友好

### 结论

采用 **方案 6.2：规则优先 + LLM 辅助**。

---

## 7. 中间表示：InstructionIR

### 7.1 引入原因

当前从“原始文本”直接跳到 `EvalSpec`，会导致：

- 编译过程不可见
- 页面无法展示“它是怎么理解任务的”
- 规则层与评估层耦合过紧

因此引入一个轻量中间表示 `InstructionIR`。

### 7.2 InstructionIR 建议字段

```json
{
  "instruction_id": "instr_xxx",
  "title": "飞毛腿骑手外呼任务",
  "role_definition": "你是美团外卖骑手的站长",
  "task_goal": "通知合同已生效并提醒完成配送任务",
  "opening_line": "你好，请问是${rider_name}吗？我是站长。",
  "sections": {
    "role": "...",
    "task": "...",
    "opening_line": "...",
    "conversation_flow": "...",
    "faq": "...",
    "constraints": "..."
  },
  "flow_steps": [
    {
      "step_id": "step_1",
      "title": "通知合同生效并确认是否可开始配送",
      "raw_text": "告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。"
    }
  ],
  "faq_items": [
    {
      "faq_id": "faq_1",
      "raw_text": "如需退出飞毛腿，必须在前一天 Z 点之前取消。"
    }
  ],
  "constraint_items": [
    {
      "constraint_id": "constraint_1",
      "raw_text": "每次回复控制在约30个字以内。"
    }
  ],
  "fallback_policy": [
    "超出职责范围时使用固定兜底话术"
  ]
}
```

### 7.3 设计原则

- `InstructionIR` 必须尽量接近原文结构；
- 不在这层做过多评判，只做理解与拆分；
- 后续 `EvalSpec` 从该层生成。

---

## 8. 规则解析器设计

### 8.1 解析目标

优先识别以下显式标题：

- `Role`
- `Task`
- `Opening Line`
- `Conversation Flow`
- `Call Flow`
- `Knowledge Points`
- `FAQ`
- `Constraints`

并兼容变体，如：

- `# Role`
- `## Task`
- `# Constraints:`
- `Knowledge Points (FAQ)`

### 8.2 解析方法

建议分两步：

1. **章节切分**
   - 基于 Markdown 标题
   - 基于全大写/固定标签
   - 基于常见 section 标识词

2. **章节内结构提取**
   - `Step 1..N`
   - 列表项
   - FAQ 条目
   - 约束条目

### 8.3 对 Conversation Flow 的抽取

例如：

- `Step 1: 身份确认`
- `Step 2: 确认是否知情`
- `Step 3: 传达升级内容`

应抽成 `flow_steps`，保留：

- 顺序
- 标题
- 原始内容
- 子分支说明

---

## 9. LLM 辅助层设计

### 9.1 角色

LLM 在本次升级中 **不负责主解析**，只负责：

- 补缺
- 归一化
- 分类

### 9.2 LLM 适用场景

1. 标题不标准但语义清晰
2. 约束项需要分类
3. FAQ 项需要归入知识点
4. Step 语义需要归一化成统一命名
5. 兜底话术需要识别为 fallback policy

### 9.3 LLM 不做的事

- 不覆盖规则已经明确抽出的 section
- 不重写原始指令
- 不凭空补充业务规则

### 9.4 合并原则

合并时采用：

- **规则结果优先**
- **LLM 只补缺**
- 若发生冲突，保留规则解析值并记录冲突日志

---

## 10. 增强版 EvalSpec 设计

升级后 `EvalSpec` 至少应新增以下字段：

### 10.1 推荐新增字段

- `role_definition`
- `opening_requirements`
- `flow_steps`
- `faq_items`
- `constraint_items`
- `fallback_policy`
- `step_to_evidence_mapping`

### 10.2 字段说明

#### `role_definition`
表示模型在任务中的角色设定。

#### `opening_requirements`
表示开场必须包含的要求，例如：

- 是否要确认身份
- 是否要表明来电目的

#### `flow_steps`
表示任务流程主线，是评测核心之一。

#### `faq_items`
表示可用于作答的知识点，不一定全部必答，但能支撑问答评测。

#### `constraint_items`
表示行为约束和表达限制，例如：

- 回复长度
- 不可使用某类语气
- 不可承诺优惠

#### `fallback_policy`
表示越权、打断、拒绝、忙碌等场景下的兜底策略。

#### `step_to_evidence_mapping`
表示一个流程步骤在对话中通常靠什么证据来判断命中。

---

## 11. EvalSpec 映射策略

从 `InstructionIR` 到 `EvalSpec` 的映射建议如下：

### 11.1 `Role` → `role_definition`

直接映射。

### 11.2 `Task` → `task_goal`

抽取任务核心目标。

### 11.3 `Opening Line` → `opening_requirements`

拆为可评估要求，例如：

- 是否包含身份确认
- 是否说明来电身份
- 是否说明任务目的

### 11.4 `Conversation Flow / Step 1..N` → `flow_steps`

按顺序映射为评测流程主线。

### 11.5 `FAQ / Knowledge Points` → `faq_items`

保留原文，并为后续问答评测做知识支撑。

### 11.6 `Constraints` → `constraint_items`

进一步分类：

- 语气约束
- 长度约束
- 禁止承诺
- 超纲兜底
- 忙碌/开车等终止条件

### 11.7 兜底类 Constraints → `fallback_policy`

例如：

- 超出职责范围时如何回复
- 用户在开车时如何挂断
- 用户明确拒绝时如何结束

---

## 12. 对评测链路的影响

本次升级不直接重写整个评测器，但会为后续评测升级提供基础。

### 12.1 短期影响

短期内，页面和后端至少可以展示：

- 编译出的 role
- task_goal
- flow_steps
- constraints
- faq_items

也就是让“评测逻辑可见”。

### 12.2 中期影响

后续规则评估可逐步从仅靠：

- identity_check
- delivery_time
- forbidden promise

升级为：

- 开场要求命中
- 流程步骤命中
- FAQ 应答能力
- 约束遵守情况

---

## 13. Demo 页联动价值

本次 `SpecCompiler` 升级最大的直接收益之一，是让 demo 页面可以展示“评测是怎么来的”。

建议页面后续增加以下可视区：

1. **任务编译结果**
   - Role
   - Task Goal
   - Opening Requirements

2. **流程步骤**
   - Step 1..N

3. **约束项**
   - 禁止项
   - 风格约束
   - 长度约束
   - 兜底策略

4. **FAQ / Knowledge Points**
   - 知识点清单

这样页面不再只是“打完分”，而是能展示：

> “系统是如何理解这个任务，并据此设计评测标准的”

---

## 14. 第一版升级边界

### 本次必须完成

1. 引入 `InstructionIR`
2. 支持规则切分主要 section
3. 支持抽取 `flow_steps`
4. 支持抽取 `constraint_items`
5. 支持抽取 `faq_items`
6. 支持映射到增强版 `EvalSpec`
7. 为页面提供可展示的编译结构

### 本次可以不做

1. 完整分支状态机
2. 复杂话术语义判定
3. FAQ 与真实问答表现的自动对齐评分
4. 复杂约束的自动执行器

---

## 15. 测试策略

### 15.1 单元测试

针对以下能力分别写测试：

- section 切分
- step 抽取
- constraint 抽取
- faq 抽取
- IR 到 EvalSpec 映射

### 15.2 样例回归测试

直接使用 Excel 中的两条任务指令做回归样本，验证：

- role 是否正确抽取
- opening line 是否可见
- steps 是否按顺序抽取
- constraints 是否被分类

### 15.3 冲突测试

验证当规则与 LLM 补全出现冲突时：

- 规则结果优先
- 冲突被显式记录

---

## 16. 关键决策总结

1. 本次升级目标为 **中升级**，不是通用 DSL 编译器。
2. 编译架构采用 **规则优先 + LLM 辅助**。
3. 引入轻量中间表示 `InstructionIR`。
4. `EvalSpec` 将扩展为更适合复杂任务指令的结构。
5. 本次升级重点之一是让评测逻辑 **可展示、可理解、可追溯**。

