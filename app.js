"use strict";

const get = (id) => document.getElementById(id);
let papers = [];
let libraries = [];
let selectedLibraryId = localStorage.getItem('papershelf.library') || 'all';
let selectedId = null;
let lastSaved = '';
let noteLoadSequence = 0;
let saveTimer = null;
let saveChain = Promise.resolve();
let toastTimer;
let previewMode = false;
let libraryDialogMode = 'create';

async function api(path, options) {
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); }
  catch { throw new Error(`HTTP ${response.status}`); }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function toast(message) {
  const el = get('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 4000);
}

function authorShort(author) {
  return (author || '作者未知').split(/\s+and\s+/i).slice(0, 2).join(' · ');
}

function currentLibraryName() {
  return selectedLibraryId === 'all' ? '全部文献' :
    (libraries.find((lib) => lib.id === selectedLibraryId)?.name || '文献库');
}

function visiblePapers() {
  return papers.filter((paper) => selectedLibraryId === 'all' || paper.library_id === selectedLibraryId);
}

function filterPapers() {
  const query = get('search').value.trim().toLowerCase();
  const status = get('status-filter').value;
  const year = get('year-filter').value;
  return visiblePapers().filter((paper) => {
    if (status && paper.status !== status) return false;
    if (year && paper.year !== year) return false;
    const searchable = [paper.title, paper.author, paper.journal, paper.year, paper.doi, paper.key,
      paper.keywords, ...(paper.tags || [])].join(' ').toLowerCase();
    return searchable.includes(query);
  }).sort((a, b) => (b.year || '').localeCompare(a.year || '') || a.title.localeCompare(b.title));
}

function renderLibraries() {
  const list = get('library-list');
  list.replaceChildren();
  function addItem(id, name, count) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'library-item' + (selectedLibraryId === id ? ' active' : '');
    button.setAttribute('aria-pressed', selectedLibraryId === id ? 'true' : 'false');
    const label = document.createElement('span');
    label.textContent = name;
    label.className = 'library-item-name';
    label.title = name;
    const badge = document.createElement('span');
    badge.className = 'library-count';
    badge.textContent = String(count);
    button.append(label, badge);
    button.addEventListener('click', () => switchLibrary(id));
    list.append(button);
  }
  addItem('all', '全部文献', papers.length);
  for (const lib of libraries) {
    addItem(lib.id, lib.name, papers.filter((paper) => paper.library_id === lib.id).length);
  }
  get('active-library-name').textContent = currentLibraryName();
  get('rename-library-btn').classList.toggle('hidden', selectedLibraryId === 'all');
}

function renderList() {
  const list = get('paper-list');
  list.replaceChildren();
  const filtered = filterPapers();
  get('count').textContent = `${filtered.length} / ${visiblePapers().length} 篇`;
  for (const paper of filtered) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'paper-item' + (selectedId === paper.id ? ' selected' : '');
    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = paper.title;
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = [paper.year, authorShort(paper.author)].filter(Boolean).join(' · ');
    const line = document.createElement('div');
    line.className = 'tag-line';
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = paper.status || '未读';
    line.append(badge);
    if (paper.has_pdf) {
      const pdf = document.createElement('span');
      pdf.textContent = 'PDF ✓';
      line.append(pdf);
    }
    if (selectedLibraryId === 'all') {
      const lib = libraries.find((item) => item.id === paper.library_id);
      if (lib) {
        const label = document.createElement('span');
        label.className = 'paper-library-label';
        label.textContent = lib.name;
        line.append(label);
      }
    }
    if ((paper.tags || []).length) {
      const tags = document.createElement('span');
      tags.textContent = paper.tags.slice(0, 2).join(' · ');
      line.append(tags);
    }
    button.append(title, meta, line);
    button.addEventListener('click', () => selectPaper(paper.id));
    list.append(button);
  }
  if (!filtered.length) {
    const p = document.createElement('p');
    p.className = 'muted';
    p.style.padding = '15px 10px';
    p.textContent = visiblePapers().length ? '没有符合条件的文献。' :
      '这个文献库还没有论文。点击「导入 BibTeX」添加。';
    list.append(p);
  }
}

function renderYears() {
  const element = get('year-filter');
  const old = element.value;
  element.replaceChildren(new Option('全部年份', ''));
  [...new Set(visiblePapers().map((paper) => paper.year).filter(Boolean))]
    .sort((a, b) => b.localeCompare(a))
    .forEach((year) => element.add(new Option(year, year)));
  element.value = [...element.options].some((option) => option.value === old) ? old : '';
}

async function loadAll() {
  const [libraryResponse, paperResponse] = await Promise.all([
    api('/api/libraries'), api('/api/papers'),
  ]);
  libraries = libraryResponse.libraries;
  papers = paperResponse.papers;
  if (selectedLibraryId !== 'all' && !libraries.some((lib) => lib.id === selectedLibraryId)) {
    selectedLibraryId = 'all';
  }
  renderLibraries();
  renderYears();
  renderList();
}

function currentPaper() { return papers.find((paper) => paper.id === selectedId); }

function renderPaper() {
  const paper = currentPaper();
  get('empty').classList.toggle('hidden', Boolean(paper));
  get('detail').classList.toggle('hidden', !paper);
  if (!paper) {
    get('pdf-frame').src = 'about:blank';
    return;
  }
  const libraryName = libraries.find((lib) => lib.id === paper.library_id)?.name || '未知文献库';
  get('paper-meta').textContent = `${libraryName} · ${paper.year || '年份未知'} · ${paper.key || 'BibTeX'}`;
  get('paper-title').textContent = paper.title;
  get('paper-authors').textContent = paper.author ? paper.author.replace(/\s+and\s+/gi, ' · ') : '作者未知';
  get('paper-journal').textContent = paper.journal;
  get('paper-status').value = paper.status || '未读';
  const librarySelect = get('paper-library');
  librarySelect.replaceChildren(...libraries.map((lib) => new Option(lib.name, lib.id)));
  librarySelect.value = paper.library_id;
  get('tags').value = (paper.tags || []).join(', ');
  const doi = get('paper-doi');
  doi.classList.toggle('hidden', !paper.doi);
  if (paper.doi) doi.href = `https://doi.org/${encodeURIComponent(paper.doi)}`;
  const hasPDF = Boolean(paper.has_pdf);
  get('pdf-label').textContent = hasPDF ? '本地文件' : '未关联';
  get('pdf-frame').classList.toggle('hidden', !hasPDF);
  get('no-pdf').classList.toggle('hidden', hasPDF);
  get('pdf-open').classList.toggle('hidden', !hasPDF);
  get('pdf-open').href = hasPDF ? `/api/pdf/${paper.id}` : '#';
  get('pdf-frame').src = hasPDF ? `/api/pdf/${paper.id}` : 'about:blank';
}

function setSaveState(text) { get('save-state').textContent = text; }

async function flushNote() {
  clearTimeout(saveTimer);
  if (!selectedId) return true;
  const id = selectedId;
  const content = get('note-editor').value;
  if (content === lastSaved) {
    await saveChain;
    return true;
  }
  setSaveState('保存中…');
  const saving = saveChain.then(async () => {
    await api(`/api/note/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      body: content,
    });
    if (selectedId === id && get('note-editor').value === content) {
      lastSaved = content;
      setSaveState('已保存到本地');
    }
  });
  saveChain = saving.catch(() => {});
  try { await saving; return true; }
  catch (error) { setSaveState('保存失败'); toast(`笔记保存失败：${error.message}`); return false; }
}

function clearSelection() {
  selectedId = null;
  ++noteLoadSequence;
  clearTimeout(saveTimer);
  get('note-editor').disabled = true;
  get('note-editor').value = '';
  lastSaved = '';
  setSaveState('未选择论文');
  renderPaper();
  renderNotePreview();
}

async function switchLibrary(id, preferredPaperId = null, force = false) {
  if (!force && id === selectedLibraryId) return;
  if (id !== 'all' && !libraries.some((lib) => lib.id === id)) return;
  if (!(await flushNote())) return;
  clearSelection();
  selectedLibraryId = id;
  localStorage.setItem('papershelf.library', id);
  renderLibraries();
  renderYears();
  renderList();
  const first = filterPapers().find((paper) => paper.id === preferredPaperId) || filterPapers()[0];
  if (first) await selectPaper(first.id);
}

async function selectPaper(id) {
  if (id === selectedId) return;
  if (!(await flushNote())) return;
  selectedId = id;
  ++noteLoadSequence;
  const sequence = noteLoadSequence;
  renderList();
  renderPaper();
  get('note-editor').disabled = true;
  get('note-editor').value = '';
  lastSaved = '';
  setSaveState('载入笔记…');
  try {
    const data = await api(`/api/note/${id}`);
    if (sequence !== noteLoadSequence) return;
    get('note-editor').value = data.note;
    get('note-editor').disabled = false;
    lastSaved = data.note;
    setSaveState('已同步到本地');
    renderNotePreview();
  } catch (error) {
    if (sequence === noteLoadSequence) setSaveState('笔记载入失败');
    toast(error.message);
  }
}

function escapeHTML(value) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function inlineMarkdown(text) {
  let safe = escapeHTML(text);
  safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
  safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  return safe;
}

function renderNotePreview() {
  const source = get('note-editor').value;
  const lines = source.split(/\r?\n/);
  const html = [];
  let list = false;
  for (const line of lines) {
    const item = line.match(/^\s*[-*]\s+(.+)$/);
    if (item) {
      if (!list) { html.push('<ul>'); list = true; }
      html.push(`<li>${inlineMarkdown(item[1])}</li>`);
      continue;
    }
    if (list) { html.push('</ul>'); list = false; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const n = heading[1].length;
      html.push(`<h${n}>${inlineMarkdown(heading[2])}</h${n}>`);
    } else if (/^>\s?/.test(line)) {
      html.push(`<blockquote>${inlineMarkdown(line.replace(/^>\s?/, ''))}</blockquote>`);
    } else if (line.trim()) {
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    } else {
      html.push('<p></p>');
    }
  }
  if (list) html.push('</ul>');
  get('note-preview').innerHTML = html.join('');
}

function togglePreview(usePreview) {
  previewMode = usePreview;
  get('edit-tab').classList.toggle('active', !usePreview);
  get('preview-tab').classList.toggle('active', usePreview);
  get('note-editor').classList.toggle('hidden', usePreview);
  get('note-preview').classList.toggle('hidden', !usePreview);
  if (usePreview) renderNotePreview();
}

async function patchPaper(payload) {
  const paper = currentPaper();
  if (!paper) return;
  try {
    await api(`/api/paper/${paper.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    Object.assign(paper, payload);
    renderList();
    toast('文献信息已保存');
  } catch (error) {
    renderPaper();
    toast(`保存失败：${error.message}`);
  }
}

function populateImportLibraries() {
  const select = get('import-library');
  select.replaceChildren(new Option('请选择目标文献库…', ''), ...libraries.map((lib) => new Option(lib.name, lib.id)));
  select.options[0].disabled = true;
  select.add(new Option('＋ 新建文献库…', '__new__'));
  select.value = selectedLibraryId === 'all' ? '' : selectedLibraryId;
  get('import-new-library').value = '';
  updateImportNewLibrary();
}

function updateImportNewLibrary() {
  const isNew = get('import-library').value === '__new__';
  get('new-import-library-row').classList.toggle('hidden', !isNew);
  get('import-new-library').required = isNew;
  if (isNew) get('import-new-library').focus();
}

async function uploadBib(event) {
  event.preventDefault();
  const file = get('bib-upload').files[0];
  if (!file) return toast('请选择 BibTeX 文件');
  const selectValue = get('import-library').value;
  if (!selectValue) return toast('请选择目标文献库');
  const creating = selectValue === '__new__';
  const name = get('import-new-library').value.trim();
  if (creating && !name) return toast('请输入新文献库的名称');
  const qs = creating ? `new_library_name=${encodeURIComponent(name)}` :
    `library_id=${encodeURIComponent(selectValue)}`;
  const button = get('import-submit');
  button.disabled = true;
  button.textContent = '正在导入…';
  try {
    const result = await api(`/api/import-bib?${qs}`, { method: 'POST', body: file });
    get('import-dialog').close();
    get('import-form').reset();
    await loadAll();
    await switchLibrary(result.library_id, null, true);
    toast(`已导入「${result.library_name}」：新增 ${result.added} 篇，更新 ${result.updated} 篇，库内共 ${result.total} 篇`);
  } catch (error) {
    toast(`导入失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = '导入文献';
  }
}

function openLibraryDialog(mode) {
  libraryDialogMode = mode;
  const isRename = mode === 'rename';
  const current = libraries.find((lib) => lib.id === selectedLibraryId);
  if (isRename && !current) return;
  get('library-dialog-title').textContent = isRename ? '重命名文献库' : '新建文献库';
  get('library-submit').textContent = isRename ? '保存名称' : '创建文献库';
  get('library-name').value = isRename ? current.name : '';
  get('library-dialog').showModal();
  get('library-name').focus();
}

async function saveLibraryDialog(event) {
  event.preventDefault();
  const name = get('library-name').value.trim();
  const isRename = libraryDialogMode === 'rename';
  const button = get('library-submit');
  button.disabled = true;
  try {
    const result = await api(isRename ? `/api/library/${selectedLibraryId}` : '/api/libraries', {
      method: isRename ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    get('library-dialog').close();
    await loadAll();
    if (!isRename) await switchLibrary(result.library.id);
    else { renderLibraries(); renderPaper(); }
    toast(isRename ? '文献库已重命名' : `已创建「${name}」文献库`);
  } catch (error) {
    toast(`操作失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

async function movePaper(event) {
  const paper = currentPaper();
  if (!paper) return;
  const oldLibraryId = paper.library_id;
  const targetId = event.target.value;
  if (oldLibraryId === targetId) return;
  if (!(await flushNote())) {
    event.target.value = oldLibraryId;
    return;
  }
  try {
    await api(`/api/paper/${paper.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({library_id: targetId}),
    });
    await loadAll();
    await switchLibrary(targetId, paper.id, true);
    toast('文献已移动到目标库，PDF 与原有笔记保持关联');
  } catch (error) {
    event.target.value = oldLibraryId;
    toast(`移动失败：${error.message}`);
  }
}

async function uploadPDF(event) {
  const file = event.target.files[0];
  const id = selectedId;
  if (!file || !id) return;
  try {
    if (!file.name.toLowerCase().endsWith('.pdf')) throw new Error('请选择 PDF 文件');
    await api(`/api/pdf/${id}`, { method: 'POST', headers: {'Content-Type': 'application/pdf'}, body: file });
    const paper = papers.find((item) => item.id === id);
    if (paper) paper.has_pdf = true;
    if (selectedId === id) renderPaper();
    renderList();
    toast('PDF 已复制到本地文献库');
  } catch (error) { toast(`关联失败：${error.message}`); }
  finally { event.target.value = ''; }
}

get('open-import').addEventListener('click', () => {
  populateImportLibraries();
  get('import-dialog').showModal();
});
get('import-library').addEventListener('change', updateImportNewLibrary);
get('import-form').addEventListener('submit', uploadBib);
get('cancel-import').addEventListener('click', () => get('import-dialog').close());
get('new-library-btn').addEventListener('click', () => openLibraryDialog('create'));
get('rename-library-btn').addEventListener('click', () => openLibraryDialog('rename'));
get('library-form').addEventListener('submit', saveLibraryDialog);
get('cancel-library').addEventListener('click', () => get('library-dialog').close());
get('paper-library').addEventListener('change', movePaper);
get('pdf-upload').addEventListener('change', uploadPDF);
get('search').addEventListener('input', renderList);
get('status-filter').addEventListener('change', renderList);
get('year-filter').addEventListener('change', renderList);
get('paper-status').addEventListener('change', (event) => patchPaper({status: event.target.value}));
get('tags').addEventListener('change', (event) => {
  const tags = [...new Set(event.target.value.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean))];
  patchPaper({tags});
});
get('tags').addEventListener('keydown', (event) => { if (event.key === 'Enter') event.target.blur(); });
get('note-editor').addEventListener('input', () => {
  setSaveState('未保存…');
  if (previewMode) renderNotePreview();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushNote, 750);
});
get('template-btn').addEventListener('click', () => {
  if (!selectedId) return;
  const editor = get('note-editor');
  const template = '## 研究问题\n\n## 研究方法\n\n## 主要结论\n\n## 值得借鉴的内容\n\n## 局限与思考\n\n';
  editor.value += (editor.value.trim() ? '\n\n' : '') + template;
  editor.dispatchEvent(new Event('input'));
  togglePreview(false);
  editor.focus();
});
get('edit-tab').addEventListener('click', () => togglePreview(false));
get('preview-tab').addEventListener('click', () => togglePreview(true));
document.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
    event.preventDefault();
    flushNote();
  }
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden && selectedId && get('note-editor').value !== lastSaved) {
    fetch(`/api/note/${selectedId}`, { method: 'PUT',
      headers: {'Content-Type': 'text/plain; charset=utf-8'},
      body: get('note-editor').value, keepalive: true }).catch(() => {});
  }
});

loadAll().then(() => switchLibrary(selectedLibraryId, null, true))
  .catch((error) => toast(`读取本地文献库失败：${error.message}`));
