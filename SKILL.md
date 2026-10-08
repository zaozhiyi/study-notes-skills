---
name: study-notes-skills
description: 学习笔记仓库统一入口。用户给本仓库链接、要求按技能整理对话或继续笔记时，先识别宿主应用，再读取对应的 Claude、Codex 或 Cursor 适配版。
---

# 学习笔记统一入口

本仓库包含三个适配版。先读 [共同规则](shared/principles.md)，再根据当前宿主和真实工具选择下面一版；不要把模型名称当成应用名称，也不要把库中第一个找到的 SKILL.md 当默认。

| 当前宿主 | 操作入口 |
| --- | --- |
| Claude（原生 Docs 能力须实际可用） | [Claude 版](claude/study-notes-docs/SKILL.md) |
| Codex，包括使用其他厂商模型时 | [Codex 版](codex/study-notes-pages/SKILL.md) |
| Cursor，包括使用 Claude、Grok 或 OpenAI 模型时 | [Cursor 版](cursor/study-notes-cursor/SKILL.md) |

优先依据明确的宿主上下文和平台工具；通过该环境支持的工具发现机制查文档能力。无法识别宿主时只澄清应用，不要先选 Cursor 或先降级成 Markdown。用户明确指定平台时遵循指定，但核实其工具在当前环境能否实际调用。

正确交付包括：围绕理解缺口讲清原理、用户能打开主阅读文档、图表能呈现、继续提问的方式真实可用。只有文件写入不能称为完整学习体验已完成。对已有文档的读取、评论和修改边界见对应适配版与共同规则。

只读取需要的适配版；不运行本库中的备份或 Word 脚本来安装技能，也不把学习笔记提交到这个仓库。
