#!/usr/bin/env python3
"""
Build script for PyJavaBridge documentation.
Converts Markdown source files in docs/src/ into a static HTML site in docs/.

Requirements: pip install markdown zstandard
Usage: python docs/build.py
"""

import concurrent.futures
from pathlib import Path
import subprocess
import tempfile
import base64
import shutil
import html
import os
import re
import threading

try: # Import markdown
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension
except ImportError:
    print('Please install markdown')
    exit(1)

try: import zstandard
except ImportError:
    print('Please install zstandard')
    exit(1)

# ── Paths ────────────────────────────────────────────────────────────────────
DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(DOCS_DIR, "src")
OUT_DIR = os.path.join(DOCS_DIR, "site")

# Minify built HTML using `html-minifier-next` (via `npx`).
# Set `MINIFY_HTML = False` to disable. If `npx` or the package is
# unavailable the builder will fall back to a lightweight Python minifier.
MINIFY_HTML = True
HTML_MINIFIER_ARGS = [
    "--minify-css",
    "--minify-js",
    "--minify-svg",
    "--minify-urls",
    "--remove-attribute-quotes",
    "--collapse-whitespace",
    "--remove-tag-whitespace",
]

# ── Sidebar definition (order matters) ──────────────────────────────────────
SIDEBAR = [
    ("Getting Started", [
        ("getting_started/index", "Home"),
        ("getting_started/decorators", "Decorators"),
        ("getting_started/exceptions", "Exceptions"),
        ("getting_started/examples", "Examples"),
    ]),
    ("Core", [
        ("core/server", "Server"),
        ("core/event", "Event"),
        ("core/entity", "Entity"),
        ("core/entitysubtypes", "Entity Subtypes"),
        ("core/player", "Player"),
    ]),
    ("World & Space", [
        ("world/world", "World"),
        ("world/location", "Location"),
        ("world/block", "Block"),
        ("world/blocksnapshot", "BlockSnapshot"),
        ("world/chunk", "Chunk"),
        ("world/vector", "Vector"),
    ]),
    ("Items & Inventory", [
        ("items/item", "Item"),
        ("items/itembuilder", "ItemBuilder"),
        ("items/inventory", "Inventory"),
        ("items/recipe", "Recipe"),
    ]),
    ("Effects & Attributes", [
        ("effects/effect", "Effect"),
        ("effects/potion", "Potion"),
        ("effects/attribute", "Attribute"),
        ("effects/advancement", "Advancement"),
        ("effects/firework", "Firework"),
        ("effects/textcomponent", "TextComponent"),
        ("effects/bookbuilder", "BookBuilder"),
    ]),
    ("Scoreboards & UI", [
        ("ui/menu", "Menu"),
        ("ui/menuitem", "MenuItem"),
        ("ui/sidebar", "Sidebar"),
        ("ui/actionbardisplay", "ActionBarDisplay"),
        ("ui/bossbardisplay", "BossBarDisplay"),
        ("ui/bossbar", "BossBar"),
        ("ui/scoreboard", "Scoreboard"),
        ("ui/objective", "Objective"),
        ("ui/team", "Team"),
    ]),
    ("Helpers", [
        ("helpers/npc", "NPC"),
        ("helpers/config", "Config"),
        ("helpers/state", "State"),
        ("helpers/cooldown", "Cooldown"),
        ("helpers/paginator", "Paginator"),
        ("helpers/enums", "Enums"),
        ("helpers/enumvalue", "EnumValue"),
    ]),
    ("Display Entities", [
        ("display/hologram", "Hologram"),
        ("display/blockdisplay", "BlockDisplay"),
        ("display/itemdisplay", "ItemDisplay"),
    ]),
    ("Extensions", [
        ("extensions/imagedisplay", "ImageDisplay"),
        ("extensions/meshdisplay", "MeshDisplay"),
        ("extensions/quest", "Quest"),
        ("extensions/dialog", "Dialog"),
        ("extensions/bank", "Bank"),
        ("extensions/shop", "Shop"),
        ("extensions/trade", "TradeWindow"),
        ("extensions/ability", "Ability"),
        ("extensions/mana", "ManaStore"),
        ("extensions/combat", "CombatSystem"),
        ("extensions/levels", "LevelSystem"),
        ("extensions/region", "Region"),
        ("extensions/party", "Party"),
        ("extensions/guild", "Guild"),
        ("extensions/customitem", "CustomItem"),
        ("extensions/leaderboard", "Leaderboard"),
        ("extensions/visualeffect", "VisualEffect"),
        ("extensions/playerdatastore", "PlayerDataStore"),
        ("extensions/dungeon", "Dungeon"),
        ("extensions/tablist", "TabList"),
        ("extensions/statemachine", "StateMachine"),
        ("extensions/scheduler", "Scheduler"),
        ("extensions/placeholder", "Placeholder"),
        ("extensions/loottable", "LootTable"),
        ("extensions/clientmod", "ClientMod"),
    ]),
    ("Utilities", [
        ("utilities/raycast", "Raycast"),
        ("utilities/chat", "Chat"),
        ("utilities/reflect", "Reflect"),
    ]),
    ("Internals", [
        ("internals/bridge", "Bridge"),
        ("internals/events_internal", "Events"),
        ("internals/execution", "Execution"),
        ("internals/serialization", "Serialization"),
        ("internals/lifecycle", "Lifecycle"),
        ("internals/debugging", "Debugging")
    ]),
]


def slug_basename(slug):
    """Extract the filename part from a possibly prefixed slug (e.g. 'core/entity' → 'entity')."""
    return slug.rsplit("/", 1)[-1]


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

# Precompile highlight regexes for speed
TOKEN_SPECS = [
    ('st', r'&quot;&quot;&quot;.*?&quot;&quot;&quot;|&#x27;&#x27;&#x27;.*?&#x27;&#x27;&#x27;'),
    ('st', r'f?&quot;(?:[^&]|&(?!quot;))*?&quot;|f?&#x27;(?:[^&]|&(?!#x27;))*?&#x27;'),
    ('cm', r'#[^\n]*'),
    ('dc', r'@\w+'),
    ('nb', r'\b\d+\.?\d*\b'),
    ('kw', r'\b(?:' + '|'.join(sorted(PYTHON_KEYWORDS, key=len, reverse=True)) + r')\b'),
]

HIGHLIGHT_CLASSES = [cls for cls, _ in TOKEN_SPECS]
HIGHLIGHT_PATTERN = '|'.join(f'(?P<g{i}>{pat})' for i, (_, pat) in enumerate(TOKEN_SPECS))
HIGHLIGHT_RE = re.compile(HIGHLIGHT_PATTERN, flags=re.DOTALL)

# Precompiled pre/code block matcher
PRE_CODE_RE = re.compile(r'<pre><code class="language-(\w*)">(.*?)</code></pre>', flags=re.DOTALL)


def highlight_python(code):
    """Highlight Python-like tokens using the precompiled regex."""
    def _replacer(m):
        for i, cls in enumerate(HIGHLIGHT_CLASSES):
            if m.group(f'g{i}') is not None:
                return f'<span class="{cls}">{m.group(f"g{i}")}</span>'
        return m.group(0)

    return HIGHLIGHT_RE.sub(_replacer, code)


def highlight_code_blocks(html_text):
    """Apply highlighting to <pre><code class="language-..."> blocks."""
    def replace_block(m):
        lang = m.group(1) or ""
        inner = m.group(2)
        if "python" in lang or "py" in lang:
            inner = highlight_python(inner)
        return f'<pre><code class="language-{lang}">{inner}</code></pre>'

    return PRE_CODE_RE.sub(replace_block, html_text)


# ── Markdown → HTML conversion ──────────────────────────────────────────────
# Use a per-thread Markdown instance to avoid cross-thread state corruption
_MD_LOCAL = threading.local()

def _make_md():
    return markdown.Markdown(extensions=[
        FencedCodeExtension(),
        TableExtension(),
    ])


def convert_markdown(text):
    """Convert markdown text to HTML using a per-thread Markdown instance."""
    md = getattr(_MD_LOCAL, 'md', None)
    if md is None:
        md = _make_md()
        _MD_LOCAL.md = md

    md.reset()
    html_out = md.convert(text)
    toc_tokens = getattr(md, 'toc_tokens', [])
    md.reset()
    return html_out, toc_tokens

def rewrite_md_links(html_text):
    """Rewrite .md links to .html links."""
    return re.sub(r'href="([^"#]+)\.md(#[^"]*)?"', lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', html_text)

def process_blockquotes(html_text):
    """Convert blockquotes starting with bold markers into styled callouts."""
    def classify(m):
        """Classify a blockquote as a callout based on its leading marker."""
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


# ── Tag formatting ───────────────────────────────────────────────────────────
def format_ext_tags(html_text):
    """Replace [ext] with a styled badge span."""
    return html_text.replace('[ext]', '<span class="ext-tag">ext</span>')


# ── Auto-linking for class references in Markdown -------------------------
def auto_link_markdown(md_text, search_map):
    """Auto-link plain class names in Markdown to their docs using search_map.

    - Avoids touching fenced code blocks, inline code, and existing Markdown links.
    - search_map maps a title (e.g. 'Player') -> destination markdown filename (e.g. 'player.md').
    """
    if not search_map:
        return md_text

    # Protect fenced code blocks (```...```)
    code_fence_pat = re.compile(r'```[\s\S]*?```')
    code_fences = []

    def _cf(m):
        code_fences.append(m.group(0))
        return f"@@CODEFENCE{len(code_fences)-1}@@"

    text = code_fence_pat.sub(_cf, md_text)

    # Protect inline code (`...`) but capture inner content for later processing
    inline_code_pat = re.compile(r'`([^`]*?)`')
    inline_codes = []

    def _ic(m):
        # store inner content (without backticks)
        inline_codes.append(m.group(1))
        return f"@@INLINECODE{len(inline_codes)-1}@@"

    text = inline_code_pat.sub(_ic, text)

    # Protect existing markdown links [label](dest)
    link_pat = re.compile(r'\[[^\]]+\]\([^\)]+\)')
    links = []

    def _ln(m):
        links.append(m.group(0))
        return f"@@LINK{len(links)-1}@@"

    text = link_pat.sub(_ln, text)

    # Only replace type names inside inline code spans (backticks).
    def _transform_inline_content(content):
        esc = html.escape(content)
        # Use a precompiled combined regex when available for speed
        if 'SEARCH_RE' in globals() and SEARCH_RE:
            def _linker(m):
                k = m.group(1)
                dest = search_map.get(k)
                return f'<a href="{dest}">{k}</a>' if dest else k

            esc = SEARCH_RE.sub(_linker, esc)
        else:
            for name in sorted(search_map.keys(), key=len, reverse=True):
                dest = search_map[name]
                pattern = r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])'
                esc = re.sub(pattern, f'<a href="{dest}">{name}</a>', esc)

        # Link decorator tokens like @event/@command to the decorators doc
        decorators_dest = DECORATORS_DEST if 'DECORATORS_DEST' in globals() else (search_map.get('Decorators', 'decorators.md') if search_map else 'decorators.md')

        def _decor_replace(m):
            nm = m.group(1)
            # anchor uses the plain name (markdown slugs drop the leading @)
            return f'<a href="{decorators_dest}#{nm}">@{nm}</a>'

        esc = re.sub(r'@([A-Za-z_][A-Za-z0-9_]*)', _decor_replace, esc)

        # Prevent Markdown from interpreting square brackets when raw HTML is mixed
        esc = esc.replace('[', '&#91;').replace(']', '&#93;')

        return f'<code>{esc}</code>'

    transformed_inlines = [_transform_inline_content(c) for c in inline_codes]

    # Restore existing markdown links
    def _restore_link(m):
        return links[int(m.group(1))]

    text = re.sub(r'@@LINK(\d+)@@', _restore_link, text)

    # Restore inline code placeholders with transformed HTML
    def _restore_inline(m):
        return transformed_inlines[int(m.group(1))]

    text = re.sub(r'@@INLINECODE(\d+)@@', _restore_inline, text)

    # Finally restore fenced code blocks
    text = re.sub(r'@@CODEFENCE(\d+)@@', lambda m: code_fences[int(m.group(1))], text)

    return text


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
        is_ext = section_name == "Extensions"
        for slug, label in pages:
            base = slug_basename(slug)
            active = ' class="active"' if slug == current_slug else ''
            href = "index.html" if base == "index" else f"{base}.html"
            display = f'{label} <span class="ext-tag">ext</span>' if is_ext else label
            parts.append(f'    <li><a href="{href}"{active}>{display}</a></li>')

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
        children = token.get("children", [])
        if children:
            toc_parts.append(f'    <li><ul class="toc-sub" data-parent="{token["id"]}">')
            toc_parts.extend(
                f'      <li><a href="#{child["id"]}">{child["name"]}</a></li>'
                for child in children
            )
            toc_parts.append('    </ul></li>')

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
  <title>{page_title} — PyJavaBridge</title>
  <meta property="og:title" content="{og_title} — PyJavaBridge">
  <meta property="og:description" content="{og_description}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="PyJavaBridge Docs">
  <meta name="theme-color" content="#6366f1">
  <meta name="color-scheme" content="dark">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,400..800&family=JetBrains+Mono:wght@400..700&display=swap" rel="stylesheet">
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
        <div class="header-brand-row">
            <a href="index.html" class="header-brand">
                <span class="logo">Py</span>
                PyJavaBridge

            </a>
            <div class="version-selector-wrap">
                <select id="version-selector" class="version-selector" aria-label="Select version">
                    {version_options}
                </select>
            </div>
        </div>
    <div class="header-search">
      <svg class="header-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="text" id="header-search" placeholder="Search docs… (Ctrl+K)" autocomplete="off">
      <div id="search-results" class="search-results"></div>

    </div>
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

    <script id="git-meta" type="application/json">{git_meta_json}</script>
    <script id="zstd-data" type="text/plain">{search_index_zstd_b64}</script>
    <script src="https://cdn.jsdelivr.net/npm/fzstd@0.1.1/umd/index.js" async></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
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
    page_title = meta.get("page_title", title).replace("[ext]", "").strip()
    og_title = meta.get("og_title", title).replace("[ext]", "").strip()

    # Auto-link class references in Markdown using the search map
    try:
        if SEARCH_MAP:
            body_md = auto_link_markdown(body_md, SEARCH_MAP)
    except Exception:
        # Fail-safe: if auto-linking errors, continue without it
        pass

    # Convert markdown to HTML
    body_html, toc_tokens = convert_markdown(body_md)

    # Post-processing
    body_html = rewrite_md_links(body_html)
    body_html = highlight_code_blocks(body_html)
    body_html = process_blockquotes(body_html)
    body_html = format_ext_tags(body_html)

    # Build subtitle HTML
    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""

    # Build sidebar
    sidebar = build_toc_sidebar(toc_tokens, slug)

    # Build OG description from subtitle or first paragraph
    og_description = subtitle or f"{title} — PyJavaBridge documentation"

    # Render template
    # Escape braces in injected HTML to avoid accidental format placeholders
    def _safe(s):
        return s.replace('{', '{{').replace('}', '}}') if isinstance(s, str) else s

    out_html = TEMPLATE.format(
        title=title,
        page_title=page_title,
        og_title=og_title,
        og_description=og_description,
        subtitle_html=_safe(subtitle_html),
        body=_safe(body_html),
        sidebar=_safe(sidebar),
        search_index_zstd_b64=_safe(_search_index_zstd_b64),
        version_options=_safe(VERSION_OPTIONS),
        git_meta_json=_git_meta_json,
    )

    # Optimize the html
    try:
        out_html = optimize_html(out_html)
    except Exception as e:
        print(f'Failed to optimize HTML: {e}')

    # Minify the html
    try:
        out_html = minify_html(out_html)
    except Exception as e:
        print(f'Failed to minify HTML: {e}')

    out_name = "index.html" if slug_basename(slug) == "index" else f"{slug_basename(slug)}.html"
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)

OPTIMIZE = True
MINIFY   = True
def optimize_html(html_input, base_path=None):
    """
    Runs Critical safely using temp input file + captured stdout.
    base_path: directory where CSS/assets are located; defaults to the output dir.
    """
    if not OPTIMIZE:
        return html_input

    # Write input HTML to temp file
    with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False) as f_in:
        f_in.write(html_input)
        in_path = Path(f_in.name)

    # Resolve base path: prefer explicit, otherwise use output dir which already
    # contains copied assets (style.css, etc.). If a relative path was given,
    # treat it as relative to DOCS_DIR.
    if base_path is None:
        base_path = OUT_DIR
    elif not os.path.isabs(base_path):
        base_path = os.path.join(DOCS_DIR, base_path)

    cmd = [
        "npx", "critical",
        str(in_path),
        "--base", str(base_path),
        "--inline",
        "--extract",
        "--width", "1920",
        "--height", "1080",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    try:
        if result.returncode != 0:
            raise RuntimeError(f"Critical failed:\n{result.stderr}")

        optimized_html = result.stdout

        # sanity check (VERY important)
        if "</html>" not in optimized_html:
            raise RuntimeError("Critical output looks truncated/corrupted")

        return optimized_html

    finally:
        try:
            in_path.unlink()
        except:
            pass

def minify_html(html_input):
    if not MINIFY:
        return html_input

    with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False) as temp_in:
        temp_in.write(html_input)
        temp_in_path = Path(temp_in.name)

    with tempfile.NamedTemporaryFile("r+", suffix=".html", delete=False) as temp_out:
        temp_out_path = Path(temp_out.name)

    cmd = [
        "npx", "html-minifier-next",
        "--minify-css", "true",
        "--minify-js", "true",
        "--minify-svg", "true",
        "--minify-urls", "true",
        "--remove-attribute-quotes",
        "--collapse-whitespace",
        "--remove-tag-whitespace",
        "--remove-comments",
        "-o", str(temp_out_path),
        str(temp_in_path)
    ]

    subprocess.run(cmd, check=True)

    # Read back minified HTML
    minified_html = temp_out_path.read_text(encoding="utf-8")

    # Clean up temp files
    temp_in_path.unlink()
    temp_out_path.unlink()

    return minified_html

def get_all_slugs():
    """Get all markdown file slugs from the sidebar definition."""
    slugs = []
    for _, pages in SIDEBAR:
        slugs.extend(slug for slug, _ in pages)

    return slugs

_search_index_zstd_b64 = ""
SEARCH_MAP = {}
VERSION_OPTIONS = ""
_git_meta_json = '{}'

WORKERS = 18

def main():
    """Build the static documentation site from markdown sources."""
    global _search_index_zstd_b64
    print("📖 Building PyJavaBridge docs...")
    print(f"   Source: {SRC_DIR}")
    print(f"   Output: {OUT_DIR}")
    print()

    # Copy static assets into output directory. Try DOCS_DIR first, fall back
    # to DOCS_DIR/site if assets are colocated there.
    for name in ('favicon.svg', 'script.js', 'style.css'):
        src = os.path.join(DOCS_DIR, name)
        dst = os.path.join(OUT_DIR, name)

        try:
            shutil.copyfile(src, dst)
        except Exception:
            print(f"   ⚠ Could not copy {name} (source {src} missing)")

    slugs = get_all_slugs()

    # Also check for any .md files not in the sidebar
    if os.path.isdir(SRC_DIR):
        for dirpath, _dirnames, filenames in os.walk(SRC_DIR):
            for fname in filenames:
                if fname.endswith(".md"):
                    rel = os.path.relpath(os.path.join(dirpath, fname), SRC_DIR)
                    s = rel[:-3]  # strip .md, keeps subfolder prefix
                    if s not in slugs:
                        slugs.append(s)

    built = 0
    search_index = []

    # Build search index first (needed for inlining into pages)
    for slug in slugs:
        src = os.path.join(SRC_DIR, f"{slug}.md")

        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                raw = f.read()

            meta, body_md = parse_frontmatter(raw)

            title = meta.get("title", slug.capitalize())
            current_heading = title

            sections = []
            in_table = False

            table_first_cols = []
            table_header_seen = False

            for line in body_md.split("\n"):
                stripped = line.strip()

                if stripped.startswith("|") and "|" in stripped[1:]:
                    # Table row
                    if re.match(r'^\|[\s\-:|]+\|$', stripped):
                        table_header_seen = True  # separator marks end of header
                        continue

                    if not in_table:
                        # First row is the header — skip it
                        in_table = True
                        table_header_seen = False
                        continue

                    if not table_header_seen:
                        continue  # still in header somehow

                    cols = [c.strip() for c in stripped.strip("|").split("|")]

                    if cols:
                        col = re.sub(r'[`*\[\]()]', '', cols[0]).strip()

                        if col:
                            table_first_cols.append(col)

                    continue

                else:
                    if in_table and table_first_cols:
                        sections.append({"heading": current_heading, "text": ", ".join(table_first_cols)})
                        table_first_cols = []

                    in_table = False
                    table_header_seen = False

                if stripped.startswith("#"):
                    current_heading = stripped.lstrip("#").strip()

                elif stripped and not stripped.startswith("```") and not stripped.startswith("---"):
                    clean = re.sub(r'[`*\[\]()]', '', stripped)

                    if clean:
                        sections.append({"heading": current_heading, "text": clean})

            # Flush any remaining table
            if table_first_cols:
                sections.append({"heading": current_heading, "text": ", ".join(table_first_cols)})

            url = "index.html" if slug_basename(slug) == "index" else f"{slug_basename(slug)}.html"
            search_index.append({"slug": slug_basename(slug), "title": title, "url": url, "sections": sections})

    import json

    # Build a simple title -> source-md mapping for auto-linking class references.
    # Clean titles (remove `[ext]` marker and lightweight formatting) so pages
    # whose H1/title include the `[ext]` tag (extensions) still map to the
    # plain name (e.g. "Bank"). Also skip mapping the site/project name
    # `PyJavaBridge` so it isn't auto-linked.
    global SEARCH_MAP
    SEARCH_MAP = {}
    for item in search_index:
        title = item.get('title') or ''
        slug = item.get('slug')
        if not title or not slug:
            continue

        # Remove explicit [ext] markers and lightweight markdown chars
        cleaned = re.sub(r'\[ext\]', '', title)
        cleaned = re.sub(r'[`*()]+', '', cleaned).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Don't auto-link the project/site name
        if cleaned == 'PyJavaBridge' or title == 'PyJavaBridge':
            continue

        dest = f"{slug}.md"
        # Map both cleaned and original titles (if different)
        SEARCH_MAP[cleaned] = dest
        if title != cleaned:
            SEARCH_MAP[title] = dest

    # Precompile a combined regex for fast inline auto-linking replacements.
    # Keys are sorted longest-first to avoid partial matches (e.g. "Item" vs "ItemBuilder").
    global SEARCH_RE, DECORATORS_DEST
    SEARCH_RE = None
    try:
        keys = sorted(SEARCH_MAP.keys(), key=len, reverse=True)
        if keys:
            SEARCH_RE = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(k) for k in keys) + r')(?![A-Za-z0-9_])')
    except Exception:
        SEARCH_RE = None

    # Where decorator links should point (fallback to decorators.md)
    DECORATORS_DEST = SEARCH_MAP.get('Decorators') or SEARCH_MAP.get('decorators') or 'decorators.md'

    # Build backlinks and related-page suggestions
    # Backlinks: which pages mention this page's title
    title_to_slug = {item['title'].lower(): item['slug'] for item in search_index}

    # Precompute combined text for each page
    page_texts = {}
    for item in search_index:
        combined = item.get('title', '') + ' '
        for s in item.get('sections', []):
            combined += ' ' + (s.get('heading', '') or '') + ' ' + (s.get('text', '') or '')
        page_texts[item['slug']] = re.sub(r'\s+', ' ', combined).lower()

    # Compute backlinks
    slug_to_backlinks = {item['slug']: [] for item in search_index}
    for src in search_index:
        src_text = page_texts[src['slug']]
        for tgt in search_index:
            if src['slug'] == tgt['slug']:
                continue
            ttitle = (tgt.get('title') or '').lower()
            if not ttitle:
                continue
            if ttitle in src_text:
                slug_to_backlinks[tgt['slug']].append(src['slug'])

    # Compute related pages by simple word-overlap heuristic
    def words(s):
        return set(re.findall(r"[a-z0-9]{3,}", s.lower()))

    word_sets = {slug: words(text) for slug, text in page_texts.items()}
    related_map = {}
    for a in page_texts:
        scores = []
        for b in page_texts:
            if a == b:
                continue
            inter = len(word_sets[a].intersection(word_sets[b]))
            if inter > 0:
                scores.append((inter, b))
        scores.sort(reverse=True)
        related_map[a] = [b for _, b in scores[:6]]

    # Attach backlinks and related arrays to each search_index entry
    for item in search_index:
        item['backlinks'] = slug_to_backlinks.get(item['slug'], [])
        item['related'] = related_map.get(item['slug'], [])

    # Emit git metadata (repo, commits, tags) for client-side versioning support
    # Default inline git meta (fallback when git access fails)
    global _git_meta_json
    _git_meta_json = '{}'
    try:
        repo_root = os.path.dirname(DOCS_DIR)
        # remote URL
        try:
            remote_url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=repo_root, text=True).strip()
        except Exception:
            remote_url = ''

        repo_name = None
        m = re.search(r'github.com[:/](.+?)(?:\.git)?$', remote_url)
        if m:
            repo_name = m.group(1)

        # Gather commits (hash + message) so we can detect commit-prefixed versions
        commits = []
        versions = []  # list of {code, commit, label}
        try:
            log_out = subprocess.check_output(['git', 'log', '--pretty=format:%H%x01%s', '--reverse'], cwd=repo_root, text=True)
            for line in log_out.splitlines():
                if not line:
                    continue
                parts = line.split('\x01', 1)
                if len(parts) == 2:
                    h, msg = parts
                else:
                    h = parts[0]; msg = ''
                commits.append(h)
                # Match commit messages that start with a version code like "12A - description"
                # Only accept codes that are digits followed by a letter (e.g. 1A, 12B).
                # Accept common dash characters (hyphen, colon, en-dash, em-dash).
                m = re.match(r"^\s*([0-9]+[A-Za-z])\s*[-:—–]\s*(.+)", msg)
                if m:
                    code = m.group(1).upper()
                    label = m.group(2).strip()
                    versions.append({'code': code, 'commit': h, 'label': label})
        except Exception:
            # fallback to simple rev-list if git log fails
            try:
                commits = subprocess.check_output(['git', 'rev-list', '--reverse', 'HEAD'], cwd=repo_root, text=True).splitlines()
            except Exception:
                commits = []

        # Keep tags mapping for backwards compatibility but do not use tags for version selector
        tags = {}
        try:
            tag_lines = subprocess.check_output(['git', 'for-each-ref', '--format=%(refname:strip=2) %(objectname)', 'refs/tags'], cwd=repo_root, text=True).splitlines()
            for line in tag_lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    h = parts[1]
                    tags[name] = h
        except Exception:
            tags = {}

        # Map output page basenames (slug basename) back to their source
        # markdown path so the client can fetch raw markdown at a historical
        # commit when the generated HTML isn't present in that commit.
        try:
            src_map = {slug_basename(s): f"docs/src/{s}.md" for s in slugs}
        except Exception:
            src_map = {}

        # Determine which pages (by basename) exist in each version commit so
        # the client can hide links that weren't present in that historical
        # version. We inspect the repository tree at each version commit for
        # files under `docs/src/` and map them back to their slug basenames.
        pages_by_commit = {}
        try:
            for v in versions:
                c = v.get('commit')
                if not c:
                    pages_by_commit[c] = []
                    continue
                try:
                    tree_out = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', c, 'docs/src'], cwd=repo_root, text=True)
                    tree_files = set(line.strip() for line in tree_out.splitlines() if line.strip())
                except Exception:
                    tree_files = set()
                avail = []
                for s in slugs:
                    # Check both the full slug path (e.g. docs/src/getting_started/index.md)
                    # and the basename path (e.g. docs/src/index.md) because files
                    # were moved between commits and may appear under either location.
                    path_full = f"docs/src/{s}.md"
                    path_base = f"docs/src/{slug_basename(s)}.md"
                    if path_full in tree_files or path_base in tree_files:
                        avail.append(slug_basename(s))
                pages_by_commit[c] = avail
        except Exception:
            pages_by_commit = {}

        git_meta = {'repo': repo_name, 'commits': commits, 'tags': tags, 'versions': versions, 'src_map': src_map, 'pages_by_commit': pages_by_commit}
        try:
            with open(os.path.join(OUT_DIR, 'git_meta.json'), 'w', encoding='utf-8') as gf:
                json.dump(git_meta, gf, separators=(',', ':'))
        except Exception:
            pass

        # Inline JSON for file:// usage (client falls back to this if fetch fails)
        _git_meta_json = json.dumps(git_meta, separators=(',', ':'))

        # Pre-render version selector options so the <select> isn't empty before JS runs.
        try:
            global VERSION_OPTIONS
            opts = ['<option value="">Live</option>']
            if versions:
                # newest-first
                for v in reversed(versions):
                    code = v.get('code')
                    commit = v.get('commit','')
                    label = v.get('label','')
                    if not code: continue
                    # Render compact option text (only the version code).
                    # Attach label/commit as data attributes so the client can
                    # display the description under the selector.
                    esc_code = html.escape(code)
                    if label:
                        esc_label = html.escape(label)
                        esc_commit = html.escape(commit[:8])
                        opts.append(f'<option value="{esc_code}" data-label="{esc_label}" data-commit="{esc_commit}">{esc_code}</option>')
                    else:
                        esc_commit = html.escape(commit[:8])
                        opts.append(f'<option value="{esc_code}" data-commit="{esc_commit}">{esc_code}</option>')
            else:
                # fallback: include latest commit if present
                if commits:
                    latest = commits[-1]
                    esc_commit = html.escape(latest[:8])
                    opts.append(f'<option value="{latest}" data-commit="{esc_commit}">{esc_commit}</option>')

            VERSION_OPTIONS = '\n'.join(opts)
        except Exception:
            VERSION_OPTIONS = '<option value="">Live</option>'
    except Exception:
        pass

    search_json = json.dumps(search_index, separators=(',', ':'))
    cctx = zstandard.ZstdCompressor(level=22)

    compressed = cctx.compress(search_json.encode('utf-8'))
    _search_index_zstd_b64 = base64.b64encode(compressed).decode('ascii')

    raw_size = len(search_json.encode('utf-8'))
    compressed_size = len(compressed)
    b64_size = len(_search_index_zstd_b64)

    print(f"   Search index: {raw_size:,} bytes → {compressed_size:,} zstd → {b64_size:,} base64 ({100*b64_size/raw_size:.1f}%)")

    # Build pages (with search index inlined) — parallelized
    slugs_to_build = []
    for slug in slugs:
        src = os.path.join(SRC_DIR, f"{slug}.md")
        if os.path.exists(src):
            slugs_to_build.append(slug)

    if slugs_to_build:
        # Use a ThreadPoolExecutor to allow concurrent page builds (I/O and subprocess heavy).
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
            future_to_slug = {executor.submit(build_page, slug): slug for slug in slugs_to_build}
            for fut in concurrent.futures.as_completed(future_to_slug):
                slug = future_to_slug[fut]
                try:
                    fut.result()
                    print(f"  ✓ {slug_basename(slug)}.html")
                    built += 1
                except Exception as e:
                    print(f"  ✗ {slug_basename(slug)}.html (error: {e})")
    else:
        print("No pages found to build.")

    print(f"\n✅ Built {built} pages")

if __name__ == "__main__":
    main()

