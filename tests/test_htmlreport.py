"""Informe HTML autocontenido a partir del Markdown del informe. Datos sintéticos."""

import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

from mvpup.cli import main
from mvpup.htmlreport import render_html

BASE = ["run", "--product", "Producto Demo", "--objective", "ingresos", "--stage", "mvp"]
RESOURCE_TAGS = {"script", "link", "img", "iframe", "object", "embed", "source", "video", "audio", "track"}


class _Inventory(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.styles: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self._in_style = tag == "style"

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self.styles.append(data)


def _inventory(html: str) -> _Inventory:
    inv = _Inventory()
    inv.feed(html)
    return inv


def _dry_run_markdown(tmp_path: Path, *extra: str) -> Path:
    out = tmp_path / "informes"
    assert main([*BASE, *extra, "--dry-run", "--out", str(out)]) == 0
    return next((out / "producto-demo").glob("*-dry-run.md"))


@pytest.fixture
def express_md(tmp_path, capsys) -> str:
    text = _dry_run_markdown(tmp_path).read_text(encoding="utf-8")
    capsys.readouterr()
    return text


def test_html_is_well_formed_xml(express_md):
    html = render_html(express_md)
    root = ET.fromstring(html)  # un solo árbol bien formado: void elements cerrados, & escapados
    assert root.tag == "html" and root.get("lang") == "es"
    assert html.lstrip().startswith("<!DOCTYPE html>")


def test_html_has_no_external_resources(express_md):
    inv = _inventory(render_html(express_md))
    assert not [t for t, _ in inv.tags if t in RESOURCE_TAGS]
    for tag, attrs in inv.tags:
        for name, value in attrs.items():
            if name in ("src", "href") and value:
                assert tag == "a" or not value.startswith(("http:", "https:", "//"))
    css = "\n".join(inv.styles)
    assert "url(" not in css and "@import" not in css
    assert any(t == "meta" and a.get("charset") == "utf-8" for t, a in inv.tags)


def test_matrix_is_an_accessible_table(express_md):
    html = render_html(express_md)
    root = ET.fromstring(html)
    tables = root.iter("table")
    matrix = next(t for t in tables if t.find("caption") is not None and "Matriz" in (t.find("caption").text or ""))
    header_cells = matrix.find("thead").find("tr").findall("th")
    assert [c.get("scope") for c in header_cells] == ["col", "col", "col"]
    assert [c.text for c in header_cells][1:] == ["Esfuerzo BAJO", "Esfuerzo MEDIO/ALTO"]
    body_rows = matrix.find("tbody").findall("tr")
    assert len(body_rows) == 2
    for row in body_rows:
        first = row[0]
        assert first.tag == "th" and first.get("scope") == "row"
        assert "Impacto" in "".join(first.itertext())
        for cell in row.findall("td"):  # cada cuadrante: etiqueta + lista de hallazgos, no <br>
            assert cell.find("strong") is not None
            assert cell.find("ul") is not None
            assert cell.find("br") is None
    assert "<br>" not in html


def test_headings_lists_checkboxes_and_scores_table_are_rendered(express_md):
    html = render_html(express_md)
    root = ET.fromstring(html)
    assert root.find("head/title").text == "MVP-UP · Producto Demo · " + express_md.split(" · ")[2].split("\n")[0]
    h2 = [h.text for h in root.iter("h2")]
    assert "Scores por dimensión" in h2 and "TOP-5 propuesto para autorización" in h2
    assert any(h.text and h.text.startswith("H1 — ") for h in root.iter("h3"))
    assert len(list(root.iter("input"))) >= 1  # «- [ ] acción» del roadmap
    scores = next(t for t in root.iter("table") if (t.find("caption").text or "").startswith("Scores"))
    assert scores.find("thead/tr/th").text == "Dimensión"
    assert any("Técnica" in "".join(r.itertext()) for r in scores.find("tbody"))
    assert root.find("body/main") is not None or root.find("body") is not None


def test_inline_markdown_and_escaping():
    html = render_html("# T <x> & y\n\nTexto **negrita** y `codigo` con <script> & fin.\n\n> cita\n\n1. uno\n2. dos\n")
    root = ET.fromstring(html)
    assert root.find("body//h1").text == "T <x> & y"
    p = root.find("body//p")
    assert p.find("strong").text == "negrita" and p.find("code").text == "codigo"
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert root.find("body//blockquote") is not None
    assert [li.text for li in root.find("body//ol")] == ["uno", "dos"]


def test_nested_lists_keep_their_nesting():
    html = render_html("- padre\n  - hijo\n- otro\n")
    root = ET.fromstring(html)
    top = root.find("body//ul")
    assert [li.text.strip() for li in top.findall("li")] == ["padre", "otro"]
    assert top.find("li/ul/li").text.strip() == "hijo"


def test_ligera_report_and_comparison_render_too(tmp_path, capsys):
    ligera = _dry_run_markdown(tmp_path, "--mode", "ligera").read_text(encoding="utf-8")
    ET.fromstring(render_html(ligera))
    assert "3 tareas de reanudación" in render_html(ligera)
    from mvpup.compare import diff_reports, render_diff

    md = render_diff(diff_reports({"scores": {"tecnica": 4}}, {"scores": {"tecnica": 6}}))
    assert "Δ por dimensión" in render_html(md)
    ET.fromstring(render_html(md))


def test_cli_html_writes_next_to_the_report_or_to_out(tmp_path, capsys):
    md_path = _dry_run_markdown(tmp_path)
    assert main(["html", str(md_path)]) == 0
    html_path = md_path.with_suffix(".html")
    assert html_path.is_file() and str(html_path) in capsys.readouterr().out
    ET.fromstring(html_path.read_text(encoding="utf-8"))
    target = tmp_path / "salida" / "informe.html"
    assert main(["html", str(md_path), "--out", str(target)]) == 0
    assert target.is_file()
    assert main(["html", str(tmp_path / "no-existe.md")]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_run_with_html_flag_writes_the_html_twin(tmp_path, capsys):
    out = tmp_path / "informes"
    assert main([*BASE, "--dry-run", "--html", "--out", str(out)]) == 0
    html_path = next((out / "producto-demo").glob("*-dry-run.html"))
    assert "HTML:" in capsys.readouterr().out
    ET.fromstring(html_path.read_text(encoding="utf-8"))
