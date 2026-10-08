#!/usr/bin/env python3
"""Set/clear a uniquely identified DOCX text highlight, preserving other parts."""
import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'


def paragraph_runs(paragraph):
    return [r for r in paragraph.iter(W + 'r')
            if next(r.iterancestors(W + 'p'), None) is paragraph]


def run_text(run):
    return ''.join(t.text or '' for t in run.iter(W + 't'))


def shade(run, action):
    props = run.find(W + 'rPr')
    if props is None:
        props = etree.Element(W + 'rPr')
        run.insert(0, props)
    for item in list(props.findall(W + 'highlight')):
        props.remove(item)
    if action == 'add':
        etree.SubElement(props, W + 'highlight').set(W + 'val', 'yellow')
    else:
        # Override inherited style highlights; retain other background shading.
        etree.SubElement(props, W + 'highlight').set(W + 'val', 'none')


def apply(source, output, quote, action, paragraph_number=None, source_sha256=None):
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if source_sha256 and digest != source_sha256:
        raise ValueError('来源文件已变化，请重新读取并定位')
    if source.resolve() == output.resolve():
        raise ValueError('必须先写入独立副本，不能直接覆盖来源文件')
    if output.exists():
        raise ValueError('输出文件已存在，请使用新的文件名')
    if not quote:
        raise ValueError('高亮原文不能为空')
    with ZipFile(source) as archive:
        payload = archive.read('word/document.xml')
        tree = etree.fromstring(payload, etree.XMLParser(resolve_entities=False))
        paragraphs = list(tree.iter(W + 'p'))
        matches = []
        for number, para in enumerate(paragraphs, 1):
            if paragraph_number is not None and number != paragraph_number:
                continue
            text = ''.join(run_text(r) for r in paragraph_runs(para))
            start = 0
            while True:
                index = text.find(quote, start)
                if index < 0:
                    break
                matches.append((number, para, index, index + len(quote)))
                start = index + 1
        if len(matches) != 1:
            raise ValueError(f'匹配 {len(matches)} 处；需提供精确原文和段落位置，不能猜')
        number, para, start, end = matches[0]
        before_text = ''.join(para.itertext())
        offset = 0
        for run in list(paragraph_runs(para)):
            text = run_text(run)
            length = len(text)
            lo, hi = max(0, start - offset), min(length, end - offset)
            offset += length
            if lo >= hi:
                continue
            if lo == 0 and hi == length:
                shade(run, action)
                continue
            if any(child.tag not in (W + 'rPr', W + 't') for child in run):
                raise ValueError('选区边界包含图片、域或换行，需更精确的选区')
            parent = run.getparent()
            position = parent.index(run)
            for left, right, selected in [(0, lo, False), (lo, hi, True), (hi, length, False)]:
                if left == right:
                    continue
                piece = copy.deepcopy(run)
                for child in list(piece):
                    if child.tag != W + 'rPr':
                        piece.remove(child)
                t = etree.SubElement(piece, W + 't')
                t.text = text[left:right]
                t.set(XML_SPACE, 'preserve')
                if selected:
                    shade(piece, action)
                parent.insert(position, piece)
                position += 1
            parent.remove(run)
        if ''.join(para.itertext()) != before_text:
            raise ValueError('正文发生变化，取消写入')
        xml = etree.tostring(tree, encoding='UTF-8', xml_declaration=True,
                             standalone=tree.getroottree().docinfo.standalone)
        output.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=output.parent, suffix='.docx')
        os.close(handle)
        try:
            with ZipFile(temp, 'w') as target:
                for info in archive.infolist():
                    target.writestr(info, xml if info.filename == 'word/document.xml'
                                    else archive.read(info.filename))
            with ZipFile(temp) as check:
                if check.testzip() is not None:
                    raise ValueError('文件包校验失败')
            os.replace(temp, output)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return {'action': action, 'paragraph_number': number, 'text': quote,
            'source_sha256': digest, 'output': str(output.resolve())}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--docx', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    cli.add_argument('--text-file', type=Path, required=True)
    cli.add_argument('--action', choices=['add', 'remove'], required=True)
    cli.add_argument('--paragraph', type=int)
    cli.add_argument('--source-sha256')
    args = cli.parse_args()
    result = apply(args.docx, args.out, args.text_file.read_text(), args.action,
                   args.paragraph, args.source_sha256)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
