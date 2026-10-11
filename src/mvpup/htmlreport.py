"""Informe HTML autocontenido a partir del Markdown del informe.

Sin CDN, sin JavaScript, sin imágenes ni fuentes externas: un único fichero que se
abre en cualquier navegador (y se imprime) aunque no haya red. Convierte solo el
subconjunto de Markdown que generan `report.py`, `compare.py` y `portfolio.py`:
headers, párrafos, negrita, código en línea, enlaces, listas anidadas (con casillas
`- [ ]`), listas numeradas, citas y tablas.

La matriz impacto × esfuerzo sale como tabla accesible: `<caption>`, cabeceras de
columna y de fila con `scope`, y cada cuadrante como etiqueta + lista de hallazgos
(en el Markdown son celdas separadas por `<br>`).

La salida es XHTML bien formado (void elements cerrados, `&` escapado) para que se
pueda validar con un parser XML en los tests.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM_RE = re.compile(r"^(\s*)(?:([-*+])|(\d+)[.)])\s+(.*)$")
_CHECKBOX_RE = re.compile(r"^\[( |x|X)\]\s+(.*)$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
_CELL_BREAK = "<br>"  # separador de hallazgos dentro de una celda (report._cell)

CSS = """\
:root { color-scheme: light; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.5;
       max-width: 72rem; margin: 0 auto; padding: 1rem 1.25rem; color: #1b1b1b; background: #fff; }
main { display: block; }
h1 { font-size: 1.6rem; border-bottom: 2px solid #1b1b1b; padding-bottom: .25rem; }
h2 { font-size: 1.25rem; margin-top: 2rem; border-bottom: 1px solid #c8c8c8; padding-bottom: .2rem; }
h3 { font-size: 1.05rem; margin-top: 1.25rem; }
table { border-collapse: collapse; width: 100%; margin: .75rem 0 1rem; font-size: .95rem; }
caption { text-align: left; font-weight: 600; padding: .25rem 0; }
th, td { border: 1px solid #c8c8c8; padding: .4rem .55rem; vertical-align: top; text-align: left; }
th { background: #f0f0f0; }
th[scope="row"] { background: #f7f7f7; white-space: nowrap; }
table.matrix td { width: 42%; }
table.matrix ul { margin: .3rem 0 0; padding-left: 1.1rem; }
table.matrix li + li { margin-top: .25rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .92em;
       background: #f3f3f3; padding: 0 .25em; border-radius: 3px; }
blockquote { border-left: 4px solid #c8c8c8; margin: 1rem 0; padding: .25rem 1rem; color: #444; }
ul, ol { padding-left: 1.5rem; }
li { margin: .15rem 0; }
label input[type="checkbox"] { margin-right: .4rem; }
@media print { body { max-width: none; padding: 0; } h2 { break-after: avoid; } table { break-inside: avoid; } }
"""


def _inline(text: str) -> str:
    """Escapa el texto y aplica negrita, código en línea y enlaces."""
    escaped = html.escape(text, quote=True)
    escaped = _CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", escaped)
    return _LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', escaped)


def _split_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in _CELL_SPLIT_RE.split(body)]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


@dataclass
class _Converter:
    out: list[str] = field(default_factory=list)
    paragraph: list[str] = field(default_factory=list)
    quote: list[str] = field(default_factory=list)
    lists: list[tuple[int, str]] = field(default_factory=list)  # (sangría, 'ul'|'ol') abiertas
    item_open: bool = False
    table: list[list[str]] = field(default_factory=list)
    last_heading: str = ""
    title: str = ""

    # --- cierres -----------------------------------------------------------------------------

    def _flush_paragraph(self) -> None:
        if self.paragraph:
            self.out.append("<p>" + "<br/>".join(_inline(t) for t in self.paragraph) + "</p>")
            self.paragraph = []

    def _flush_quote(self) -> None:
        if self.quote:
            self.out.append("<blockquote><p>" + "<br/>".join(_inline(t) for t in self.quote) + "</p></blockquote>")
            self.quote = []

    def _close_item(self) -> None:
        if self.item_open:
            self.out[-1] += "</li>"  # en la misma línea: el texto del <li> no arrastra saltos
            self.item_open = False

    def _close_lists(self, down_to: int = -1) -> None:
        while self.lists and self.lists[-1][0] > down_to:
            self._close_item()
            _, tag = self.lists.pop()
            self.out.append(f"</{tag}>")
            self.item_open = bool(self.lists)  # el <li> padre sigue abierto

    def _flush_table(self) -> None:
        if self.table:
            self.out.append(self._render_table(self.table))
            self.table = []

    def _flush_blocks(self) -> None:
        self._flush_paragraph()
        self._flush_quote()
        self._close_lists()
        self._flush_table()

    # --- bloques -----------------------------------------------------------------------------

    def _heading(self, level: int, text: str) -> None:
        self._flush_blocks()
        self.last_heading = text
        if level == 1 and not self.title:
            self.title = text
        self.out.append(f"<h{level}>{_inline(text)}</h{level}>")

    def _list_item(self, indent: int, ordered: bool, text: str) -> None:
        self._flush_paragraph()
        self._flush_quote()
        self._flush_table()
        tag = "ol" if ordered else "ul"
        if self.lists and indent > self.lists[-1][0]:
            self.out.append(f"<{tag}>")  # anidada dentro del <li> abierto
            self.lists.append((indent, tag))
        else:
            self._close_lists(indent)
            if not self.lists or self.lists[-1][0] < indent or self.lists[-1][1] != tag:
                self._close_lists(indent - 1)
                self.out.append(f"<{tag}>")
                self.lists.append((indent, tag))
            else:
                self._close_item()
        self.out.append(f"<li>{self._item_body(text)}")
        self.item_open = True

    @staticmethod
    def _item_body(text: str) -> str:
        box = _CHECKBOX_RE.match(text)
        if not box:
            return _inline(text)
        checked = ' checked="checked"' if box.group(1).lower() == "x" else ""
        return f'<label><input type="checkbox" disabled="disabled"{checked}/>{_inline(box.group(2))}</label>'

    def _render_table(self, rows: list[list[str]]) -> str:
        header, body = rows[0], rows[1:]
        if body and _is_separator(body[0]):
            body = body[1:]
        matrix = header[0] == "" and len(header) > 1  # primera columna = cabeceras de fila
        width = len(header)
        parts = ['<table class="matrix">' if matrix else "<table>"]
        if self.last_heading:
            parts.append(f"<caption>{_inline(self.last_heading)}</caption>")
        parts.append("<thead><tr>" + "".join(f'<th scope="col">{_inline(c)}</th>' for c in header) + "</tr></thead>")
        parts.append("<tbody>")
        for row in body:
            cells = (row + [""] * width)[:width]
            rendered = []
            for n, cell in enumerate(cells):
                if matrix and n == 0:
                    rendered.append(f'<th scope="row">{_inline(cell)}</th>')
                elif matrix:
                    rendered.append(f"<td>{self._quadrant_cell(cell)}</td>")
                else:
                    rendered.append(f"<td>{self._plain_cell(cell)}</td>")
            parts.append("<tr>" + "".join(rendered) + "</tr>")
        parts.append("</tbody></table>")
        return "".join(parts)

    @staticmethod
    def _plain_cell(cell: str) -> str:
        return "<br/>".join(_inline(part) for part in cell.split(_CELL_BREAK))

    @staticmethod
    def _quadrant_cell(cell: str) -> str:
        """«⚡ QUICK WINS: a<br>b» → etiqueta + lista; «⚡ QUICK WINS: —» → etiqueta + «—»."""
        items = cell.split(_CELL_BREAK)
        label, sep, first = items[0].partition(": ")
        if not sep:
            label, first = "", items[0]
        items = [first, *items[1:]]
        head = f"<strong>{_inline(label)}:</strong> " if label else ""
        if items == ["—"] or items == [""]:
            return head + _inline(items[0] or "—")
        return head + "<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items if i) + "</ul>"

    # --- entrada -----------------------------------------------------------------------------

    def feed(self, markdown: str) -> None:
        for raw in markdown.splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                self._flush_paragraph()
                self._flush_quote()
                self._close_lists()
                self.table.append(_split_cells(stripped))
                continue
            self._flush_table()
            if not stripped:
                self._flush_blocks()
                continue
            heading = _HEADING_RE.match(line)
            if heading:
                self._heading(len(heading.group(1)), heading.group(2))
                continue
            item = _ITEM_RE.match(line)
            if item:
                self._list_item(len(item.group(1).expandtabs(4)), item.group(3) is not None, item.group(4))
                continue
            if stripped.startswith(">"):
                self._flush_paragraph()
                self._close_lists()
                self.quote.append(stripped[1:].strip())
                continue
            self._close_lists()
            self._flush_quote()
            self.paragraph.append(stripped)
        self._flush_blocks()


def markdown_to_html(markdown: str) -> tuple[str, str]:
    """(título, cuerpo HTML) del Markdown dado; el título es el primer `# `."""
    conv = _Converter()
    conv.feed(markdown)
    return conv.title, "\n".join(conv.out)


def render_html(markdown: str, title: str | None = None) -> str:
    """Página HTML completa y autocontenida (sin recursos externos)."""
    found, body = markdown_to_html(markdown)
    page_title = title or found or "MVP-UP"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n<head>\n<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        f"<title>{html.escape(page_title, quote=True)}</title>\n"
        f"<style>\n{CSS}</style>\n</head>\n<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n"
    )
