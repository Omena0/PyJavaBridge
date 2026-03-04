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
      } catch (e) {
        console.error('Failed to decompress search index:', e);
      }
      return true;
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
    const hits = [];
    for (const page of searchIndex) {
      // Title match
      if (page.title.toLowerCase().includes(q)) {
        hits.push({ url: page.url, title: page.title, text: '', score: 10 });
      }
      // Section matches
      for (const sec of page.sections) {
        if (sec.text.toLowerCase().includes(q) || sec.heading.toLowerCase().includes(q)) {
          hits.push({
            url: page.url + '#' + sec.heading.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''),
            title: page.title,
            heading: sec.heading,
            text: sec.text,
            score: sec.heading.toLowerCase().includes(q) ? 5 : 1,
          });
        }
      }
    }
    // Sort by score, dedupe by url
    hits.sort((a, b) => b.score - a.score);
    const seen = new Set();
    const unique = [];
    for (const h of hits) {
      // When heading equals title, collapse to the base page URL
      const baseUrl = h.url.split('#')[0];
      if (h.heading && h.heading === h.title) {
        h.heading = null;
        h.url = baseUrl;
      }
      const key = h.url;
      if (!seen.has(key) && unique.length < 12) {
        seen.add(key);
        // Also mark the base URL as seen so title+section don't both appear
        seen.add(baseUrl);
        unique.push(h);
      } else {
        // Merge: if existing entry has no text but this one does, update it
        const existing = unique.find(u => u.url.split('#')[0] === baseUrl);
        if (existing && !existing.text && h.text) {
          existing.text = h.text;
        }
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
      return `<a class="search-hit" href="${h.url}"><strong>${fmtTitle}</strong><span>${snippet}</span></a>`;
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
});
