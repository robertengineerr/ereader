#pragma once

const char* HTML_PAGE = R"rawhtml(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>e-Reader</title>
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

  <div class="drop-zone" id="dropZone">
    <p>Drag &amp; drop .txt files here</p>
    <label class="pick-btn" for="fileInput">Choose files</label>
    <input type="file" id="fileInput" accept=".txt" multiple>
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

    function uploadFiles(files) {
      const txt = [...files].filter(f => f.name.endsWith('.txt'));
      if (!txt.length) { showStatus('Only .txt files are supported.', false); return; }

      let i = 0;
      const prog = document.getElementById('progWrap');
      const bar  = document.getElementById('progBar');

      function next() {
        if (i >= txt.length) { prog.style.display = 'none'; loadFiles(); return; }
        const file = txt[i++];
        const fd = new FormData();
        fd.append('file', file, file.name);
        prog.style.display = 'block';
        bar.style.width = '0%';
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = e => {
          if (e.lengthComputable) bar.style.width = (e.loaded / e.total * 100) + '%';
        };
        xhr.onload = () => {
          showStatus(xhr.status === 200 ? 'Uploaded ' + file.name : 'Failed: ' + file.name, xhr.status === 200);
          next();
        };
        xhr.onerror = () => { showStatus('Upload error', false); next(); };
        xhr.open('POST', '/api/upload');
        xhr.send(fd);
      }
      next();
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

    loadFiles();
  </script>
</body>
</html>
)rawhtml";
