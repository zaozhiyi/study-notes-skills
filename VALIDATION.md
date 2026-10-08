# v1.0.0 验证记录

日期：2026-10-08。

## 来源与保留

- 本机原有 Claude、Codex skill 未修改，原说明与来源 SHA-256 已留档。
- 原有脚本逐字节保留。Cursor 版两份 Word 脚本与 Codex 原件逐字节一致。
- Cursor 主体由本地 Cursor Agent CLI 使用用户指定的 `grok-4.7-high` 生成；初始化日志确认显示 `Grok 4.7 256K High`。来源记录在 `sources/cursor-generation.json`，不含账号与会话内容。
- Codex 整理共同规则、仓库包装，检查生成文件，提出少量能力边界修正，由同一 Cursor 会话收尾。

## 已完成的本地检查

- 三份 skill 通过 skill-creator 的 `quick_validate.py`；名称、YAML frontmatter 和正文基本格式通过。
- `scripts/sync_principles.py --check` 确认三份共同规则副本与维护源完全一致。
- 全部 Python 源文件通过语法检查；skill 引用的本地支持文件存在。
- 使用临时生成的 Word 样例验证：添加黄色高亮、取消高亮、正文文字不变、其他 ZIP 成员内容不变、来源文件不变、重复选区拒绝写入、过期来源哈希拒绝写入。全部通过，未使用真实笔记。
- 检查仓库内容未包含笔记正文、备份目录、会话日志、Python 缓存或常见凭据格式。

Cursor CLI 的复制命令和 Python shell 检查曾被其执行权限机制拒绝，未返回具体原因。Cursor 改用文件编辑生成，脚本运行验证由 Codex 在隔离的临时样例上完成；没有把被拒绝的操作算成成功，也没有改变 Cursor 的权限设置。

## 尚未验证与使用范围

- 未在三平台真实文档上重新验证 UI、原生选区评论、文档 MCP 或 Word 预览里的黄色显示。
- 共同规则副本一致，不证明三种 agent 每次执行行为都一致。升级后按 README 的场景清单逐版检查。
- Claude 旧同步脚本未运行，以免扫描私人会话。它的单份同步范围与当前连接器兼容性仍须核实；现行说明要求先限定目标，不能直接当作已验证的单份同步命令。
- Codex 版内的旧迁移记录是历史说明，不是本次对当前账号权限和 Pages 能力的重新确认。
- Cursor Markdown 的本地评论记录不是 Claude Docs 或 Codex Page 的原生线程；原生文档工具只在真实可用时使用。
