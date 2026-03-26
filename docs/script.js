document.addEventListener('DOMContentLoaded', () => {
  const STORAGE_KEY = 'pjb-sidebar-state';

  // ── Helpers ──────────────────────────────────────────────────
  function loadState() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
  }
  function saveState(state) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {}
  }

  // ── Restore sidebar collapsed/expanded state ────────────────
  const state = loadState();
  document.querySelectorAll('.sidebar-heading[data-section]').forEach(h => {
    const key = h.dataset.section;
    if (key in state) {
      h.classList.toggle('collapsed', state[key]);
    }
    // Measure natural height so CSS max-height animation works
    const ul = h.nextElementSibling;
    if (ul && ul.classList.contains('sidebar-links')) {
      if (!h.classList.contains('collapsed')) {
        ul.style.maxHeight = ul.scrollHeight + 'px';
      }
    }
  });

  // ── Highlight current page ──────────────────────────────────
  const currentPage = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.sidebar-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href && !href.startsWith('#')) {
      if (href.split('/').pop() === currentPage) a.classList.add('active');
    }
  });

  // ── Sidebar search filter ───────────────────────────────────
  const input = document.getElementById('sidebar-search');
  if (input) {
    input.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      document.querySelectorAll('.sidebar-links a').forEach(a => {
        a.style.display = (!q || a.textContent.toLowerCase().includes(q)) ? '' : 'none';
      });
      document.querySelectorAll('.sidebar-section').forEach(sec => {
        const links = sec.querySelectorAll('.sidebar-links a');
        const anyVisible = Array.from(links).some(a => a.style.display !== 'none');
        sec.style.display = anyVisible || !q ? '' : 'none';
        if (q) {
          const heading = sec.querySelector('.sidebar-heading');
          if (heading) expandSection(heading);
        }
      });
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const first = document.querySelector('.sidebar-links a:not([style*="display: none"])');
        if (first) { first.click(); }
      }
    });
  }

  // ── Collapsible sections with animation ─────────────────────
  function expandSection(heading) {
    heading.classList.remove('collapsed');
    const ul = heading.nextElementSibling;
    if (ul && ul.classList.contains('sidebar-links')) {
      ul.style.maxHeight = ul.scrollHeight + 'px';
    }
  }
  function collapseSection(heading) {
    heading.classList.add('collapsed');
    const ul = heading.nextElementSibling;
    if (ul && ul.classList.contains('sidebar-links')) {
      // Force a reflow so the transition starts from the current height
      ul.style.maxHeight = ul.scrollHeight + 'px';
      ul.offsetHeight; // reflow
      ul.style.maxHeight = '0';
    }
  }

  document.querySelectorAll('.sidebar-heading').forEach(h => {
    h.addEventListener('click', () => {
      const willCollapse = !h.classList.contains('collapsed');
      if (willCollapse) {
        collapseSection(h);
      } else {
        expandSection(h);
      }
      // Persist
      const key = h.dataset.section;
      if (key) {
        const s = loadState();
        s[key] = willCollapse;
        saveState(s);
      }
    });
  });

  // After expand animation ends, set max-height to none so dynamically
  // added content (e.g. search results) isn't clipped
  document.querySelectorAll('.sidebar-links').forEach(ul => {
    ul.addEventListener('transitionend', () => {
      const heading = ul.previousElementSibling;
      if (heading && !heading.classList.contains('collapsed')) {
        ul.style.maxHeight = 'none';
      }
    });
  });

  // ── Mobile menu toggle ──────────────────────────────────────
  const toggle = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('open');
    });
    if (overlay) {
      overlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
      });
    }
  }

  // ── Back to top ─────────────────────────────────────────────
  const btn = document.querySelector('.back-to-top');
  if (btn) {
    window.addEventListener('scroll', () => {
      btn.classList.toggle('visible', window.scrollY > 400);
    });
    btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  // ── Active sidebar link tracking + TOC sub-section collapse ──
  const sections = document.querySelectorAll('.api-section, h2[id]');
  const allLinks = document.querySelectorAll('.sidebar-links a');
  const tocSubs = document.querySelectorAll('.toc-sub');

  function expandTocSub(sub) {
    if (sub.classList.contains('expanded')) return;
    sub.classList.add('expanded');
    sub.style.maxHeight = sub.scrollHeight + 'px';
    sub.addEventListener('transitionend', function handler() {
      if (sub.classList.contains('expanded')) sub.style.maxHeight = 'none';
      sub.removeEventListener('transitionend', handler);
    });
  }
  function collapseTocSub(sub) {
    if (!sub.classList.contains('expanded')) return;
    sub.style.maxHeight = sub.scrollHeight + 'px';
    sub.offsetHeight; // reflow
    sub.classList.remove('expanded');
    sub.style.maxHeight = '0';
  }

  function updateActiveTocSub(activeH2Id) {
    tocSubs.forEach(sub => {
      if (sub.dataset.parent === activeH2Id) {
        expandTocSub(sub);
      } else {
        collapseTocSub(sub);
      }
    });
  }

  if (sections.length && allLinks.length) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          allLinks.forEach(l => {
            l.classList.toggle('active', l.getAttribute('href') === '#' + id);
          });
          // Find the parent H2 for this section
          let h2Id = id;
          const el = entry.target;
          if (el.tagName === 'H3' || (el.tagName !== 'H2' && el.closest && !el.matches('h2'))) {
            // Walk backwards to find the owning H2
            let prev = el;
            while (prev) {
              prev = prev.previousElementSibling;
              if (prev && prev.tagName === 'H2' && prev.id) {
                h2Id = prev.id;
                break;
              }
            }
          }
          updateActiveTocSub(h2Id);
        }
      });
    }, { rootMargin: '-80px 0px -60% 0px', threshold: 0 });
    sections.forEach(s => { if (s.id) observer.observe(s); });

    // Also observe h3[id] elements for sub-section tracking
    document.querySelectorAll('h3[id]').forEach(s => observer.observe(s));
  }

  // ── Smooth scroll for sidebar links ─────────────────────────
  document.querySelectorAll('.sidebar-links a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
        history.replaceState(null, '', a.getAttribute('href'));
      }
    });
  });

  // ── Decompress zstd search index (async, non-blocking) ──────
  let searchIndex = [];

  function loadSearchIndex() {
    const el = document.getElementById('zstd-data');
    if (!el || !el.textContent.trim()) return;
    function tryLoad() {
      if (typeof fzstd === 'undefined') return false;
      try {
        const b64 = el.textContent.trim();
        const compressed = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
        const decompressed = fzstd.decompress(compressed);
        const json = new TextDecoder().decode(decompressed);
        searchIndex = JSON.parse(json);
        // signal that the search index is ready
        if (searchIndex && searchIndex.length) {
          document.dispatchEvent(new CustomEvent('searchIndexLoaded'));
          return true;
        }
      } catch (e) {
        console.error('Failed to decompress search index:', e);
      }
      return false;
    }
    if (!tryLoad()) {
      // fzstd not yet loaded — poll until available
      const iv = setInterval(() => { if (tryLoad()) clearInterval(iv); }, 50);
    }
  }
  loadSearchIndex();

  

  // ── Header full-text search ─────────────────────────────────
  const headerSearch = document.getElementById('header-search');
  const searchResults = document.getElementById('search-results');

  function doSearch(query) {
    if (!searchIndex || !query.trim()) {
      searchResults.style.display = 'none';
      return;
    }
    const q = query.toLowerCase().trim();
    const tokens = q.split(/\s+/).filter(Boolean);
    const hits = [];

    function scorePage(page) {
      let score = 0;
      const title = (page.title || '').toLowerCase();
      if (title === q) score += 200;
      else if (title.includes(q)) score += 120 - Math.min(100, title.indexOf(q));

      for (const sec of page.sections || []) {
        const heading = (sec.heading || '').toLowerCase();
        const text = (sec.text || '').toLowerCase();
        if (heading.includes(q)) score += 40;
        if (text.includes(q)) score += 20;
        for (const t of tokens) {
          if (heading.includes(t)) score += 8;
          if (text.includes(t)) score += 4;
        }
      }

      // token coverage bonus
      let cover = 0;
      for (const t of tokens) {
        if (title.includes(t)) cover += 2;
      }
      score += cover;
      return score;
    }

    for (const page of searchIndex) {
      const s = scorePage(page);
      if (s > 0) {
        // pick best matching section for snippet
        let bestSec = null;
        for (const sec of page.sections || []) {
          for (const t of tokens) {
            if ((sec.text || '').toLowerCase().includes(t) || (sec.heading || '').toLowerCase().includes(t)) {
              bestSec = sec; break;
            }
          }
          if (bestSec) break;
        }
        const hit = { url: page.url, title: page.title, text: bestSec ? bestSec.text : '', score: s };
        hits.push(hit);
      }
    }

    // Sort and dedupe
    hits.sort((a, b) => b.score - a.score);
    const seen = new Set();
    const unique = [];
    for (const h of hits) {
      const baseUrl = h.url.split('#')[0];
      if (!seen.has(baseUrl) && unique.length < 12) {
        seen.add(baseUrl);
        unique.push(h);
      }
    }
    if (!unique.length) {
      searchResults.innerHTML = '<div class="search-no-results">No results</div>';
      searchResults.style.display = 'block';
      return;
    }
    searchResults.innerHTML = unique.map(h => {
      const snippet = h.text ? h.text.substring(0, 100) : '';
      const heading = h.heading ? ` › ${h.heading}` : '';
      const fmtTitle = (h.title + heading).replace(/\[ext\]/g, '<span class="ext-tag">ext</span>');
      const href = addVerToHref(h.url);
      return `<a class="search-hit" href="${href}"><strong>${fmtTitle}</strong><span>${snippet}</span></a>`;
    }).join('');
    searchResults.style.display = 'block';
  }

  if (headerSearch) {
    headerSearch.addEventListener('input', () => doSearch(headerSearch.value));
    headerSearch.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        headerSearch.value = '';
        searchResults.style.display = 'none';
        headerSearch.blur();
      }
      if (e.key === 'Enter') {
        const first = searchResults.querySelector('.search-hit');
        if (first) { window.location.href = first.getAttribute('href'); }
      }
    });
    document.addEventListener('click', e => {
      if (!headerSearch.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.style.display = 'none';
      }
    });
    // Ctrl+K shortcut
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        headerSearch.focus();
        headerSearch.select();
      }
    });
  }

  // ── Code block copy buttons ─────────────────────────────────
  function addCopyButtons() {
    document.querySelectorAll('pre > code').forEach(codeEl => {
      const pre = codeEl.parentElement;
      if (!pre) return;
      if (pre.parentElement && pre.parentElement.classList.contains('code-wrap')) return;
      const wrap = document.createElement('div');
      wrap.className = 'code-wrap';
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      const btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Copy code');
      btn.textContent = 'Copy';
      wrap.appendChild(btn);
      btn.addEventListener('click', async () => {
        try {
          const text = codeEl.innerText;
          await navigator.clipboard.writeText(text);
          btn.textContent = 'Copied';
          setTimeout(() => btn.textContent = 'Copy', 1500);
        } catch (e) {
          console.error('Copy failed', e);
          btn.textContent = 'Copy';
        }
      });
    });
  }
  // Run immediately for the current page
  try { addCopyButtons(); } catch (e) { /* ignore */ }

  // ── Backlinks & Related pages ───────────────────────────────
  function renderBacklinksAndRelated() {
    if (!searchIndex || !searchIndex.length) return;
    const me = searchIndex.find(p => (p.url || '').split('/').pop() === currentPage);
    if (!me) return;
    const content = document.querySelector('.content');
    if (!content) return;
    if (document.getElementById('page-extras')) return; // only once

    const extras = document.createElement('div');
    extras.id = 'page-extras';
    extras.className = 'page-extras';

    // Related comes first (as requested). Render as an H2-equivalent section.
    if (me.related && me.related.length) {
      const hr = document.createElement('h2'); hr.textContent = 'Related';
      extras.appendChild(hr);
      const rel = document.createElement('div');
      rel.className = 'related';
      const ul = document.createElement('ul');
      me.related.slice(0, 12).forEach(slug => {
        const p = searchIndex.find(x => x.slug === slug);
        if (!p) return;
        const a = document.createElement('a');
        const hrefOrig = p.url || (slug === 'index' ? 'index.html' : slug + '.html');
        a.href = addVerToHref(hrefOrig);
        a.textContent = p.title || slug;
        const li = document.createElement('li'); li.appendChild(a); ul.appendChild(li);
      });
      rel.appendChild(ul);
      extras.appendChild(rel);
    }

    // Backlinks after Related. Collapsed by default using <details> so large lists don't overwhelm the page.
    if (me.backlinks && me.backlinks.length) {
      const hb = document.createElement('h2'); hb.textContent = 'Backlinks';
      extras.appendChild(hb);
      const det = document.createElement('details');
      det.className = 'backlinks-details';
      const summary = document.createElement('summary');
      summary.textContent = `Show ${me.backlinks.length} backlinks`;
      det.appendChild(summary);
      const ul = document.createElement('ul');
      me.backlinks.forEach(slug => {
        const p = searchIndex.find(x => x.slug === slug);
        if (!p) return;
        const a = document.createElement('a');
        const hrefOrig = p.url || (slug === 'index' ? 'index.html' : slug + '.html');
        a.href = addVerToHref(hrefOrig);
        a.textContent = p.title || slug;
        const li = document.createElement('li'); li.appendChild(a); ul.appendChild(li);
      });
      det.appendChild(ul);
      extras.appendChild(det);
    }

    if (extras.childElementCount) content.appendChild(extras);
  }

  // Ensure backlinks are rendered whenever the search index becomes available
  document.addEventListener('searchIndexLoaded', () => {
    try { renderBacklinksAndRelated(); } catch (e) { /* ignore */ }
    try { persistVerOnLinks(); } catch (e) { /* ignore */ }
  });

  // ── Versioning: ?ver= parameter support (resolve to commit, fetch historical HTML) ──
  async function loadGitMeta() {
    // If opened via file://, skip network fetch to avoid CORS errors and
    // read the inline <script id="git-meta"> injected at build-time.
    if (location.protocol === 'file:') {
      try {
        const el = document.getElementById('git-meta');
        if (el && el.textContent && el.textContent.trim()) return JSON.parse(el.textContent.trim());
      } catch (e) {
        console.error('Failed to parse inline git_meta:', e);
      }
      return null;
    }

    // Try network fetch first (works when served over HTTP)
    try {
      const r = await fetch('git_meta.json', { cache: 'no-store' });
      if (r && r.ok) return await r.json();
    } catch (e) {
      // ignore network errors and fall back to inline data
    }

    // Fallback: read inline <script id="git-meta"> injected at build-time
    try {
      const el = document.getElementById('git-meta');
      if (el && el.textContent && el.textContent.trim()) {
        return JSON.parse(el.textContent.trim());
      }
    } catch (e) {
      console.error('Failed to parse inline git_meta:', e);
    }

    return null;
  }

  function resolveVerToCommit(ver, meta) {
    if (!meta) return null;
    const commits = meta.commits || [];
    // full or prefix hash
    if (/^[0-9a-f]{7,40}$/i.test(ver)) {
      const match = commits.find(c => c.startsWith(ver));
      if (match) return match;
      if (ver.length === 40) return ver; // accept full hash even if not in list
      return null;
    }
    // If a short numeric index was provided, treat it as an index into the commits
    if (/^\d+$/.test(ver)) {
      const i = parseInt(ver, 10);
      if (i >= 0 && i < commits.length) return commits[i];
      return null;
    }

    // If a version code like "1A" was provided, look it up in meta.versions
    if (meta.versions && Array.isArray(meta.versions)) {
      for (const v of meta.versions) {
        if (v.code && v.code.toLowerCase() === ver.toLowerCase()) return v.commit;
      }
    }

    // Fallback: check tags (legacy)
    if (meta.tags && meta.tags[ver]) return meta.tags[ver];
    for (const t in (meta.tags || {})) {
      if (t.toLowerCase() === ver.toLowerCase()) return meta.tags[t];
    }
    return null;
  }

  function applyPagesFilter(commit, meta) {
    try {
      if (!meta || !meta.pages_by_commit || !commit) return;
      const allowed = new Set(meta.pages_by_commit[commit] || []);
      if (!allowed.size) return;

      document.querySelectorAll('.sidebar-links a').forEach(a => {
        const href = a.getAttribute('href') || '';
        if (!href || href.startsWith('#')) return;
        const page = href.split('/').pop().split('?')[0].split('#')[0];
        const base = page.replace(/\.html$/, '');
        const li = a.closest('li') || a.parentElement;
        if (!allowed.has(base)) {
          if (li) li.style.display = 'none'; else a.style.display = 'none';
        } else {
          if (li) li.style.display = ''; else a.style.display = '';
        }
      });

      // Hide entire sections with no visible links
      document.querySelectorAll('.sidebar-section').forEach(sec => {
        const links = sec.querySelectorAll('.sidebar-links a');
        const any = Array.from(links).some(l => {
          const li = l.closest('li') || l.parentElement;
          return li ? li.style.display !== 'none' : l.style.display !== 'none';
        });
        sec.style.display = any ? '' : 'none';
      });
    } catch (e) {
      console.error('applyPagesFilter failed:', e);
    }
  }

  async function handleVersionParam() {
    const params = new URLSearchParams(location.search);
    const ver = params.get('ver');
    if (!ver) return;
    const meta = await loadGitMeta();
    if (!meta) return;
    const commit = resolveVerToCommit(ver, meta);
    if (!commit) return;

    // Build raw.githubusercontent URL to fetch historical HTML. If the
    // generated HTML isn't present at that commit (404), fall back to
    // fetching the source markdown and render it client-side using
    // `marked` (included via CDN in the template).
    if (!meta.repo) return;
    const page = currentPage || 'index.html';
    const rawHtmlUrl = `https://raw.githubusercontent.com/${meta.repo}/${commit}/docs/site/${page}`;
    try {
      const r = await fetch(rawHtmlUrl, { cache: 'no-store' });
      if (r && r.ok) {
        const html = await r.text();
        const parser = new DOMParser();
        const doc2 = parser.parseFromString(html, 'text/html');
        const newContent = doc2.querySelector('.content');
        if (!newContent) return;
        // Insert a banner to indicate this is a historical version
        const banner = document.createElement('div');
        banner.className = 'callout callout-info';
        const short = commit.slice(0, 8);
        banner.innerHTML = `<strong>Viewing version ${short}</strong> — <a href="${page}">View live</a>`;
        // Replace content
        const content = document.querySelector('.content');
        if (!content) return;
        content.innerHTML = '';
        content.appendChild(banner);
        // Append the historical content body
        Array.from(newContent.children).forEach(n => content.appendChild(document.importNode(n, true)));
        document.title = doc2.title || document.title;
        // Re-initialize copy buttons for the loaded content
        try { addCopyButtons(); } catch (e) { /* ignore */ }
        // Filter sidebar to pages that existed at this commit
        try { applyPagesFilter(commit, meta); } catch (e) { /* ignore */ }
        return;
      }
    } catch (e) {
      // network error or CORS — continue to markdown fallback
      console.error('Failed to fetch historical HTML page:', e);
    }

    // Markdown fallback: attempt to fetch the source markdown for this
    // page at that commit. The build embeds a `src_map` in `git_meta`
    // mapping page basenames to their docs/src path.
    try {
      const key = page.replace(/\.html$/, '');
      const srcPath = meta.src_map && meta.src_map[key];
      if (srcPath) {
        const mdUrl = `https://raw.githubusercontent.com/${meta.repo}/${commit}/${srcPath}`;
        try {
          const rm = await fetch(mdUrl, { cache: 'no-store' });
          if (rm && rm.ok) {
            const md = await rm.text();
            // Render markdown using `marked` (if available)
            let rendered = md;
            try {
              if (typeof marked === 'function') rendered = marked(md);
              else if (marked && typeof marked.parse === 'function') rendered = marked.parse(md);
            } catch (e) {
              console.error('Marked render failed:', e);
            }
            const content = document.querySelector('.content');
            if (!content) return;
            const banner = document.createElement('div');
            banner.className = 'callout callout-info';
            const short = commit.slice(0, 8);
            banner.innerHTML = `<strong>Viewing version ${short}</strong> — <a href="${page}">View live</a>`;
            content.innerHTML = '';
            content.appendChild(banner);
            // Insert rendered markdown (may be raw markdown if marked missing)
            const wrapper = document.createElement('div');
            wrapper.innerHTML = rendered;
            Array.from(wrapper.children).forEach(n => content.appendChild(document.importNode(n, true)));
            document.title = `${document.title} — ${short}`;
            try { addCopyButtons(); } catch (e) { /* ignore */ }
            // Filter sidebar to pages that existed at this commit
            try { applyPagesFilter(commit, meta); } catch (e) { /* ignore */ }
            return;
          }
        } catch (e) {
          console.error('Failed to fetch historical markdown:', e);
        }
      }
    } catch (e) {
      console.error('Markdown fallback error:', e);
    }
  }

  // Attempt to apply versioning if requested
  try { handleVersionParam(); } catch (e) { /* ignore */ }

  // Populate the version selector from git_meta.json
  async function populateVersionSelector() {
    const sel = document.getElementById('version-selector');
    if (!sel) return;
    const meta = await loadGitMeta();
    if (!meta) return;
    // Replace options with Live + commit-based versions detected in git commit messages
    sel.innerHTML = '';
    const live = document.createElement('option'); live.value = ''; live.textContent = 'Live';
    sel.appendChild(live);

    // If build emitted `meta.versions`, use that (commit messages like "1A - message")

    if (meta.versions && Array.isArray(meta.versions) && meta.versions.length) {
      // show newest first
      const list = meta.versions.slice().reverse();
      // Only include version codes that match digits+letter (e.g. 1A, 12B)
      const codeRE = /^[0-9]+[A-Za-z]$/;
      // If the builder provided pages_by_commit info, only include versions
      // whose commit contains the current page.
      const pagesByCommit = meta.pages_by_commit || {};
      const pageBase = (currentPage || 'index.html').replace(/\.html$/, '');
      const useFilter = pagesByCommit && Object.keys(pagesByCommit).length > 0;
      for (const v of list) {
        if (!v || !v.commit || !v.code) continue;
        if (!codeRE.test(String(v.code))) continue;
        if (useFilter) {
          const avail = pagesByCommit[v.commit] || pagesByCommit[v.commit.slice(0,8)];
          if (!avail || !avail.includes(pageBase)) continue;
        }
        const opt = document.createElement('option');
        // Use the short version code as the option value so ?ver=1A is compact
        opt.value = v.code;
        // Display only the compact code in the select
        opt.textContent = v.code;
        if (v.label) opt.dataset.label = v.label;
        if (v.commit) opt.dataset.commit = v.commit.slice(0,8);
        sel.appendChild(opt);
      }
    } else {
      // Fallback: show latest commit and recent commits (but filter by availability if possible)
      const commits = meta.commits || [];
      const pagesByCommit = meta.pages_by_commit || {};
      const pageBase = (currentPage || 'index.html').replace(/\.html$/, '');
      const useFilter = pagesByCommit && Object.keys(pagesByCommit).length > 0;
      if (commits.length) {
        const latest = commits[commits.length - 1];
        if (!useFilter || (pagesByCommit[latest] && pagesByCommit[latest].includes(pageBase))) {
          const opt = document.createElement('option'); opt.value = latest; opt.textContent = latest.slice(0,8); opt.dataset.commit = latest.slice(0,8); sel.appendChild(opt);
        }
        const recent = commits.slice(-10).reverse();
        for (const c of recent) {
          if (useFilter && (!(pagesByCommit[c] && pagesByCommit[c].includes(pageBase)))) continue;
          const o = document.createElement('option'); o.value = c; o.textContent = c.slice(0,8); o.dataset.commit = c.slice(0,8); sel.appendChild(o);
        }
      }
    }

    // No description shown under selector by design.

    // If a `ver` parameter exists in the URL, reflect it in the selector.
    try {
      const params = new URLSearchParams(location.search);
      const verParam = params.get('ver');
      if (verParam) {
        const v = verParam;
        // Try to find an exact option match (case-insensitive)
        let found = Array.from(sel.options).find(o => String(o.value).toLowerCase() === String(v).toLowerCase());
        if (!found) {
          // Try matching by short commit in data-commit
          const short = String(v).slice(0,8).toLowerCase();
          found = Array.from(sel.options).find(o => o.dataset && o.dataset.commit && String(o.dataset.commit).toLowerCase() === short);
        }
        if (found) {
          sel.value = found.value;
        }
      }
    } catch (e) { /* ignore */ }

    sel.addEventListener('change', () => {
      const v = sel.value;
      // Navigate explicitly so behavior is consistent across environments.
      if (!v) {
        const params = new URLSearchParams(location.search);
        params.delete('ver');
        const qs = params.toString();
        const newUrl = qs ? `${location.pathname}?${qs}` : location.pathname;
        location.href = newUrl;
      } else {
        const newUrl = `${location.pathname}?ver=${encodeURIComponent(v)}`;
        location.href = newUrl;
      }
    });
    try { persistVerOnLinks(); } catch (e) { /* ignore */ }
  }

  // Helper: append current `ver` query param to an internal href if present.
  function addVerToHref(href) {
    try {
      if (!href) return href;
      // Skip external or special links
      if (href.startsWith('http:') || href.startsWith('https:') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return href;
      if (href.startsWith('#')) return href;
      const params = new URLSearchParams(location.search);
      const ver = params.get('ver');
      if (!ver) return href;
      const u = new URL(href, location.href);
      if (u.origin !== location.origin) return href;
      u.searchParams.set('ver', ver);
      return u.pathname + u.search + u.hash;
    } catch (e) {
      return href;
    }
  }

  // Walk page links and persist `ver` for same-origin navigations.
  function persistVerOnLinks() {
    try {
      const params = new URLSearchParams(location.search);
      const ver = params.get('ver');
      if (!ver) return;
      document.querySelectorAll('a[href]').forEach(a => {
        const href = a.getAttribute('href');
        if (!href) return;
        if (href.startsWith('http:') || href.startsWith('https:') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return;
        if (href.startsWith('#')) return;
        try {
          const u = new URL(href, location.href);
          if (u.origin !== location.origin) return;
          u.searchParams.set('ver', ver);
          a.setAttribute('href', u.pathname + u.search + u.hash);
        } catch (e) { /* ignore */ }
      });
    } catch (e) { /* ignore */ }
  }

  try { populateVersionSelector(); } catch (e) { /* ignore */ }
});
