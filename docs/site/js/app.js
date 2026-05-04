/* ============================================================
   docs/site/js/app.js
   Documentation site JavaScript
   ============================================================ */

'use strict';

// ── Navigation ──────────────────────────────────────────────
const sidebar   = document.getElementById('sidebar');
const overlay   = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburgerBtn');

function openSidebar() {
  sidebar.classList.add('open');
  overlay.classList.add('visible');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('visible');
  document.body.style.overflow = '';
}

hamburger?.addEventListener('click', () => {
  sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
});

overlay?.addEventListener('click', closeSidebar);

// ── Section Routing ─────────────────────────────────────────
const sidebarLinks = document.querySelectorAll('.sidebar-link[data-section]');
const sections     = document.querySelectorAll('.doc-section');

function showSection(sectionId) {
  sections.forEach(s => s.classList.remove('active'));
  sidebarLinks.forEach(l => l.classList.remove('active'));

  const target = document.getElementById(sectionId);
  if (target) {
    target.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  sidebarLinks.forEach(l => {
    if (l.dataset.section === sectionId) l.classList.add('active');
  });

  history.pushState(null, '', `#${sectionId}`);
  if (window.innerWidth <= 768) closeSidebar();
  updateTOC(sectionId);
}

sidebarLinks.forEach(link => {
  link.addEventListener('click', () => showSection(link.dataset.section));
});

// Hero / callout internal links
document.addEventListener('click', e => {
  const trigger = e.target.closest('[data-goto]');
  if (trigger) {
    e.preventDefault();
    showSection(trigger.dataset.goto);
  }
});

// Handle hash on load
function loadFromHash() {
  const hash = location.hash.slice(1);
  const valid = hash && document.getElementById(hash);
  showSection(valid ? hash : 'home');
}

window.addEventListener('load', loadFromHash);
window.addEventListener('popstate', loadFromHash);

// ── Dark Mode ────────────────────────────────────────────────
const themeBtn = document.getElementById('themeBtn');
const html     = document.documentElement;

function applyTheme(theme) {
  html.dataset.theme = theme;
  localStorage.setItem('docs-theme', theme);
  if (themeBtn) themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

themeBtn?.addEventListener('click', () => {
  applyTheme(html.dataset.theme === 'dark' ? 'light' : 'dark');
});

// Auto-detect preference on first visit
const stored = localStorage.getItem('docs-theme');
if (stored) {
  applyTheme(stored);
} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  applyTheme('dark');
}

// ── Search ───────────────────────────────────────────────────
const searchInput   = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');

// Build a flat index from page content
const searchIndex = [
  { section: 'home',      title: 'Overview',                keywords: 'home overview introduction what is exam marks extractor obe' },
  { section: 'home',      title: 'Tech Stack',              keywords: 'flask python javascript html css supabase postgresql gpt openai' },
  { section: 'home',      title: 'Key Features',            keywords: 'features ocr upload excel export admin panel history' },
  { section: 'quickstart',title: 'Quick Start',             keywords: 'getting started quick start setup begin first time' },
  { section: 'quickstart',title: 'Sign Up',                 keywords: 'signup register account teacher create' },
  { section: 'quickstart',title: 'Admin Approval',          keywords: 'admin approval pending approved status' },
  { section: 'user-guide',title: 'User Guide',              keywords: 'user guide teacher workflow exam marks' },
  { section: 'user-guide',title: 'Create Exam',             keywords: 'create exam setup questions clo subject code' },
  { section: 'user-guide',title: 'Upload Exam Sheet',       keywords: 'upload image ocr scan extract marks' },
  { section: 'user-guide',title: 'Manual Entry',            keywords: 'manual entry edit marks correct verify' },
  { section: 'user-guide',title: 'Export Excel',            keywords: 'export excel download spreadsheet results' },
  { section: 'api',       title: 'API Reference',           keywords: 'api rest endpoints http json' },
  { section: 'api',       title: 'Authentication',          keywords: 'auth login signup jwt token bearer' },
  { section: 'api',       title: 'POST /auth/login',        keywords: 'login endpoint jwt token authentication' },
  { section: 'api',       title: 'POST /auth/signup',       keywords: 'signup register endpoint' },
  { section: 'api',       title: 'POST /api/upload',        keywords: 'upload ocr extract marks image endpoint' },
  { section: 'api',       title: 'Error Codes',             keywords: 'error 400 401 403 404 500 codes http status' },
  { section: 'dev',       title: 'Developer Guide',         keywords: 'developer local setup installation environment' },
  { section: 'dev',       title: 'Environment Variables',   keywords: 'env environment variables .env OPENAI_API_KEY SUPABASE' },
  { section: 'dev',       title: 'Local Development',       keywords: 'local dev run start flask python venv' },
  { section: 'dev',       title: 'Code Structure',          keywords: 'code structure files modules app.py database.py' },
  { section: 'ocr',       title: 'OCR Guide',               keywords: 'ocr gpt4 vision exam sheet image quality' },
  { section: 'ocr',       title: 'Exam Sheet Format',       keywords: 'format table layout marks row question headers' },
  { section: 'ocr',       title: 'Confidence Scores',       keywords: 'confidence score low high percentage accuracy' },
  { section: 'ocr',       title: 'Common Failures',         keywords: 'failures errors handwriting faint blur erasure' },
];

function highlight(text, query) {
  if (!query) return text;
  const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(re, '<mark>$1</mark>');
}

const SECTION_LABELS = {
  'home':       'Home',
  'quickstart': 'Quick Start',
  'user-guide': 'User Guide',
  'api':        'API Reference',
  'dev':        'Developer Guide',
  'ocr':        'OCR Guide',
};

function runSearch(query) {
  if (!query.trim()) {
    searchResults.classList.add('hidden');
    return;
  }

  const q = query.toLowerCase();
  const matches = searchIndex.filter(item =>
    item.title.toLowerCase().includes(q) ||
    item.keywords.toLowerCase().includes(q)
  ).slice(0, 8);

  if (!matches.length) {
    searchResults.innerHTML = `<div class="search-empty">No results for "<strong>${query}</strong>"</div>`;
    searchResults.classList.remove('hidden');
    return;
  }

  searchResults.innerHTML = matches.map(item => `
    <div class="search-result-item" data-goto="${item.section}">
      <span class="search-result-icon">📄</span>
      <div class="search-result-text">
        <div class="search-result-title">${highlight(item.title, query)}</div>
        <div class="search-result-section">${SECTION_LABELS[item.section] || item.section}</div>
      </div>
    </div>
  `).join('');

  searchResults.classList.remove('hidden');
}

searchInput?.addEventListener('input', e => runSearch(e.target.value));

searchInput?.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    searchResults.classList.add('hidden');
    searchInput.blur();
  }
});

document.addEventListener('click', e => {
  if (!e.target.closest('.header-search')) {
    searchResults?.classList.add('hidden');
  }
});

// Keyboard shortcut: / to focus search
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault();
    searchInput?.focus();
  }
});

// ── Endpoint Toggles ─────────────────────────────────────────
document.addEventListener('click', e => {
  const header = e.target.closest('.endpoint-header');
  if (header) {
    const endpoint = header.closest('.endpoint');
    endpoint.classList.toggle('open');
  }
});

// ── Response Tabs ────────────────────────────────────────────
document.addEventListener('click', e => {
  const tab = e.target.closest('.res-tab');
  if (!tab) return;
  const parent = tab.closest('.endpoint-body');
  parent.querySelectorAll('.res-tab').forEach(t => t.classList.remove('active'));
  parent.querySelectorAll('.res-panel').forEach(p => p.classList.remove('active'));
  tab.classList.add('active');
  const panel = parent.querySelector(`[data-panel="${tab.dataset.tab}"]`);
  if (panel) panel.classList.add('active');
});

// ── Copy-to-Clipboard ────────────────────────────────────────
document.addEventListener('click', e => {
  const btn = e.target.closest('.copy-btn');
  if (!btn) return;
  const pre = btn.closest('.code-block').querySelector('code');
  if (!pre) return;
  navigator.clipboard.writeText(pre.textContent).then(() => {
    btn.textContent = '✓ Copied';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
});

// ── Table of Contents ────────────────────────────────────────
function updateTOC(sectionId) {
  const toc = document.getElementById('toc');
  if (!toc) return;

  const section = document.getElementById(sectionId);
  if (!section) return;

  const headings = section.querySelectorAll('h2, h3');
  if (!headings.length) {
    toc.innerHTML = '';
    return;
  }

  const items = Array.from(headings).map(h => {
    if (!h.id) h.id = h.textContent.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
    return `<li class="toc-item"><a href="#${h.id}">${h.textContent}</a></li>`;
  }).join('');

  toc.innerHTML = `
    <div class="toc-label">On this page</div>
    <ul class="toc-list">${items}</ul>
  `;

  // Highlight active heading on scroll
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        toc.querySelectorAll('.toc-item').forEach(item => item.classList.remove('active'));
        const active = toc.querySelector(`a[href="#${entry.target.id}"]`);
        active?.closest('.toc-item')?.classList.add('active');
      }
    });
  }, { rootMargin: '-60px 0px -80% 0px' });

  headings.forEach(h => observer.observe(h));
}

// ── Confidence bar animation ─────────────────────────────────
function animateConfidenceBars() {
  document.querySelectorAll('.confidence-fill[data-width]').forEach(bar => {
    setTimeout(() => {
      bar.style.width = bar.dataset.width;
    }, 200);
  });
}

// Animate bars when OCR section becomes visible
const mutObserver = new MutationObserver(() => {
  const ocr = document.getElementById('ocr');
  if (ocr?.classList.contains('active')) animateConfidenceBars();
});

const ocrSection = document.getElementById('ocr');
if (ocrSection) {
  mutObserver.observe(ocrSection, { attributes: true, attributeFilter: ['class'] });
}
