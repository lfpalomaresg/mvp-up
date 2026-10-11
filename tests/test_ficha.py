"""`--ficha`: anclar la pasada en el frontmatter de la ficha sin tocar el resto. Datos ficticios."""

import json
from datetime import date
from pathlib import Path

import pytest

from mvpup.cli import main
from mvpup.ficha import FRONTMATTER_KEYS, anchor_frontmatter, read_frontmatter
from mvpup.parsing import GROUP_SEPARATOR
from support import VALID_OUTPUT

WHEN = date(2026, 10, 11)
REPORT = Path("informes/demo/2026-10-11-informe.md")
BODY = "# Demo\n\nFicha ficticia con **negrita**, una lista:\n\n- a\n- b\n\n---\n\nY una regla horizontal arriba.\n"


def test_ficha_without_frontmatter_gets_one_and_keeps_the_body_byte_for_byte(tmp_path):
    ficha = tmp_path / "demo.md"
    ficha.write_bytes(BODY.encode("utf-8"))
    assert anchor_frontmatter(ficha, WHEN, 6.2, REPORT) is True
    text = ficha.read_text(encoding="utf-8")
    assert text.endswith(BODY)  # el cuerpo no se reescribe
    head = text[: -len(BODY)]
    assert head == (
        "---\nmvpup_date: 2026-10-11\nmvpup_score: 6.2\n"
        'mvpup_report: "informes/demo/2026-10-11-informe.md"\n---\n'
    )


def test_existing_frontmatter_keeps_foreign_keys_verbatim(tmp_path):
    ficha = tmp_path / "demo.md"
    original = (
        "---\n"
        "title:   Demo   \n"
        "tags: [a, b]\n"
        "# comentario que debe sobrevivir\n"
        "owner:\n  name: Alguien\n"
        "---\n"
        + BODY
    )
    ficha.write_text(original, encoding="utf-8")
    assert anchor_frontmatter(ficha, WHEN, 6.2, REPORT) is True
    text = ficha.read_text(encoding="utf-8")
    foreign = "title:   Demo   \ntags: [a, b]\n# comentario que debe sobrevivir\nowner:\n  name: Alguien\n"
    assert text.startswith("---\n" + foreign)
    assert text.endswith("---\n" + BODY)
    assert read_frontmatter(ficha) == {
        "mvpup_date": "2026-10-11", "mvpup_score": "6.2",
        "mvpup_report": '"informes/demo/2026-10-11-informe.md"',
    }


def test_anchor_is_idempotent_and_a_new_pass_replaces_values_in_place(tmp_path):
    ficha = tmp_path / "demo.md"
    ficha.write_text("---\ntitle: Demo\n---\n" + BODY, encoding="utf-8")
    anchor_frontmatter(ficha, WHEN, 6.2, REPORT)
    first = ficha.read_bytes()
    assert anchor_frontmatter(ficha, WHEN, 6.2, REPORT) is False
    assert ficha.read_bytes() == first
    later = Path("informes/demo/2026-11-20-informe.md")
    assert anchor_frontmatter(ficha, date(2026, 11, 20), 7.0, later) is True
    text = ficha.read_text(encoding="utf-8")
    for key in FRONTMATTER_KEYS:
        assert text.count(f"{key}:") == 1  # sin duplicar claves
    assert "mvpup_date: 2026-11-20" in text and "mvpup_score: 7.0" in text and "2026-11-20-informe.md" in text
    assert text.endswith("---\n" + BODY) and text.startswith("---\ntitle: Demo\n")


def test_crlf_and_bom_are_preserved(tmp_path):
    ficha = tmp_path / "demo.md"
    body = "# Demo\r\n\r\nTexto.\r\n"
    ficha.write_bytes("\ufeff---\r\ntitle: Demo\r\n---\r\n".encode("utf-8") + body.encode("utf-8"))
    anchor_frontmatter(ficha, WHEN, 6.2, REPORT)
    raw = ficha.read_bytes()
    assert raw.startswith("\ufeff---\r\ntitle: Demo\r\nmvpup_date: 2026-10-11\r\n".encode("utf-8"))
    assert raw.endswith(body.encode("utf-8"))
    assert b"\n" not in raw.replace(b"\r\n", b"")  # ningún salto sin \r


def test_missing_ficha_is_created_minimal_with_frontmatter(tmp_path):
    ficha = tmp_path / "fichas" / "nueva.md"
    assert anchor_frontmatter(ficha, WHEN, None, REPORT, product="Nueva Demo") is True
    text = ficha.read_text(encoding="utf-8")
    assert text.startswith("---\nmvpup_date: 2026-10-11\nmvpup_score: null\n")
    assert "# Nueva Demo" in text


def test_report_path_is_quoted_as_a_yaml_string(tmp_path):
    ficha = tmp_path / "demo.md"
    ficha.write_text(BODY, encoding="utf-8")
    anchor_frontmatter(ficha, WHEN, 5.0, Path('C:\\informes\\raro "x".md'))
    assert read_frontmatter(ficha)["mvpup_report"] == '"C:\\\\informes\\\\raro \\"x\\".md"'


def test_unclosed_leading_fence_is_body_not_frontmatter(tmp_path):
    ficha = tmp_path / "demo.md"
    original = "---\nesto no es frontmatter: no cierra\n\n# Demo\n"
    ficha.write_text(original, encoding="utf-8")
    anchor_frontmatter(ficha, WHEN, 5.0, REPORT)
    text = ficha.read_text(encoding="utf-8")
    assert text.endswith(original)
    assert text.startswith("---\nmvpup_date: 2026-10-11\n")


def test_mixed_crlf_and_lf_frontmatter_is_still_recognised_and_not_duplicated(tmp_path):
    # Ficha sincronizada entre equipos: el fence va con CRLF y una clave con LF. Sin esto el cierre
    # no se reconocía y la ficha recibía un SEGUNDO frontmatter delante del original.
    ficha = tmp_path / "demo.md"
    ficha.write_bytes(b"---\r\ntitle: Demo\n---\r\n# Body\n")
    assert anchor_frontmatter(ficha, WHEN, 6.0, REPORT) is True
    raw = ficha.read_bytes()
    assert raw.count(b"---") == 2
    assert raw.startswith(b"---\r\ntitle: Demo\r\nmvpup_date: 2026-10-11\r\n")
    assert raw.endswith(b"---\r\n# Body\n")
    assert anchor_frontmatter(ficha, WHEN, 6.0, REPORT) is False


def test_frontmatter_closed_with_dots_keeps_its_closing_fence(tmp_path):
    ficha = tmp_path / "demo.md"
    ficha.write_bytes(b"---\ntitle: Demo\n...\n# Body\n")
    assert anchor_frontmatter(ficha, WHEN, 6.0, REPORT) is True
    text = ficha.read_text(encoding="utf-8")
    assert text.startswith("---\ntitle: Demo\nmvpup_date: 2026-10-11\n")
    assert text.endswith('mvpup_report: "informes/demo/2026-10-11-informe.md"\n...\n# Body\n')
    assert read_frontmatter(ficha)["mvpup_score"] == "6.0"


# --- CLI -----------------------------------------------------------------------------------

BASE = ["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos"]


def _fake(tmp_path):
    grouped = "\n".join(f"{GROUP_SEPARATOR}{d}\n{VALID_OUTPUT}" for d in ("comercial", "marketing"))
    resp = tmp_path / "resp.json"
    resp.write_text(json.dumps({"tecnica": VALID_OUTPUT, "producto_ux": VALID_OUTPUT,
                                "comercial+marketing": grouped}), encoding="utf-8")
    return ["--runner", "fake", "--fake-responses", str(resp), "--out", str(tmp_path / "inf")]


def test_cli_ficha_updates_frontmatter_and_keeps_the_rest(tmp_path, capsys):
    ficha = tmp_path / "demo.md"
    ficha.write_text("---\ntitle: Demo\n---\n" + BODY, encoding="utf-8")
    assert main([*BASE, *_fake(tmp_path), "--ficha", str(ficha)]) == 0
    out = capsys.readouterr().out
    assert "Ficha" in out and "frontmatter" in out
    text = ficha.read_text(encoding="utf-8")
    fm = read_frontmatter(ficha)
    assert fm["mvpup_date"] == date.today().isoformat() and fm["mvpup_score"] == "6.0"
    assert fm["mvpup_report"].endswith('-informe.md"') and "title: Demo" in text
    assert text.endswith("---\n" + BODY)
    assert "LEER AL RETOMAR" not in text  # el bloque visible sigue siendo opt-in (--anclar)
    assert main([*BASE, *_fake(tmp_path), "--ficha", str(ficha)]) == 0  # segunda pasada: informe-2
    assert read_frontmatter(ficha)["mvpup_report"].endswith('-informe-2.md"')


def test_cli_ficha_with_anclar_writes_both_frontmatter_and_block(tmp_path, capsys):
    ficha = tmp_path / "demo.md"
    assert main([*BASE, *_fake(tmp_path), "--ficha", str(ficha), "--anclar"]) == 0
    text = ficha.read_text(encoding="utf-8")
    assert text.startswith("---\nmvpup_date:") and "LEER AL RETOMAR" in text and "# Demo" in text


def test_cli_dry_run_never_touches_the_ficha(tmp_path, capsys):
    ficha = tmp_path / "demo.md"
    ficha.write_text(BODY, encoding="utf-8")
    assert main([*BASE, "--dry-run", "--ficha", str(ficha), "--out", str(tmp_path / "inf")]) == 0
    assert ficha.read_text(encoding="utf-8") == BODY
    assert "ficha" in capsys.readouterr().err.lower()
    missing = tmp_path / "no-existe.md"
    assert main([*BASE, "--dry-run", "--ficha", str(missing), "--out", str(tmp_path / "inf")]) == 0
    assert not missing.exists()
