#!/usr/bin/env python3
"""
Build script for PyJavaBridge documentation.
Converts Markdown source files in docs/src/ into a static HTML site in docs/.

Requirements: pip install markdown
Usage: python docs/build.py
"""
import os
import re
import sys

try:
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.toc import TocExtension
except ImportError:
    print("Installing markdown library...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.toc import TocExtension

# ── Paths ────────────────────────────────────────────────────────────────────

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(DOCS_DIR, "src")
OUT_DIR = os.path.join(DOCS_DIR, "site")

# ── Sidebar definition (order matters) ──────────────────────────────────────

SIDEBAR = [
    ("Getting Started", [
        ("index", "Home"),
        ("decorators", "Decorators"),
        ("exceptions", "Exceptions"),
        ("examples", "Examples"),
    ]),
    ("Core", [
        ("server", "Server"),
        ("event", "Event"),
        ("entity", "Entity"),
        ("player", "Player"),
    ]),
    ("World & Space", [
        ("world", "World"),
        ("location", "Location"),
        ("block", "Block"),
        ("chunk", "Chunk"),
        ("vector", "Vector"),
    ]),
    ("Items & Inventory", [
        ("item", "Item"),
        ("itembuilder", "ItemBuilder"),
        ("inventory", "Inventory"),
        ("menu", "Menu"),
    ]),
    ("Effects & Attributes", [
        ("effect", "Effect"),
        ("potion", "Potion"),
        ("attribute", "Attribute"),
        ("advancement", "Advancement"),
    ]),
    ("Scoreboards & UI", [
        ("bossbar", "BossBar"),
        ("scoreboard", "Scoreboard"),
        ("objective", "Objective"),
        ("team", "Team"),
        ("sidebar", "Sidebar"),
    ]),
    ("Helpers", [
        ("config", "Config"),
        ("cooldown", "Cooldown"),
        ("hologram", "Hologram"),
        ("enumvalue", "EnumValue"),
        ("enums", "Enums"),
    ]),
    ("Display Entities", [
        ("actionbardisplay", "ActionBarDisplay"),
        ("bossbardisplay", "BossBarDisplay"),
        ("blockdisplay", "BlockDisplay"),
        ("itemdisplay", "ItemDisplay"),
        ("imagedisplay", "ImageDisplay"),
    ]),
    ("Utilities", [
        ("raycast", "Raycast"),
        ("chat", "Chat"),
        ("reflect", "Reflect"),
    ]),
]

# ── Frontmatter parser ──────────────────────────────────────────────────────

def parse_frontmatter(text):
    """Extract YAML-like frontmatter and return (metadata_dict, remaining_text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 3:].strip()
    meta = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, body

# ── Syntax highlighter (simple Python-aware) ────────────────────────────────

PYTHON_KEYWORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield',
}

def highlight_python(code):
    """Python syntax highlighter using single-pass tokenization.

    Input is already HTML-escaped by the markdown library, so we must NOT
    escape again.  A single combined regex ensures that once a token is
    matched (e.g. a string containing the word 'class'), later patterns
    cannot corrupt it by matching inside the replacement HTML.
    """
    token_specs = [
        # Order matters – earlier patterns take priority
        ('st', r'&quot;&quot;&quot;.*?&quot;&quot;&quot;|&#x27;&#x27;&#x27;.*?&#x27;&#x27;&#x27;'),
        ('st', r'f?&quot;(?:[^&]|&(?!quot;))*?&quot;|f?&#x27;(?:[^&]|&(?!#x27;))*?&#x27;'),
        ('cm', r'#[^\n]*'),
        ('dc', r'@\w+'),
        ('nb', r'\b\d+\.?\d*\b'),
        ('kw', r'\b(?:' + '|'.join(sorted(PYTHON_KEYWORDS, key=len, reverse=True)) + r')\b'),
    ]
    combined = '|'.join(
        f'(?P<g{i}>{pat})' for i, (_, pat) in enumerate(token_specs)
    )
    classes = [cls for cls, _ in token_specs]

    def _replacer(m):
        for i, cls in enumerate(classes):
            if m.group(f'g{i}') is not None:
                return f'<span class="{cls}">{m.group(f"g{i}")}</span>'
        return m.group(0)

    return re.sub(combined, _replacer, code, flags=re.DOTALL)


def highlight_code_blocks(html_text):
    """Find <pre><code class="language-python"> blocks and apply highlighting."""
    def replace_block(m):
        lang = m.group(1) or ""
        inner = m.group(2)
        if "python" in lang or "py" in lang:
            inner = highlight_python(inner)
        return f'<pre><code class="language-{lang}">{inner}</code></pre>'

    html_text = re.sub(
        r'<pre><code class="language-(\w*)">(.*?)</code></pre>',
        replace_block, html_text, flags=re.DOTALL
    )
    # Also handle bare <pre><code> blocks (no language) — don't highlight
    return html_text

# ── Markdown → HTML conversion ──────────────────────────────────────────────

def convert_markdown(text):
    """Convert markdown text to HTML with extensions."""
    md = markdown.Markdown(extensions=[
        FencedCodeExtension(),
        TableExtension(),
        TocExtension(permalink=False, toc_depth="2-3"),
    ])
    html = md.convert(text)
    toc_tokens = md.toc_tokens
    md.reset()
    return html, toc_tokens


def rewrite_md_links(html_text):
    """Rewrite .md links to .html links."""
    return re.sub(r'href="([^"#]+)\.md(#[^"]*)?"', lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', html_text)


def process_blockquotes(html_text):
    """Convert blockquotes starting with bold markers into styled callouts."""
    def classify(m):
        content = m.group(1)
        if content.strip().startswith("<strong>Warning"):
            cls = "callout callout-warn"
        elif content.strip().startswith("<strong>Tip"):
            cls = "callout callout-tip"
        elif content.strip().startswith("<strong>Note"):
            cls = "callout callout-info"
        elif content.strip().startswith("<strong>See also"):
            cls = "callout callout-info"
        else:
            cls = "callout callout-info"
        return f'<div class="{cls}">{content}</div>'
    return re.sub(r'<blockquote>\s*(.*?)\s*</blockquote>', classify, html_text, flags=re.DOTALL)


# ── HTML template ────────────────────────────────────────────────────────────

def _section_key(name):
    """Turn a section name into a compact localStorage key."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def build_sidebar_html(current_slug):
    """Generate the sidebar HTML."""
    parts = [
        '<div class="search-box">',
        '  <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
        '  <input type="text" id="sidebar-search" placeholder="Search docs…">',
        '</div>',
    ]

    for section_name, pages in SIDEBAR:
        key = _section_key(section_name)
        # Collapsed by default
        parts.extend(
            (
                '<div class="sidebar-section">',
                f'  <div class="sidebar-heading collapsed" data-section="{key}">{section_name}</div>',
                '  <ul class="sidebar-links">',
            )
        )
        for slug, label in pages:
            active = ' class="active"' if slug == current_slug else ''
            href = "index.html" if slug == "index" else f"{slug}.html"
            parts.append(f'    <li><a href="{href}"{active}>{label}</a></li>')

        parts.extend(('  </ul>', '</div>'))
    return "\n".join(parts)


def build_toc_sidebar(toc_tokens, current_slug):
    """Build the sidebar with 'On This Page' TOC at the top, then nav sections."""
    nav = build_sidebar_html(current_slug)
    if not toc_tokens:
        return nav

    # Build the TOC block (always expanded, inserted before nav links)
    toc_parts = [
        '<div class="sidebar-section">',
        '  <div class="sidebar-heading" data-section="on-this-page">On This Page</div>',
        '  <ul class="sidebar-links">',
    ]
    for token in toc_tokens:
        toc_parts.append(f'    <li><a href="#{token["id"]}">{token["name"]}</a></li>')
        toc_parts.extend(
            f'    <li><a href="#{child["id"]}" style="padding-left:40px;font-size:.8rem">{child["name"]}</a></li>'
            for child in token.get("children", [])
        )
    toc_parts.extend(('  </ul>', '</div>'))

    # Insert TOC right after the search box (first </div>)
    search_end = nav.find('</div>') + len('</div>')
    return nav[:search_end] + '\n' + '\n'.join(toc_parts) + '\n' + nav[search_end:]


TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — PyJavaBridge</title>
  <meta property="og:title" content="{title} — PyJavaBridge">
  <meta property="og:description" content="{og_description}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="PyJavaBridge Docs">
  <meta name="theme-color" content="#6366f1">
  <meta name="color-scheme" content="dark">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <!-- Header -->
  <header class="site-header">
    <button class="menu-toggle" aria-label="Toggle menu">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 12h18M3 6h18M3 18h18"/>
      </svg>
    </button>
    <a href="index.html" class="header-brand">
      <span class="logo">Py</span>
      PyJavaBridge
    </a>
    <nav class="header-nav">
      <a href="index.html">Docs</a>
      <a href="examples.html">Examples</a>
      <a href="https://github.com/Omena0/PyJavaBridge">GitHub</a>
    </nav>
  </header>

  <!-- Sidebar -->
  <aside class="sidebar">
{sidebar}
  </aside>
  <div class="sidebar-overlay"></div>

  <!-- Main -->
  <main class="main">
    <div class="content">
      {subtitle_html}
      {body}
    </div>
    <footer class="site-footer">
      &copy; Omena0 2026 &middot; PyJavaBridge Documentation
    </footer>
  </main>

  <!-- Back to top -->
  <button class="back-to-top" aria-label="Back to top">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M18 15l-6-6-6 6"/>
    </svg>
  </button>

  <script src="script.js"></script>
</body>
</html>
"""

# ── Builder ──────────────────────────────────────────────────────────────────

def build_page(slug):
    """Build a single page from its markdown source."""
    src_path = os.path.join(SRC_DIR, f"{slug}.md")
    if not os.path.exists(src_path):
        print(f"  ⚠ Skipping {slug}.md (not found)")
        return

    with open(src_path, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body_md = parse_frontmatter(raw)
    title = meta.get("title", slug.capitalize())
    subtitle = meta.get("subtitle", "")

    # Convert markdown to HTML
    body_html, toc_tokens = convert_markdown(body_md)

    # Post-processing
    body_html = rewrite_md_links(body_html)
    body_html = highlight_code_blocks(body_html)
    body_html = process_blockquotes(body_html)

    # Build subtitle HTML
    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""

    # Build sidebar
    sidebar = build_toc_sidebar(toc_tokens, slug)

    # Build OG description from subtitle or first paragraph
    og_description = subtitle if subtitle else f"{title} — PyJavaBridge documentation"

    # Render template
    out_html = TEMPLATE.format(
        title=title,
        og_description=og_description,
        subtitle_html=subtitle_html,
        body=body_html,
        sidebar=sidebar,
    )

    out_name = "index.html" if slug == "index" else f"{slug}.html"
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)


def get_all_slugs():
    """Get all markdown file slugs from the sidebar definition."""
    slugs = []
    for _, pages in SIDEBAR:
        slugs.extend(slug for slug, _ in pages)
    return slugs


def main():
    print("📖 Building PyJavaBridge docs...")
    print(f"   Source: {SRC_DIR}")
    print(f"   Output: {OUT_DIR}")
    print()

    slugs = get_all_slugs()

    # Also check for any .md files not in the sidebar
    if os.path.isdir(SRC_DIR):
        for fname in os.listdir(SRC_DIR):
            if fname.endswith(".md"):
                s = fname[:-3]
                if s not in slugs:
                    slugs.append(s)

    built = 0
    for slug in slugs:
        src = os.path.join(SRC_DIR, f"{slug}.md")
        if os.path.exists(src):
            build_page(slug)
            print(f"  ✓ {slug}.html")
            built += 1

    print(f"\n✅ Built {built} pages")


if __name__ == "__main__":
    main()
