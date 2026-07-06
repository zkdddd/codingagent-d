import html
import re

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer, get_lexer_by_name, TextLexer


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
    formatter = HtmlFormatter(nowrap=True, style="default")
    highlighted = highlight(code, lexer, formatter).strip()
    return f'<pre><code class="hl">{highlighted}</code></pre>'


def render(text: str) -> str:
    """Markdown -> HTML，代码块用 Pygments 高亮。"""
    if not text:
        return ""
    html_body = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "breaks", "sane_lists"],
    )
    html_body = _CODE_RE.sub(_highlight_code, html_body)
    return html_body


def highlight_css() -> str:
    return HtmlFormatter(style="default").get_style_defs(".hl")
