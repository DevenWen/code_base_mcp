---
description: "Brainstorming for user story."
disable-model-invocation: true
---

# 输入
1. 执行这个命令时，用户会输入一份用户故事。位置是 ./prd/{version}/userstory.md 。

# 目标
1. 命令的目标是，通过一系列的工作步骤，将用户故事转换为一份详细的 PRD。

# 准则
1. 过程中，所有的变更都应该在 ./prd/{version} 的目录中进行。

# 步骤
1. 使用 brainstorming SKILL 与用户进行对话，了解用户故事的背景、需求、预期结果等信息。**确保清晰用户的需求，同时也确保用户清晰自己的需求**。输出结果：userstory.md（在源文件上变更）
2. 使用 concept-crystallizer SKILL 分析 userstory.md , 并输出结果
3. 使用 schema-architect SKILL 分析 concept-crystallizer 的输出， 并输出结果
4. 使用 ui-simulator SKILL 分析 schema-architect 的输出， 完成后需要启用一个 python http 服务，让用户可以预览原型。

# 输出
1. 一份完成的 PRD 目录，里面包括：
    - userstory.md
    - w1_concept_crystallizer_{yyyymmddhhmmss}.md
    - w2_schema_architect_{yyyymmddhhmmss}.md
    - w3_ui_simulator_{yyyymmddhhmmss}.md
    - w4_prototype.html


