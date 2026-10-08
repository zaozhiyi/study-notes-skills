#!/usr/bin/env python3
"""Extract DOCX highlight colors, ranges and context without modifying the source."""
import argparse
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def extract(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    found = []
    for number, paragraph in enumerate(root.iter(W + 'p'), 1):
        runs = []
        for run in paragraph.iter(W + 'r'):
            text = ''.join(node.text or '' for node in run.iter(W + 't'))
            highlight = run.find(W + 'rPr/' + W + 'highlight')
            color = highlight.get(W + 'val') if highlight is not None else None
            if color == 'none':
                color = None
            runs.append((text, color))
        full = ''.join(text for text, color in runs)
        offset = 0
        active = None
        ranges = []
        for text, color in runs:
            if not text:
                continue
            if color:
                if active and active['color'] == color:
                    active['end'] += len(text)
                else:
                    if active:
                        ranges.append(active)
                    active = {'start': offset, 'end': offset + len(text), 'color': color}
            elif active:
                ranges.append(active)
                active = None
            offset += len(text)
        if active:
            ranges.append(active)
        for area in ranges:
            text = full[area['start']:area['end']]
            found.append({
                'id': f'p{number}:{area["start"]}:{area["end"]}',
                'paragraph_number': number,
                'start': area['start'], 'end': area['end'],
                'offset_unit': 'Unicode code points',
                'text': text, 'color': area['color'], 'paragraph_text': full,
                'prefix': full[max(0, area['start'] - 80):area['start']],
                'suffix': full[area['end']:area['end'] + 80],
            })
    return found


def normalize(text):
    # Comparison only; retain all original source and Page text unmodified.
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\\([\\`*_{}\[\]()#+.!|>~-])', r'\1', text)
    text = re.sub(r'^\s*(?:#{1,6}\s+|>\s*)', '', text, flags=re.M)
    text = re.sub(r'[*`~]', '', text)
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docx', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--page-json', type=Path)
    args = parser.parse_args()
    highlights = extract(args.docx)
    payload = {'version': 1, 'source_docx': str(args.docx.resolve()),
               'source_sha256': hashlib.sha256(args.docx.read_bytes()).hexdigest(),
               'count': len(highlights), 'highlights': highlights}
    if args.page_json:
        page = json.loads(args.page_json.read_text())
        while isinstance(page.get('structuredContent'), dict):
            page = page['structuredContent']
        selection = page.get('selection')
        if selection and not selection.get('whole_page_complete'):
            raise SystemExit('需要完整 Page 读取，不能用局部内容判断高亮缺失')
        content = page.get('content', {})
        if not isinstance(content.get('blocks'), list):
            raise SystemExit('Page JSON 不包含完整 blocks')
        payload['page_id'] = content.get('page_id') or page.get('metadata', {}).get('page_id')
        blocks = [(b, normalize(b.get('markdown', ''))) for b in content['blocks'] if b.get('kind') == 'markdown']
        for mark in highlights:
            text = normalize(mark['text'])
            candidates = [b for b, plain in blocks if text and text in plain]
            paragraph = normalize(mark['paragraph_text'])
            contextual = [b for b in candidates if paragraph and paragraph in normalize(b['markdown'])]
            chosen = contextual if len(contextual) == 1 else candidates
            mark['page_matches'] = [{'block_id': b['id'], 'hash': b['hash']} for b in chosen]
            mark['match_status'] = 'unique' if len(chosen) == 1 else 'ambiguous' if chosen else 'missing'
            mark['match_method'] = 'normalized text plus paragraph context; not a native highlight anchor'
        payload['match_counts'] = {state: sum(h['match_status'] == state for h in highlights) for state in ['unique', 'ambiguous', 'missing']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'count': len(highlights), 'matches': payload.get('match_counts'), 'output': str(args.out.resolve())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
