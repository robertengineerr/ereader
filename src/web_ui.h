#pragma once

const char* HTML_PAGE = R"rawhtml(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>e-Reader</title>
  <script src="https://unpkg.com/jszip@3.10.1/dist/jszip.min.js"></script>
  <script src="https://unpkg.com/pdfjs-dist@4.4.168/build/pdf.min.mjs" type="module" id="pdfjs"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      max-width: 580px;
      margin: 40px auto;
      padding: 0 20px;
      background: #f2f2f2;
      color: #222;
    }
    h1 { font-size: 1.4em; margin-bottom: 4px; }
    .subtitle { color: #888; font-size: 0.9em; margin-bottom: 28px; }
    .drop-zone {
      border: 2px dashed #bbb;
      border-radius: 10px;
      padding: 36px 20px;
      text-align: center;
      background: white;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .drop-zone.drag-over { border-color: #444; background: #f8f8f8; }
    .drop-zone p { margin: 0 0 14px; color: #666; font-size: 0.95em; }
    .pick-btn {
      display: inline-block;
      padding: 8px 20px;
      background: #222;
      color: white;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9em;
    }
    input[type=file] { display: none; }
    .progress-wrap { height: 4px; background: #e0e0e0; border-radius: 2px; margin-top: 16px; display: none; }
    .progress-bar  { height: 100%; background: #222; border-radius: 2px; width: 0%; transition: width 0.2s; }
    .status {
      margin-top: 12px;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 0.88em;
      display: none;
    }
    .status.ok  { background: #e8f5e9; color: #2e7d32; display: block; }
    .status.err { background: #ffebee; color: #c62828; display: block; }
    .section-title {
      font-size: 0.8em;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #888;
      margin: 28px 0 10px;
    }
    .file-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 11px 14px;
      background: white;
      border-radius: 8px;
      margin-bottom: 7px;
    }
    .file-left { display: flex; flex-direction: column; gap: 2px; }
    .file-name { font-weight: 500; font-size: 0.95em; }
    .file-size { font-size: 0.78em; color: #aaa; }
    .del-btn {
      border: 1px solid #ddd;
      background: none;
      color: #aaa;
      padding: 5px 12px;
      border-radius: 5px;
      cursor: pointer;
      font-size: 0.82em;
      white-space: nowrap;
    }
    .del-btn:hover { border-color: #e53935; color: #e53935; }
    .empty { color: #bbb; font-style: italic; font-size: 0.9em; padding: 10px 0; }
  </style>
</head>
<body>
  <h1>e-Reader</h1>
  <p class="subtitle">Drop .txt files below to add books to the device.</p>
  <button class="pick-btn" style="margin-bottom:18px;background:#555" onclick="exitWifi()">Exit WiFi Mode</button>

  <div class="drop-zone" id="dropZone">
    <p>Drag &amp; drop books here — .txt .epub .pdf .html .docx .fb2</p>
    <label class="pick-btn" for="fileInput">Choose files</label>
    <input type="file" id="fileInput" accept=".txt,.epub,.pdf,.html,.htm,.docx,.fb2,.mobi" multiple>
    <div class="progress-wrap" id="progWrap">
      <div class="progress-bar" id="progBar"></div>
    </div>
  </div>
  <div id="status" class="status"></div>

  <p class="section-title">Books on device</p>
  <div id="fileList"></div>

  <script>
    function fmt(b) {
      if (b < 1024) return b + ' B';
      if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
      return (b / 1048576).toFixed(1) + ' MB';
    }

    function showStatus(msg, ok) {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.className = 'status ' + (ok ? 'ok' : 'err');
      clearTimeout(el._t);
      el._t = setTimeout(() => el.className = 'status', 5000);
    }

    async function loadFiles() {
      try {
        const res = await fetch('/api/files');
        const files = await res.json();
        const list = document.getElementById('fileList');
        if (!files.length) {
          list.innerHTML = '<p class="empty">No books yet.</p>';
          return;
        }
        list.innerHTML = files.map(f => `
          <div class="file-item">
            <div class="file-left">
              <span class="file-name">${f.name}</span>
              <span class="file-size">${fmt(f.size)}</span>
            </div>
            <button class="del-btn" onclick="del('${f.name}')">Delete</button>
          </div>`).join('');
      } catch (e) {
        document.getElementById('fileList').innerHTML = '<p class="empty">Could not load file list.</p>';
      }
    }

    async function del(name) {
      const r = await fetch('/api/file?name=' + encodeURIComponent(name), { method: 'DELETE' });
      showStatus(r.ok ? 'Deleted ' + name : 'Failed to delete ' + name, r.ok);
      loadFiles();
    }

    // PDF → text via PDF.js
    async function pdfToText(file) {
      const pdfjsLib = await import('https://unpkg.com/pdfjs-dist@4.4.168/build/pdf.min.mjs');
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://unpkg.com/pdfjs-dist@4.4.168/build/pdf.worker.min.mjs';
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
      let text = '';
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        text += content.items.map(s => s.str).join(' ') + '\n';
      }
      return text;
    }

    // HTML/HTM → text
    function htmlToText(str) {
      const doc = new DOMParser().parseFromString(str, 'text/html');
      doc.querySelectorAll('script, style').forEach(el => el.remove());
      return doc.body.textContent.replace(/\s+/g, ' ').trim();
    }

    // DOCX → text (word/document.xml inside ZIP)
    async function docxToText(file) {
      const zip = await JSZip.loadAsync(file);
      const xml = await zip.file('word/document.xml').async('text');
      const doc = new DOMParser().parseFromString(xml, 'application/xml');
      return [...doc.querySelectorAll('w\\:t, t')].map(n => n.textContent).join(' ');
    }

    // FB2 → text (XML ebook format)
    async function fb2ToText(file) {
      const str = await file.text();
      const doc = new DOMParser().parseFromString(str, 'application/xml');
      doc.querySelectorAll('description, binary').forEach(el => el.remove());
      return doc.documentElement.textContent.replace(/\s+/g, ' ').trim();
    }

    async function epubToText(file) {
      const zip  = await JSZip.loadAsync(file);
      const parser = new DOMParser();

      // Locate OPF via META-INF/container.xml
      const containerXml = await zip.file('META-INF/container.xml').async('text');
      const container    = parser.parseFromString(containerXml, 'application/xml');
      const opfPath      = container.querySelector('rootfile').getAttribute('full-path');
      const opfDir       = opfPath.includes('/') ? opfPath.slice(0, opfPath.lastIndexOf('/') + 1) : '';

      // Parse OPF for spine order
      const opfText = await zip.file(opfPath).async('text');
      const opf     = parser.parseFromString(opfText, 'application/xml');
      const manifest = {};
      opf.querySelectorAll('manifest item').forEach(item => {
        manifest[item.getAttribute('id')] = item.getAttribute('href');
      });
      const spineIds = [...opf.querySelectorAll('spine itemref')].map(r => r.getAttribute('idref'));

      // Extract plain text from each spine item in order
      let text = '';
      for (const id of spineIds) {
        const href = manifest[id];
        if (!href) continue;
        const f = zip.file(opfDir + href) || zip.file(href);
        if (!f) continue;
        const html = await f.async('text');
        const doc  = parser.parseFromString(html, 'text/html');
        doc.querySelectorAll('script, style').forEach(el => el.remove());
        const chunk = doc.body.textContent.replace(/\s+/g, ' ').trim();
        if (chunk) text += chunk + '\n\n';
      }
      return text;
    }

    const SUPPORTED = ['.txt','.epub','.pdf','.html','.htm','.docx','.fb2'];
    function ext(name) { return name.slice(name.lastIndexOf('.')).toLowerCase(); }

    async function convertToText(file) {
      const e = ext(file.name);
      if (e === '.txt')              return file.text();
      if (e === '.epub')             return epubToText(file);
      if (e === '.pdf')              return pdfToText(file);
      if (e === '.html'||e==='.htm') return file.text().then(htmlToText);
      if (e === '.docx')             return docxToText(file);
      if (e === '.fb2')              return fb2ToText(file);
      throw new Error('Unsupported format');
    }

    async function uploadFiles(files) {
      const allowed = [...files].filter(f => SUPPORTED.includes(ext(f.name)));
      if (!allowed.length) { showStatus('Supported: ' + SUPPORTED.join(' '), false); return; }

      const prog = document.getElementById('progWrap');
      const bar  = document.getElementById('progBar');
      prog.style.display = 'block';
      bar.style.width = '0%';

      for (let i = 0; i < allowed.length; i++) {
        let file = allowed[i];
        let uploadName = file.name.replace(/\.[^.]+$/, '.txt');

        if (ext(file.name) !== '.txt') {
          showStatus('Converting ' + file.name + '...', true);
          try {
            const text = await convertToText(file);
            file = new File([text], uploadName, { type: 'text/plain' });
          } catch(e) {
            showStatus('Failed to convert ' + file.name + ': ' + e.message, false);
            continue;
          }
        }

        await new Promise(resolve => {
          const fd  = new FormData();
          fd.append('file', file, uploadName);
          bar.style.width = '0%';
          const xhr = new XMLHttpRequest();
          xhr.upload.onprogress = e => {
            if (e.lengthComputable) bar.style.width = (e.loaded / e.total * 100) + '%';
          };
          xhr.onload = () => {
            showStatus(xhr.status === 200 ? 'Uploaded ' + uploadName : 'Failed: ' + uploadName, xhr.status === 200);
            resolve();
          };
          xhr.onerror = () => { showStatus('Upload error', false); resolve(); };
          xhr.open('POST', '/api/upload');
          xhr.send(fd);
        });
      }

      prog.style.display = 'none';
      loadFiles();
    }

    const zone = document.getElementById('dropZone');
    zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      uploadFiles(e.dataTransfer.files);
    });
    document.getElementById('fileInput').addEventListener('change', e => {
      uploadFiles(e.target.files);
      e.target.value = '';
    });

    async function exitWifi() {
      try { await fetch('/api/exit'); } catch(_) {}
      document.body.innerHTML = '<p style="margin:40px;font-family:system-ui">Device returning to library...</p>';
    }

    loadFiles();
  </script>
</body>
</html>
)rawhtml";
