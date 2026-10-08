#!/usr/bin/env python3
"""Save complete native Page and comment snapshots without touching Claude originals."""
import argparse
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def unwrap(value):
    while isinstance(value, dict):
        if 'blocks' in value.get('content', {}) if isinstance(value.get('content'), dict) else False:
            return value
        if 'threads' in value:
            return value
        if isinstance(value.get('structuredContent'), dict):
            value = value['structuredContent']
            continue
        text = next((b.get('text') for b in value.get('content', []) if isinstance(b, dict) and b.get('type') == 'text'), None) if isinstance(value.get('content'), list) else None
        if text:
            value = json.loads(text)
            continue
        break
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page-json', required=True, type=Path)
    ap.add_argument('--comments-json', required=True, type=Path)
    ap.add_argument('--name', required=True)
    ap.add_argument('--directory', required=True, type=Path)
    a = ap.parse_args()
    if a.name in ('.', '..') or '/' in a.name or '\\' in a.name:
        raise SystemExit('name 必须是文件名，不能是路径')
    page = unwrap(json.loads(a.page_json.read_text()))
    comments = unwrap(json.loads(a.comments_json.read_text()))
    if page.get('error') or comments.get('error') or comments.get('truncated', False):
        raise SystemExit('数据报错或评论被截断，保留旧的完整备份')
    if page.get('selection') and not page['selection'].get('whole_page_complete'):
        raise SystemExit('正文是局部读取，不能作为完整备份')
    content = page.get('content', {})
    blocks = content.get('blocks')
    if not isinstance(blocks, list) or not isinstance(comments.get('threads'), list):
        raise SystemExit('需要完整 Page blocks 和评论 threads')
    pid = page.get('metadata', {}).get('page_id') or content.get('page_id')
    if not pid or comments.get('page_id') != pid:
        raise SystemExit('正文和评论 Page ID 不一致')
    title = content.get('title', a.name)
    url = page.get('metadata', {}).get('url', '')
    body = '# ' + title + '\n\n' + '\n\n'.join(b['markdown'] for b in blocks if b.get('kind') == 'markdown') + '\n'
    discussion = [f'# {title} 评论', '', f'文档：{url}', '']
    for i, thread in enumerate(comments['threads'], 1):
        discussion += [f'## {i} {thread.get("state", "open")}', '', f'原文锚点：{json.dumps(thread.get("target", {}), ensure_ascii=False)}', '']
        for msg in thread.get('messages', []):
            author = msg.get('author', {}).get('displayName', '')
            if msg.get('authorType') == 'agent':
                author = msg.get('agent_kind', author)
            discussion += [f'**{author}** {msg.get("createdAt", "")}', '', '[已删除]' if msg.get('deletedAt') else msg.get('body', ''), '']
    if not comments['threads']:
        discussion += ['当前 Page 没有评论。', '']
    underline_count = sum(b.get('markdown', '').count('<u>') for b in blocks)
    if underline_count:
        discussion += [f'当前正文保存 {underline_count} 处下划线；具体范围见正文备份和 Page JSON。', '']
    else:
        discussion += ['文字格式以正文备份和 Page JSON 为准；旧 Claude 标记记录另保留在原始备份中。', '']
    out = a.directory.expanduser().resolve()
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S-%f')
    files = {out / f'{a.name}.md': body, out / f'{a.name}.评论.md': '\n'.join(discussion)}
    raw = out / '.sync' / 'codex' / a.name
    files[raw / 'page.json'] = json.dumps(page, ensure_ascii=False, indent=2) + '\n'
    files[raw / 'comments.json'] = json.dumps(comments, ensure_ascii=False, indent=2) + '\n'
    changed = []
    for path, text in files.items():
        if path.exists() and path.read_text() == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            old = out / '.sync' / 'history' / 'codex' / stamp / path.relative_to(out)
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_bytes(path.read_bytes())
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(text)
        temp.replace(path)
        changed.append(str(path))
    print(json.dumps({'page_id': pid, 'changed': changed, 'word': '未生成，本脚本只同步正文和评论'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
