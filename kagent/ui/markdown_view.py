import html
import re

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer


_FORMATTER = HtmlFormatter(nowrap=True, style="monokai")
_CODE_RE = re.compile(r"<pre><code(?:\s+class=\"([^\"]+)\")?>(.*?)</code></pre>", re.DOTALL)


def _highlight_code(match: re.Match) -> str:
    lang_cls, raw = match.group(1), match.group(2)
    code = html.unescape(raw)
    lexer = None
    if lang_cls and lang_cls.startswith("language-"):
        try:
            lexer = get_lexer_by_name(lang_cls[9:], stripall=False)
        except Exception:
            lexer = None
    if lexer is None:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()
    highlighted = highlight(code, lexer, _FORMATTER).strip()
    return f'<pre><code class="hl">{highlighted}</code></pre>'


def render(text: str) -> str:
    """Render Markdown to HTML and highlight fenced code blocks."""
    if not text:
        return ""
    html_body = markdown.markdown(
        text,
        extensions=[
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.sane_lists",
        ],
    )
    return _CODE_RE.sub(_highlight_code, html_body)


def highlight_css() -> str:
    return _FORMATTER.get_style_defs(".hl")
