"""Red de seguridad en las zonas de mayor riesgo (encargo t-mvp-up).

1. Secretos que salen hacia la API: redacción y exclusión de ficheros.
2. Entradas externas: JSON de pasadas anteriores (editables a mano) y salida de los agentes.
3. Fechas: orden de las pasadas y fechas imposibles.

Todos los valores son FICTICIOS y se construyen por concatenación (no disparan escáneres).
"""

import json
from datetime import date

import pytest

from mvpup.anthropic_runner import is_secret_file, repo_snapshot
from mvpup.compare import diff_reports, older_than_six_months, render_diff
from mvpup.dimensions import Dimension as D
from mvpup.parsing import FormatError, parse_agent_output
from mvpup.redaction import REDACTED, redact
from mvpup.report import previous_reports

# --- 1. secretos hacia la API -----------------------------------------------------------------

FAKE_STRIPE_LIVE = "sk_" + "live_" + "51Hx" + "a" * 24
FAKE_STRIPE_TEST = "sk_" + "test_" + "b" * 24
FAKE_STRIPE_RESTRICTED = "rk_" + "live_" + "c" * 24
FAKE_BEARER = "eyJ" + "d" * 30


@pytest.mark.parametrize("secret", [FAKE_STRIPE_LIVE, FAKE_STRIPE_TEST, FAKE_STRIPE_RESTRICTED])
def test_stripe_keys_are_redacted_anywhere_in_the_text(secret):
    out = redact(f"stripe.api_key_used({secret!r})  # cobros\nconst k = `{secret}`")
    assert secret not in out
    assert out.count(REDACTED) == 2


@pytest.mark.parametrize("line", [
    f"Authorization: Bearer {FAKE_BEARER}",
    f"headers = {{'Authorization': 'Bearer {FAKE_BEARER}'}}",
    f"curl -H \"authorization: bearer {FAKE_BEARER}\" https://api.ejemplo.test",
])
def test_bearer_tokens_are_redacted(line):
    out = redact(line)
    assert FAKE_BEARER not in out
    assert "Bearer" in out or "bearer" in out  # el contexto se conserva, solo cae el valor


def test_url_password_containing_an_at_sign_is_redacted_whole():
    url = "postgres://usuario:" + "cla" + "@ve" + "@db.ejemplo.test:5432/app"
    out = redact(url)
    assert "cla" not in out and "ve@db" not in out
    assert out == f"postgres://usuario:{REDACTED}@db.ejemplo.test:5432/app"


def test_url_credentials_redaction_does_not_swallow_the_path():
    out = redact("ver https://u:clave-ficticia@host.test/ruta/@arroba y sigue")
    assert out == f"ver https://u:{REDACTED}@host.test/ruta/@arroba y sigue"


@pytest.mark.parametrize("url, expected", [
    ("https://u:clave-ficticia@host.test?email=a@b", f"https://u:{REDACTED}@host.test?email=a@b"),
    ("https://u:clave-ficticia@host.test#ancla@x", f"https://u:{REDACTED}@host.test#ancla@x"),
    ("https://u:cla@ve@host.test?q=a@b#f@g", f"https://u:{REDACTED}@host.test?q=a@b#f@g"),
])
def test_url_credentials_redaction_stops_at_query_and_fragment(url, expected):
    assert redact(url) == expected


@pytest.mark.parametrize("name", [
    "app.sqlite3", "data/prod.sqlite3", "terraform.tfstate", "infra/terraform.tfstate.backup",
])
def test_database_and_infra_state_files_are_secret(name):
    assert is_secret_file(name) is True


def test_snapshot_never_ships_tfstate_or_sqlite3_content(tmp_path):
    (tmp_path / "README.md").write_text("# demo", encoding="utf-8")
    (tmp_path / "terraform.tfstate").write_text('{"password": "VALOR-TFSTATE"}', encoding="utf-8")
    (tmp_path / "local.sqlite3").write_text("VALOR-SQLITE", encoding="utf-8")
    snap = repo_snapshot(tmp_path)
    assert "VALOR-TFSTATE" not in snap and "VALOR-SQLITE" not in snap
    assert "terraform.tfstate" not in snap.split("## git log")[0]


@pytest.mark.parametrize("text", [
    "Bearer de un chiste",  # prosa: una palabra corta tras «Bearer» no es un token
    "sk_live_corto",
    "La key del README explica el sistema",
])
def test_redaction_leaves_ordinary_prose_alone(text):
    assert redact(text) == text


# --- 2. entradas externas ---------------------------------------------------------------------


def _report(**fields):
    base = {
        "schema": 1, "product": "Producto Demo", "slug": "producto-demo", "date": "2026-09-01",
        "mode": "express", "stage": "mvp", "objective": "ingresos", "global_score": 5.0,
        "scores": {"tecnica": 4, "producto_ux": 6},
        "roadmap": [], "findings": [],
    }
    base.update(fields)
    return base


def _from_disk(raw: str):
    """Como lo lee `load_report_json`: `json.loads` acepta NaN/Infinity."""
    return json.loads(raw)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "42", "-3", "10.5"])
def test_unreadable_or_out_of_range_previous_scores_are_ignored_and_reported(bad):
    previous = _from_disk(json.dumps(_report()).replace('"tecnica": 4', f'"tecnica": {bad}'))
    diff = diff_reports(previous, _report(date="2026-10-01", scores={"tecnica": 7, "producto_ux": 6}))
    row = next(r for r in diff.rows if r.dimension is D.TECNICA)
    assert row.previous is None
    assert row.delta == "nuevo"
    assert any("scores.tecnica" in w for w in diff.warnings)
    assert "nan" not in render_diff(diff).lower()


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "11", "-1"])
def test_unreadable_or_out_of_range_global_score_is_ignored_and_reported(bad):
    previous = _from_disk(json.dumps(_report()).replace('"global_score": 5.0', f'"global_score": {bad}'))
    diff = diff_reports(previous, _report(date="2026-10-01", global_score=6.0))
    assert diff.previous_global is None
    assert diff.global_delta == "nuevo"
    assert any("global_score" in w for w in diff.warnings)


def test_boundary_scores_zero_and_ten_are_valid_previous_scores():
    diff = diff_reports(_report(scores={"tecnica": 0, "producto_ux": 10}),
                        _report(date="2026-10-01", scores={"tecnica": 1, "producto_ux": 10}))
    deltas = {r.dimension: r.delta for r in diff.rows}
    assert deltas == {D.TECNICA: "+1", D.PRODUCTO_UX: "="}
    assert not any("ignor" in w.lower() for w in diff.warnings)


AGENT_OUTPUT = """\
## Score: 5/10 (rúbrica al pie)
## Hallazgos (máx 7, ordenados por impacto)
{line}
## Quick wins (impacto A/M con esfuerzo B)
## Riesgos si no se actúa
## Datos que faltan para evaluar mejor
"""


def test_finding_with_action_before_evidence_is_read_in_the_right_fields():
    line = ("- [H1] No hay precios públicos · Impacto: A · Esfuerzo: M · Acción: Publicar la página de precios"
            " · Evidencia: web/precios.html vacío · ver commit abc")
    finding = parse_agent_output(AGENT_OUTPUT.format(line=line)).findings[0]
    assert finding.action == "Publicar la página de precios"
    assert finding.evidence == "web/precios.html vacío · ver commit abc"


def test_evidence_may_contain_the_middle_dot_without_losing_the_action():
    line = ("- [H1] No hay precios públicos · Impacto: A · Esfuerzo: M · Evidencia: web/a.html · web/b.html"
            " · Acción: Publicar la página de precios")
    finding = parse_agent_output(AGENT_OUTPUT.format(line=line)).findings[0]
    assert finding.evidence == "web/a.html · web/b.html"
    assert finding.action == "Publicar la página de precios"


def test_finding_with_free_text_before_its_fields_fails_closed():
    line = ("- [H1] No hay precios públicos · Impacto: A · Esfuerzo: M y además texto suelto"
            " · Evidencia: web/precios.html · Acción: Publicar la página de precios")
    with pytest.raises(FormatError):
        parse_agent_output(AGENT_OUTPUT.format(line=line))


# --- 3. fechas --------------------------------------------------------------------------------


def _touch(folder, stem):
    (folder / f"{stem}.md").write_text("# informe", encoding="utf-8")


def test_previous_reports_order_numbered_passes_numerically_not_alphabetically(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    for stem in ["2026-10-15-informe-10", "2026-10-15-informe-2", "2026-10-15-informe",
                 "2026-09-30-informe-3", "2026-10-16-informe"]:
        _touch(folder, stem)
    names = [p.name for p in previous_reports(tmp_path, "Producto Demo")]
    assert names == ["2026-09-30-informe-3", "2026-10-15-informe", "2026-10-15-informe-2",
                     "2026-10-15-informe-10", "2026-10-16-informe"]


def test_previous_reports_ignore_dry_runs_orphan_json_and_foreign_names(tmp_path):
    folder = tmp_path / "producto-demo"
    folder.mkdir()
    _touch(folder, "2026-10-01-informe")
    _touch(folder, "2026-10-02-dry-run")
    _touch(folder, "2026-10-03-informe-copia")
    (folder / "2026-10-04-informe.json").write_text("{}", encoding="utf-8")
    assert [p.name for p in previous_reports(tmp_path, "Producto Demo")] == ["2026-10-01-informe"]


def test_impossible_date_in_a_report_is_unknown_and_reported():
    diff = diff_reports(_report(date="2026-02-30"), _report(date="2026-10-01"))
    assert diff.previous_date == "fecha desconocida"
    assert any("date" in w for w in diff.warnings)


@pytest.mark.parametrize("prev, today, stale", [
    (date(2023, 8, 31), date(2024, 2, 29), False),  # bisiesto: 31-ago + 6m = 29-feb
    (date(2023, 8, 31), date(2024, 3, 1), True),
    (date(2025, 12, 15), date(2026, 6, 15), False),  # cruza de año
    (date(2025, 12, 15), date(2026, 6, 16), True),
])
def test_six_month_staleness_across_leap_years_and_year_end(prev, today, stale):
    assert older_than_six_months(prev, today) is stale
