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

  // ── Active sidebar link tracking ────────────────────────────
  const sections = document.querySelectorAll('.api-section, h2[id]');
  const allLinks = document.querySelectorAll('.sidebar-links a');
  if (sections.length && allLinks.length) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          allLinks.forEach(l => {
            l.classList.toggle('active', l.getAttribute('href') === '#' + id);
          });
        }
      });
    }, { rootMargin: '-80px 0px -60% 0px', threshold: 0 });
    sections.forEach(s => { if (s.id) observer.observe(s); });
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
});
