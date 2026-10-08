#!/usr/bin/env python3
"""PaperShelf: dependency-free, local-only BibTeX / PDF / Markdown library.
Run: python3 app.py (then open http://127.0.0.1:8765)
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
PDFS = DATA / 'pdfs'
NOTES = DATA / 'notes'
DATABASE = DATA / 'library.json'
LOCK = threading.RLock()
MAX_BIB = 8 * 1024 * 1024
MAX_PDF = 80 * 1024 * 1024
MAX_NOTE = 2 * 1024 * 1024
MAX_JSON = 16 * 1024
DEFAULT_LIBRARY_ID = 'default'
ID_PATTERN = re.compile(r'^[0-9a-f]{16}$')
ENTRY_START = re.compile(r'@([A-Za-z]+)\s*([\{\(])')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_library():
    return {'id': DEFAULT_LIBRARY_ID, 'name': '默认文献库', 'created_at': now_iso()}


def init_storage():
    for path in (DATA, PDFS, NOTES):
        path.mkdir(parents=True, exist_ok=True)
    if not DATABASE.exists():
        save_library({'version': 2, 'libraries': [default_library()], 'papers': []})
        return

    # Upgrade v1 metadata in-place, keeping all paper IDs and existing note/PDF
    # filenames unchanged. Make a one-time exact backup before modifying v1.
    with LOCK:
        library = read_library()
        if 'libraries' not in library:
            backup = DATA / 'library.v1-backup.json'
            if not backup.exists():
                shutil.copy2(DATABASE, backup)
            library['version'] = 2
            library['libraries'] = [default_library()]
            for paper in library['papers']:
                paper.setdefault('library_id', DEFAULT_LIBRARY_ID)
            save_library(library)


def atomic_write(path, content):
    temp = path.with_name(path.name + '.tmp')
    with open(temp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, path)


def read_library():
    with open(DATABASE, encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get('papers'), list):
        raise ValueError('文献库数据文件格式无效')
    if 'libraries' in data:
        libraries = data['libraries']
        if not isinstance(libraries, list) or any(
            not isinstance(lib, dict) or not isinstance(lib.get('id'), str)
            or not isinstance(lib.get('name'), str) for lib in libraries
        ):
            raise ValueError('文献库列表格式无效')
    return data


def save_library(data):
    atomic_write(DATABASE, json.dumps(data, ensure_ascii=False, indent=2))


def validate_library_name(name):
    if not isinstance(name, str):
        raise ValueError('文献库名称必须是文本')
    name = name.strip()
    if not 1 <= len(name) <= 60 or any(ord(char) < 32 for char in name):
        raise ValueError('文献库名称应为 1–60 个字符，不能包含控制字符')
    return name


def find_library(data, library_id):
    return next((lib for lib in data['libraries'] if lib['id'] == library_id), None)


def create_library_in_memory(data, name):
    name = validate_library_name(name)
    if any(lib['name'].casefold() == name.casefold() for lib in data['libraries']):
        raise ValueError('已有同名文献库，请直接选择已有库')
    existing_ids = {lib['id'] for lib in data['libraries']}
    identifier = secrets.token_hex(8)
    while identifier in existing_ids:
        identifier = secrets.token_hex(8)
    lib = {'id': identifier, 'name': name, 'created_at': now_iso()}
    data['libraries'].append(lib)
    return lib

def split_top_level(text):
    """Split BibTeX entry fields on commas outside braces/quoted strings."""
    chunks = []
    start = depth = 0
    in_quote = escaped = False
    for idx, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char == '"' and depth == 0:
            in_quote = not in_quote
        elif not in_quote:
            if char == '{':
                depth += 1
            elif char == '}':
                depth = max(depth - 1, 0)
            elif char == ',' and depth == 0:
                chunks.append(text[start:idx].strip())
                start = idx + 1
    chunks.append(text[start:].strip())
    return [chunk for chunk in chunks if chunk]


def clean_value(value):
    value = value.strip()
    # Standard BibTeX values are brace-enclosed or quoted. Keep nested groups.
    if len(value) >= 2 and ((value[0] == '{' and value[-1] == '}') or
                            (value[0] == '"' and value[-1] == '"')):
        value = value[1:-1]
    value = re.sub(r'[\r\n\t]+', ' ', value)
    value = re.sub(r'\s{2,}', ' ', value)
    return value.strip()


def parse_bib(text):
    papers = []
    index = 0
    while True:
        match = ENTRY_START.search(text, index)
        if match is None:
            break
        kind = match.group(1).lower()
        opener = match.group(2)
        closer = '}' if opener == '{' else ')'
        begin = match.end()
        level = 1
        escaped = in_quote = False
        position = begin
        while position < len(text):
            char = text[position]
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"' and level == 1:
                in_quote = not in_quote
            elif not in_quote:
                if char == opener:
                    level += 1
                elif char == closer:
                    level -= 1
                    if level == 0:
                        break
            position += 1
        if level != 0:
            index = match.end()
            continue
        index = position + 1
        if kind in {'comment', 'string', 'preamble'}:
            continue
        chunks = split_top_level(text[begin:position])
        if not chunks:
            continue
        citekey = chunks[0].strip()
        fields = {}
        for chunk in chunks[1:]:
            if '=' in chunk:
                name, value = chunk.split('=', 1)
                name = name.strip().lower()
                if re.fullmatch(r'[A-Za-z][\w-]*', name):
                    fields[name] = clean_value(value)
        title = fields.get('title', '')
        if not title:
            continue
        year_match = re.search(r'\b(?:19|20)\d{2}\b', fields.get('year', '') or fields.get('date', ''))
        year = year_match.group(0) if year_match else ''
        doi = normalize_doi(fields.get('doi', ''))
        papers.append({
            'key': citekey[:250],
            'title': title,
            'author': fields.get('author', ''),
            'year': year,
            'journal': fields.get('journal') or fields.get('journaltitle') or fields.get('booktitle') or '',
            'doi': doi,
            'keywords': fields.get('keywords') or fields.get('keyword') or '',
            'abstract': fields.get('abstract', ''),
        })
    return papers


def normalize_doi(doi):
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:)', '', doi.strip(), flags=re.I)
    return doi.strip().rstrip('.,;').lower()


def title_key(paper):
    title = re.sub(r'[^\w]+', '', paper.get('title', '').lower())
    return (title, str(paper.get('year') or ''))


def paper_id(paper, library_id):
    # Legacy default-library IDs are stable, so v1 notes and PDFs remain linked.
    identity = ('doi:' + paper['doi']) if paper.get('doi') else ('title:' + '|'.join(title_key(paper)))
    prefix = '' if library_id == DEFAULT_LIBRARY_ID else 'library:' + library_id + '|'
    return hashlib.sha256((prefix + identity).encode('utf-8')).hexdigest()[:16]


def merge_bib(text, library_id=None, new_library_name=None):
    incoming = parse_bib(text)
    if not incoming:
        raise ValueError('未识别到有效文献。请确认导出格式为 BibTeX (.bib)，且包含 title 字段。')
    if library_id and new_library_name is not None:
        raise ValueError('不能同时指定已有文献库和新库名称')
    with LOCK:
        data = read_library()
        if new_library_name is not None:
            target = create_library_in_memory(data, new_library_name)
        else:
            target = find_library(data, library_id or DEFAULT_LIBRARY_ID)
            if target is None:
                raise ValueError('目标文献库不存在，请刷新页面后重试')
        target_id = target['id']
        existing = data['papers']
        subset = [p for p in existing if p.get('library_id', DEFAULT_LIBRARY_ID) == target_id]
        by_doi = {p['doi'].lower(): p for p in subset if p.get('doi')}
        by_title = {title_key(p): p for p in subset}
        used_ids = {p['id'] for p in existing}
        added = updated = 0
        for paper in incoming:
            match = (by_doi.get(paper['doi']) if paper['doi'] else None) or by_title.get(title_key(paper))
            if match:
                for field in ('key', 'title', 'author', 'year', 'journal', 'doi', 'keywords', 'abstract'):
                    if paper.get(field):
                        match[field] = paper[field]
                by_title[title_key(match)] = match
                if match.get('doi'):
                    by_doi[match['doi']] = match
                updated += 1
            else:
                identifier = paper_id(paper, target_id)
                if identifier in used_ids:
                    # A document can have been moved between libraries; avoid
                    # reusing its stable ID and overwriting its saved note/PDF.
                    identifier = secrets.token_hex(8)
                    while identifier in used_ids:
                        identifier = secrets.token_hex(8)
                used_ids.add(identifier)
                paper.update({'id': identifier, 'library_id': target_id, 'status': '未读',
                              'tags': [], 'added_at': now_iso()})
                existing.append(paper)
                by_title[title_key(paper)] = paper
                if paper['doi']:
                    by_doi[paper['doi']] = paper
                added += 1
        save_library(data)
    return {'added': added, 'updated': updated,
            'total': sum(p['library_id'] == target_id for p in existing),
            'library_id': target_id, 'library_name': target['name']}


def check_move_conflict(data, paper, target_id):
    for other in data['papers']:
        if other['id'] == paper['id'] or other.get('library_id', DEFAULT_LIBRARY_ID) != target_id:
            continue
        if paper.get('doi') and other.get('doi') and paper['doi'].lower() == other['doi'].lower():
            raise ValueError('目标文献库已存在相同 DOI 的文献，未移动')
        if title_key(paper) == title_key(other):
            raise ValueError('目标文献库已存在相同标题与年份的文献，未移动')

def lookup(library, identifier):
    if not ID_PATTERN.fullmatch(identifier):
        return None
    return next((p for p in library['papers'] if p['id'] == identifier), None)


def pdf_path(paper):
    candidates = [paper['id'] + '.pdf']
    for field in ('key', 'doi'):
        source = (paper.get(field) or '').strip()
        if source:
            stem = re.sub(r'[^A-Za-z0-9._-]+', '_', source).strip('. _')[:180]
            if stem:
                candidates.append(stem + '.pdf')
    for filename in candidates:
        path = PDFS / filename
        if path.is_file():
            return path
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = 'PaperShelf/1.1'

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args))

    def respond(self, code, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            if isinstance(body, str):
                body = body.encode('utf-8')
            else:
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def fail(self, code, message):
        self.respond(code, {'error': message})

    def body(self, max_size, allow_empty=False):
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise ValueError('Content-Length 无效')
        if size < 0 or (size == 0 and not allow_empty) or size > max_size:
            raise ValueError('文件为空或超过允许大小')
        data = self.rfile.read(size)
        if len(data) != size:
            raise ValueError('请求内容未完整接收')
        return data

    def mutation_allowed(self):
        origin = self.headers.get('Origin')
        if origin:
            host = self.headers.get('Host', '')
            if origin not in {'http://' + host, 'http://127.0.0.1:%s' % self.server.server_port,
                              'http://localhost:%s' % self.server.server_port}:
                self.fail(403, '请求来源不受信任')
                return False
        return True

    def do_GET(self):
        route = unquote(urlsplit(self.path).path)
        try:
            if route in {'/', '/index.html', '/app.js', '/style.css'}:
                files = {'/': 'index.html', '/index.html': 'index.html',
                         '/app.js': 'app.js', '/style.css': 'style.css'}
                path = BASE / files[route]
                kind = ('application/javascript' if route == '/app.js'
                        else 'text/css' if route == '/style.css' else 'text/html')
                return self.respond(200, path.read_bytes(), kind + '; charset=utf-8')
            if route == '/api/libraries':
                with LOCK:
                    data = read_library()
                    counts = {lib['id']: 0 for lib in data['libraries']}
                    for p in data['papers']:
                        counts[p.get('library_id', DEFAULT_LIBRARY_ID)] = counts.get(p.get('library_id', DEFAULT_LIBRARY_ID), 0) + 1
                    response = [dict(lib, count=counts[lib['id']]) for lib in data['libraries']]
                return self.respond(200, {'libraries': response})
            if route == '/api/papers':
                with LOCK:
                    papers = read_library()['papers']
                    response = [dict(p, has_pdf=bool(pdf_path(p))) for p in papers]
                return self.respond(200, {'papers': response})
            if route.startswith('/api/note/'):
                identifier = route.removeprefix('/api/note/')
                with LOCK:
                    paper = lookup(read_library(), identifier)
                    if paper is None:
                        return self.fail(404, '找不到文献')
                    path = NOTES / (identifier + '.md')
                    note = path.read_text(encoding='utf-8') if path.is_file() else ''
                return self.respond(200, {'note': note})
            if route.startswith('/api/pdf/'):
                identifier = route.removeprefix('/api/pdf/')
                with LOCK:
                    paper = lookup(read_library(), identifier)
                    path = pdf_path(paper) if paper else None
                if path is None:
                    return self.fail(404, '本地 PDF 尚未关联')
                return self.send_pdf(path)
            return self.fail(404, '未找到该路径')
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return self.fail(500, str(error))

    def send_pdf(self, path):
        size = path.stat().st_size
        start, end, code = 0, size - 1, 200
        requested_range = self.headers.get('Range', '')
        if requested_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested_range.strip())
            if not match or (not match.group(1) and not match.group(2)):
                return self.invalid_range(size)
            left, right = match.groups()
            if not left:
                suffix = int(right)
                if suffix == 0:
                    return self.invalid_range(size)
                start = max(size - suffix, 0)
            else:
                start = int(left)
                if right:
                    end = min(int(right), size - 1)
            if start > end or start >= size:
                return self.invalid_range(size)
            code = 206
        self.send_response(code)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Disposition', 'inline; filename="paper.pdf"')
        if code == 206:
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.end_headers()
        with path.open('rb') as pdf:
            pdf.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = pdf.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def invalid_range(self, size):
        self.send_response(416)
        self.send_header('Content-Range', 'bytes */%d' % size)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if not self.mutation_allowed():
            return
        route = urlsplit(self.path).path
        try:
            if route == '/api/libraries':
                data = json.loads(self.body(MAX_JSON).decode('utf-8'))
                if not isinstance(data, dict):
                    return self.fail(400, '请求格式无效')
                with LOCK:
                    db = read_library()
                    lib = create_library_in_memory(db, data.get('name'))
                    save_library(db)
                return self.respond(201, {'library': lib})
            if route == '/api/import-bib':
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                library_id = query.get('library_id', [None])[0]
                new_library_name = query.get('new_library_name', [None])[0]
                payload = self.body(MAX_BIB)
                text = None
                for encoding in ('utf-8-sig', 'utf-16', 'gb18030', 'latin-1'):
                    try:
                        text = payload.decode(encoding)
                        if encoding == 'utf-16' and '\x00' in text:
                            continue
                        break
                    except UnicodeError:
                        continue
                if not text:
                    return self.fail(400, '无法解码 BibTeX 文件')
                return self.respond(200, merge_bib(text, library_id=library_id, new_library_name=new_library_name))
            if route.startswith('/api/pdf/'):
                identifier = route.removeprefix('/api/pdf/')
                with LOCK:
                    paper = lookup(read_library(), identifier)
                    if paper is None:
                        return self.fail(404, '找不到文献')
                    payload = self.body(MAX_PDF)
                    if not payload.lstrip()[:5] == b'%PDF-':
                        return self.fail(400, '不是有效的 PDF 文件')
                    path = PDFS / (identifier + '.pdf')
                    temp = PDFS / (identifier + '.uploading')
                    temp.write_bytes(payload)
                    os.replace(temp, path)
                return self.respond(200, {'ok': True})
            return self.fail(404, '未找到该路径')
        except ValueError as error:
            return self.fail(400, str(error))
        except (OSError, json.JSONDecodeError) as error:
            return self.fail(500, str(error))

    def do_PUT(self):
        if not self.mutation_allowed():
            return
        route = urlsplit(self.path).path
        if not route.startswith('/api/note/'):
            return self.fail(404, '未找到该路径')
        identifier = route.removeprefix('/api/note/')
        try:
            payload = self.body(MAX_NOTE, allow_empty=True)
            note = payload.decode('utf-8')
            with LOCK:
                if lookup(read_library(), identifier) is None:
                    return self.fail(404, '找不到文献')
                atomic_write(NOTES / (identifier + '.md'), note)
            return self.respond(200, {'ok': True})
        except ValueError as error:
            return self.fail(400, str(error))
        except (OSError, UnicodeError) as error:
            return self.fail(500, str(error))

    def do_PATCH(self):
        if not self.mutation_allowed():
            return
        route = urlsplit(self.path).path
        try:
            if route.startswith('/api/library/'):
                library_id = route.removeprefix('/api/library/')
                data = json.loads(self.body(MAX_JSON).decode('utf-8'))
                if not isinstance(data, dict) or 'name' not in data:
                    return self.fail(400, '缺少文献库名称')
                name = validate_library_name(data['name'])
                with LOCK:
                    db = read_library()
                    library = find_library(db, library_id)
                    if library is None:
                        return self.fail(404, '文献库不存在')
                    if any(lib['id'] != library_id and lib['name'].casefold() == name.casefold()
                           for lib in db['libraries']):
                        return self.fail(400, '已有同名文献库')
                    library['name'] = name
                    save_library(db)
                return self.respond(200, {'library': library})
            if not route.startswith('/api/paper/'):
                return self.fail(404, '未找到该路径')
            identifier = route.removeprefix('/api/paper/')
            data = json.loads(self.body(MAX_JSON).decode('utf-8'))
            if not isinstance(data, dict):
                return self.fail(400, '请求内容无效')
            allowed = {'未读', '在读', '已读'}
            if 'status' in data and data['status'] not in allowed:
                return self.fail(400, '状态只能是未读、在读或已读')
            if 'tags' in data and (not isinstance(data['tags'], list) or
                                   len(data['tags']) > 30 or
                                   not all(isinstance(tag, str) and len(tag) <= 50 for tag in data['tags'])):
                return self.fail(400, '标签格式无效')
            if 'library_id' in data and not isinstance(data['library_id'], str):
                return self.fail(400, '目标文献库编号无效')
            with LOCK:
                db = read_library()
                paper = lookup(db, identifier)
                if paper is None:
                    return self.fail(404, '找不到文献')
                if 'library_id' in data:
                    if not find_library(db, data['library_id']):
                        return self.fail(400, '目标文献库不存在')
                    if paper.get('library_id', DEFAULT_LIBRARY_ID) != data['library_id']:
                        check_move_conflict(db, paper, data['library_id'])
                for field in ('status', 'tags', 'library_id'):
                    if field in data:
                        paper[field] = data[field]
                save_library(db)
            return self.respond(200, {'ok': True})
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            return self.fail(400, str(error))
        except OSError as error:
            return self.fail(500, str(error))


def main():
    parser = argparse.ArgumentParser(description='本地 BibTeX/PDF/Markdown 文献管理')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    init_storage()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('\n文献管理系统已启动： http://127.0.0.1:%s' % args.port, flush=True)
    print('文献与笔记保存在：%s' % DATA, flush=True)
    print('按 Ctrl+C 退出。\n', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止。')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
