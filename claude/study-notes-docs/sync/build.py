#!/usr/bin/env python3
"""把 Claude Docs 里的学习笔记落到本地。

Claude 每次调用 Docs 的 export / query / read 工具，结果都会记在 ~/.claude/projects/*/*.jsonl
（结果太大时另存在同目录的 tool-results/ 里）。本脚本从这些记录里找出每份文档最新的一次导出和评论，
生成：<名字>.md（正文）、<名字>.docx（正文 + 高亮 + 图）、<名字>.评论.md（全部评论串 + 我的高亮）。
原始数据留在输出目录的 .sync/raw/，将来可用它把文档重建回 Docs。只用 Python 标准库。
文档清单：~/.claude/study-notes/registry.json（{project id: {name, title, tab, url, dir}}）。
"""
import base64, glob, io, json, os, re, sys, zipfile
from datetime import datetime, timezone, timedelta

# 文档清单是全局的：每份文档记着自己的输出目录 dir（一般是 <项目>/学习笔记）。
# 原始数据和历史版本放在各自输出目录下的 .sync/ 里。
REGISTRY = os.path.expanduser("~/.claude/study-notes/registry.json")
DOCS = json.load(open(REGISTRY, encoding="utf-8"))
TZ = timezone(timedelta(hours=8))


def result_text(part):
    c = part.get("content")
    if isinstance(c, list):
        c = "".join(x.get("text", "") for x in c if isinstance(x, dict))
    c = c or ""
    m = re.search(r"Output has been saved to (\S+\.txt)", c)
    if m and os.path.exists(m.group(1)):
        c = open(m.group(1), encoding="utf-8").read()
        try:  # 新格式：另存的是 [{type, text}, …] 数组
            arr = json.loads(c)
            if isinstance(arr, list):
                c = "\n".join(x.get("text", "") for x in arr if isinstance(x, dict))
        except Exception:
            pass
    return c


def first_json(s):
    """结果前面可能先有一段提示文字，找到第一个 {"verdict" 再解析。"""
    i = s.find('{"verdict"')
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(s[i:])[0]
    except Exception:
        return None


def scan():
    """返回 {(kind, project, key): (timestamp, obj)}，只留最新一次。"""
    best = {}
    files = glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
    for path in files:
        uses = {}
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            continue
        for ln in fh:
            if "tool_" not in ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            ts = o.get("timestamp", "")
            content = (o.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if part.get("type") == "tool_use":
                    name = part.get("name", "")
                    if name.split("__")[-1] in ("export", "query", "read") and name.startswith("mcp__"):
                        uses[part["id"]] = (name.split("__")[-1], part.get("input") or {})
                elif part.get("type") == "tool_result" and part.get("tool_use_id") in uses:
                    verb, inp = uses[part["tool_use_id"]]
                    proj = (inp.get("container") or {}).get("id")
                    if proj not in DOCS:
                        continue
                    obj = first_json(result_text(part))
                    if not isinstance(obj, dict) or obj.get("verdict") != "allow":
                        continue
                    if verb == "export":
                        key = ("export", proj, inp.get("format"))
                    elif verb == "query":
                        under = (inp.get("payload") or {}).get("under") or {}
                        if under.get("object") != "file" or "rows" not in obj:
                            continue  # 只要整篇文档（tab）的评论列表
                        if "afterSeq" in (inp.get("payload") or {}):
                            # 增量查询：只含 afterSeq 之后的新记录，全部收集起来，和已存的合并
                            best.setdefault(("inc", proj, ""), []).extend(obj["rows"])
                            continue
                        key = ("comments", proj, "")
                    else:
                        v = obj.get("value") or {}
                        if "code" not in v:
                            continue
                        key = ("widget", proj, (inp.get("ref") or {}).get("id"))
                    if key not in best or ts >= best[key][0]:
                        best[key] = (ts, obj)
    return best


def link_toc(text):
    """Docs 导出的目录是纯文字，这里给目录每一项加上跳转链接。"""
    lines = text.split("\n")
    heads = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{2,4}) (.+)$", ln)
        if m:
            heads.setdefault(m.group(2).strip(), i)
    try:
        start = next(i for i, ln in enumerate(lines) if re.match(r"^#{2,4} 目录$", ln))
    except StopIteration:
        return text
    anchors = {}
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if re.match(r"^#{1,4} ", ln):
            break
        m = re.match(r"^- (.+)$", ln)
        if m and m.group(1).strip() in heads:
            t = m.group(1).strip()
            aid = f"s{len(anchors) + 1}"
            anchors[heads[t]] = aid
            lines[i] = f"- [{t}](#{aid})"
    for idx, aid in anchors.items():
        lines[idx] = f'<a id="{aid}"></a>\n\n' + lines[idx]
    return "\n".join(lines)


def fmt_time(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def docx_highlights(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    x = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S):
        cur = ""
        for r in re.findall(r"<w:r(?: [^>]*)?>(.*?)</w:r>", p, flags=re.S):
            t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", r))
            if "w:highlight" in r:
                cur += t
            elif cur:
                out.append(cur); cur = ""
        if cur:
            out.append(cur)
    unesc = lambda s: s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
    return [unesc(h) for h in out]


def threads(rows):
    alive = {}
    deleted = {r["id"] for r in rows if r.get("verb") == "delete"}
    for r in rows:
        if r.get("verb") == "create" and r["id"] not in deleted:
            alive[r["id"]] = r
    for r in rows:  # 改过的评论：用最新内容
        v = (r.get("payload") or {}).get("value")
        if r.get("verb") == "update" and r["id"] in alive and isinstance(v, dict):
            alive[r["id"]] = dict(alive[r["id"]], payload={"value": v})
    roots, replies, resolved = [], {}, set()
    for r in alive.values():
        v = r["payload"]["value"]; par = v.get("parent") or {}
        if par.get("object") == "utterance":
            if v.get("kind") == "resolve":
                resolved.add(par["id"])
            else:
                replies.setdefault(par["id"], []).append(r)
        else:
            roots.append(r)
    roots.sort(key=lambda r: r["seq"])
    out = []
    for r in roots:
        par = r["payload"]["value"]["parent"]
        msgs = [r] + sorted(replies.get(r["id"], []), key=lambda x: x["seq"])
        msgs = [(who(m), fmt_time(m["at"]), body(m)) for m in msgs if body(m)]
        out.append({"quote": (par.get("label") or "").strip(), "resolved": r["id"] in resolved, "msgs": msgs})
    return out


who = lambda r: "Claude" if (r.get("actor") or {}).get("via") == "mcp" else "我"
body = lambda r: r["payload"]["value"].get("body", "").replace("@Claude\u2060", "@Claude").strip()


def comments_md(title, url, rows, highlights, synced):
    ths = threads(rows)
    L = [f"# {title} · 评论与高亮", "",
         f"> 文档：{url}", f"> 本地同步：{synced}。正文见同目录的 `.md` / `.docx`。", "",
         f"共 {len(ths)} 个评论串，{len(highlights)} 处我的高亮。", "", "## 评论", ""]
    for i, t in enumerate(ths, 1):
        quote = t["quote"]
        status = "（已解决）" if t["resolved"] else ""
        L.append(f"### {i}. {quote[:40] + ('…' if len(quote) > 40 else '') if quote else '（整篇）'}{status}")
        L.append("")
        if quote:
            L += ["> " + q for q in quote.splitlines()] + [""]
        for w, tm, txt in t["msgs"]:
            L.append(f"**{w}**（{tm}）：")
            L.append("")
            L += [ln if ln.strip() else "" for ln in txt.splitlines()]
            L.append("")
        L.append("---"); L.append("")
    L += ["## 我的高亮", ""]
    L += [f"- {h}" for h in highlights] or ["（暂无）"]
    L.append("")
    return "\n".join(L)


def xesc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def docx_with_comments(blob, ths):
    """把评论串写成 Word 批注，挂在被评论的那一段上。Word / Pages / WPS 打开都能看到。"""
    if not ths:
        return blob
    zin = zipfile.ZipFile(io.BytesIO(blob))
    files = {n: zin.read(n) for n in zin.namelist()}
    doc = files["word/document.xml"].decode("utf-8")
    paras = [(m.start(), m.end()) for m in re.finditer(r"<w:p[ >].*?</w:p>", doc, flags=re.S)]
    ptext = [re.sub(r"<[^>]+>", "", "".join(re.findall(r"<w:t[^>]*>.*?</w:t>", doc[a:b], flags=re.S))) for a, b in paras]
    ptext = [t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") for t in ptext]
    flat = lambda t: re.sub(r"\s+", "", t)
    marks = {}  # para index -> [comment ids]
    comments = []
    for cid, t in enumerate(ths):
        key = flat(t["quote"].rstrip("…"))[:30]
        idx = 0
        if key:
            idx = next((i for i, pt in enumerate(ptext) if key in flat(pt)), None)
            if idx is None:
                idx = next((i for i, pt in enumerate(ptext) if key[:10] and key[:10] in flat(pt)), 0)
        marks.setdefault(idx, []).append(cid)
        ps = []
        if t["resolved"]:
            ps.append("（已解决）")
        for w, tm, txt in t["msgs"]:
            ps.append(f"【{w} · {tm}】")
            ps += [ln for ln in txt.splitlines() if ln.strip()]
        body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{xesc(p)}</w:t></w:r></w:p>' for p in ps)
        comments.append(f'<w:comment w:id="{cid}" w:author="{xesc(t["msgs"][0][0] if t["msgs"] else "")}" w:initials="C">{body}</w:comment>')
    for idx in sorted(marks, reverse=True):
        a, b = paras[idx]
        p = doc[a:b]
        m = re.match(r"(<w:p[ >].*?(?:</w:pPr>|(?=<w:r[ >])))", p, flags=re.S)
        head = m.group(1) if m and "<w:pPr" in m.group(1) else re.match(r"<w:p[^>]*>", p).group(0)
        rest = p[len(head):-len("</w:p>")]
        starts = "".join(f'<w:commentRangeStart w:id="{c}"/>' for c in marks[idx])
        ends = "".join(f'<w:commentRangeEnd w:id="{c}"/><w:r><w:commentReference w:id="{c}"/></w:r>' for c in marks[idx])
        doc = doc[:a] + head + starts + rest + ends + "</w:p>" + doc[b:]
    files["word/document.xml"] = doc.encode("utf-8")
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    files["word/comments.xml"] = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments {ns}>' + "".join(comments) + "</w:comments>").encode("utf-8")
    ct = files["[Content_Types].xml"].decode("utf-8")
    if "/word/comments.xml" not in ct:
        ct = ct.replace("</Types>", '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/></Types>')
    files["[Content_Types].xml"] = ct.encode("utf-8")
    rel = files["word/_rels/document.xml.rels"].decode("utf-8")
    if "comments.xml" not in rel:
        rel = rel.replace("</Relationships>", '<Relationship Id="rIdComments" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/></Relationships>')
    files["word/_rels/document.xml.rels"] = rel.encode("utf-8")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in zin.namelist() + (["word/comments.xml"] if "word/comments.xml" not in zin.namelist() else []):
            z.writestr(zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0)), files[n], compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


def save(path, data):
    """写文件；内容有变化时，把旧版本留一份到 .sync/history/，防止同步出错把好内容盖掉。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if os.path.exists(path):
        old = open(path, "rb").read()
        strip = lambda b: re.sub(rb"^<!-- .*? -->\n", b"", b, count=1)
        if strip(old) == strip(data):
            return False
        hist = os.path.join(os.path.dirname(path), ".sync", "history"); os.makedirs(hist, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(path))
        stamp = datetime.fromtimestamp(os.path.getmtime(path), TZ).strftime("%Y%m%d-%H%M%S")
        open(os.path.join(hist, f"{stem}.{stamp}{ext}"), "wb").write(old)
    open(path, "wb").write(data)
    return True


def main():
    best = scan()
    synced = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    report = []
    for proj, meta in DOCS.items():
        name = meta["name"]
        OUT = meta["dir"]
        raw = os.path.join(OUT, ".sync", "raw", name); os.makedirs(raw, exist_ok=True)
        highlights = []
        hit = best.get(("comments", proj, ""))
        # 评论 = 已存的 comments.json ∪ 最新完整查询 ∪ 所有增量查询，按 seq 去重
        merged = {}
        old_path = os.path.join(raw, "comments.json")
        if os.path.exists(old_path):
            try:
                for r in json.load(open(old_path, encoding="utf-8")):
                    merged[r["seq"]] = r
            except Exception:
                pass
        for r in (hit[1]["rows"] if hit else []) + best.get(("inc", proj, ""), []):
            merged[r["seq"]] = r
        rows = [merged[k] for k in sorted(merged)]
        for fmt, ext in (("markdown", "md"), ("docx", "docx")):
            hit = best.get(("export", proj, fmt))
            if not hit:
                continue
            data = hit[1]["data"]; blob = base64.b64decode(data["bytes_b64"])
            if fmt == "markdown":
                text = link_toc(blob.decode("utf-8"))
                text = f"<!-- 从 Claude Docs 导出：{meta['url']} · 文档版本 rev {hit[1].get('rev')} · 导出于 {fmt_time(hit[0])} -->\n\n" + text
                blob = text.encode("utf-8")
            else:
                highlights = docx_highlights(blob)
                blob = docx_with_comments(blob, threads(rows))
            changed = save(os.path.join(OUT, f"{name}.{ext}"), blob)
            report.append(f"{name}.{ext} ← rev {hit[1].get('rev')} @ {fmt_time(hit[0])}{'' if changed else '（无变化）'}")
        if rows:
            json.dump(rows, open(os.path.join(raw, "comments.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for (k, p, wid), val in best.items():
            if k == "inc":
                continue
            ts, obj = val
            if k == "widget" and p == proj:
                open(os.path.join(raw, f"widget-{wid}.jsx"), "w", encoding="utf-8").write(obj["value"]["code"])
        cm = comments_md(meta["title"], meta["url"], rows, highlights, synced)
        old = os.path.join(OUT, f"{name}.评论.md")
        if not os.path.exists(old) or re.sub(r"> 本地同步：.*", "", open(old, encoding="utf-8").read()) != re.sub(r"> 本地同步：.*", "", cm):
            save(old, cm)
        report.append(f"{name}.评论.md ← {len(rows)} 条记录, {len(highlights)} 处高亮")
    print("\n".join(report))


if __name__ == "__main__":
    main()
