# Word 高亮

仅用户明确选择 Word 或要求改已有 .docx 高亮时读取。下列命令中的 scripts 路径相对于 skill 根目录。


这是在另一份 `.docx` 上添加或取消 `w:highlight`，不是给当前 Markdown 增加涂色按钮，也不会和 Docs 或 Page 自动同步。第一次使用时说明这一点。

脚本与本 skill 放在一起：

- [scripts/set_docx_highlight.py](../scripts/set_docx_highlight.py)：写入或清除文字高亮。依赖 `lxml`。运行前确认当前解释器可以导入它。缺失时先查现有可用运行环境；在已授权的文件处理任务范围内，可以准备隔离的本地依赖环境，不改全局配置。不要改用其他库临时重写脚本。
- [scripts/extract_highlights.py](../scripts/extract_highlights.py)：只读提取高亮范围。只用 Python 标准库。

```bash
python3 scripts/set_docx_highlight.py \
  --docx 来源.docx \
  --out 新版本.docx \
  --text-file 选区原文.txt \
  --action add \
  --source-sha256 当前来源哈希
```

`--action` 用 `add` 或 `remove`。同一原文出现在多个段落时，加上 `--paragraph`，段落号与脚本报出的编号一致。选区原文文件保持原样，不要自行 strip 或改写。

脚本只在匹配恰好一处时写入，并且不覆盖来源、不覆盖已存在的输出。正文若发生变化会取消写入。选区切在图片、域或换行上时会拒绝，不要绕开。跨段选区按段拆开，每段单独调用。

首次写入独立的 `<短名> Cursor高亮.docx`。以后替换 Cursor 工作副本前，若内容有变化，先把上一版放进该笔记目录的 `.sync/history/cursor/<时间戳>/`。原始 Claude 或 Codex 的 `.docx` 不覆盖。工作副本不存在时，说明原始 Word 只是旧快照，不能称它为当前笔记的实时导出。

写入后用提取脚本读回，核对选区原文、颜色、数量和段落文字是否未变。这里只验证文件包里的高亮标记。不要声称 Cursor 界面已经显示黄色，也不要调用并不存在的 documents 插件做渲染验证。

`--page-json` 不是 Cursor 的功能。只有用户另外给出了完整 Page JSON 文件时才传入；匹配结果不是原生高亮锚点。局部 Page 读取会被脚本拒绝。

