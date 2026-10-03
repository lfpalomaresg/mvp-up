import pytest

from mvpup.parsing import FormatError, Level, parse_agent_output


def test_parses_valid_output(valid_output):
    r = parse_agent_output(valid_output)
    assert r.score == 6
    assert [f.id for f in r.findings] == ["H1", "H2", "H3"]
    assert r.findings[0].impact is Level.ALTO and r.findings[0].effort is Level.BAJO
    assert r.quick_wins == ["Añadir pytest con un test de humo"]
    assert r.missing_data == ["Volumen real de usuarios"]
    assert r.warnings == []


def test_missing_header_is_format_error(valid_output):
    broken = valid_output.replace("## Riesgos si no se actúa", "## Riesgos")
    with pytest.raises(FormatError) as exc:
        parse_agent_output(broken)
    assert any("Riesgos si no se actúa" in p for p in exc.value.problems)


def test_decimal_comma_score(valid_output):
    r = parse_agent_output(valid_output.replace("6/10", "6,5/10"))
    assert r.score == 6.5


@pytest.mark.parametrize("bad", ["11/10", "X/10"])
def test_invalid_score_rejected(valid_output, bad):
    with pytest.raises(FormatError):
        parse_agent_output(valid_output.replace("6/10", bad))


def test_finding_without_evidence_is_dropped(valid_output):
    text = valid_output.replace("Evidencia: requirements.txt sin versiones", "Evidencia: N/D")
    r = parse_agent_output(text)
    assert [f.id for f in r.findings] == ["H1", "H3"]
    assert any("H2" in w for w in r.warnings)


def test_more_than_seven_findings_is_format_error(valid_output):
    extra = "\n".join(
        f"- [H{i}] Hallazgo {i} · Impacto: B · Esfuerzo: B · Evidencia: fichero{i}.txt"
        for i in range(4, 10)
    )
    text = valid_output.replace("## Quick wins", extra + "\n## Quick wins")
    with pytest.raises(FormatError, match="máx 7"):
        parse_agent_output(text)


@pytest.mark.parametrize(
    "header", ["## Hallazgos INVENTADOS", "## Quick winsss", "## Riesgos si no se actúa ya mismo"]
)
def test_header_with_extra_text_is_not_exact(valid_output, header):
    original = {"## Hallazgos": "## Hallazgos (máx 7, ordenados por impacto)",
                "## Quick wins": "## Quick wins (impacto A/M con esfuerzo B)",
                "## Riesgos": "## Riesgos si no se actúa"}
    for prefix, full in original.items():
        if header.startswith(prefix):
            text = valid_output.replace(full, header)
    with pytest.raises(FormatError):
        parse_agent_output(text)


def test_header_without_parenthetical_is_accepted(valid_output):
    text = valid_output.replace("## Hallazgos (máx 7, ordenados por impacto)", "## Hallazgos")
    assert len(parse_agent_output(text).findings) == 3


@pytest.mark.parametrize("ev", ["N/D (no comprobado)", "n/d - pendiente", "Sin evidencia directa"])
def test_evidence_declaring_absence_is_dropped(valid_output, ev):
    text = valid_output.replace("Evidencia: requirements.txt sin versiones", f"Evidencia: {ev}")
    assert [f.id for f in parse_agent_output(text).findings] == ["H1", "H3"]


from support import LIGERA_OUTPUT  # noqa: E402


def test_parses_ligera_output():
    from mvpup.parsing import parse_ligera_output

    r = parse_ligera_output(LIGERA_OUTPUT)
    assert r.score == 4
    assert [f.id for f in r.findings] == ["H1", "H3", "H4"]
    assert r.findings[0].effort is None
    assert r.resume_tasks == ["Desplegar el prototipo", "Actualizar la ficha", "Definir una métrica"]
    assert "Prototipo de ejemplo" in r.state


def test_ligera_requires_three_resume_tasks():
    from mvpup.parsing import parse_ligera_output

    with pytest.raises(FormatError, match="3 tareas"):
        parse_ligera_output(LIGERA_OUTPUT.replace("3. Definir una métrica\n", ""))


def test_full_output_is_not_valid_ligera(valid_output):
    from mvpup.parsing import parse_ligera_output

    with pytest.raises(FormatError):
        parse_ligera_output(valid_output)


@pytest.mark.parametrize(
    "old, new",
    [
        ("## Hallazgos (máx 7, ordenados por impacto)", "## Hallazgos (inventado)"),
        ("## Score: 6/10 (rúbrica al pie)", "## Score: 6/10 TEXTO INVENTADO"),
        ("## Score: 6/10 (rúbrica al pie)", "## Score: 6/10 (otra cosa)"),
    ],
)
def test_only_the_template_parenthetical_is_tolerated(valid_output, old, new):
    with pytest.raises(FormatError):
        parse_agent_output(valid_output.replace(old, new))


def test_score_header_without_parenthetical(valid_output):
    text = valid_output.replace("## Score: 6/10 (rúbrica al pie)", "## Score: 7,5/10")
    assert parse_agent_output(text).score == 7.5


def test_ligera_needs_at_least_three_findings():
    from mvpup.parsing import parse_ligera_output

    two = "\n".join(
        ln for ln in LIGERA_OUTPUT.splitlines() if not ln.startswith(("- [H3]", "- [H4]"))
    )
    with pytest.raises(FormatError, match="entre 3 y 5"):
        parse_ligera_output(two)


def test_ligera_with_fewer_than_three_evidenced_findings_is_invalid():
    from mvpup.parsing import parse_ligera_output

    text = LIGERA_OUTPUT.replace("Evidencia: falta LICENSE en la raíz", "Evidencia: N/D")
    with pytest.raises(FormatError, match="con evidencia"):
        parse_ligera_output(text)


def test_header_with_extra_inner_whitespace_is_invalid(valid_output):
    text = valid_output.replace("## Riesgos si no se actúa", "## Riesgos  si no se actúa")
    with pytest.raises(FormatError):
        parse_agent_output(text)


def test_h3_subheading_does_not_cut_section(valid_output):
    text = valid_output.replace(
        "- [H2]", "### Detalle\n- [H2]"
    )
    assert [f.id for f in parse_agent_output(text).findings] == ["H1", "H2", "H3"]


from mvpup.dimensions import Dimension as D  # noqa: E402
from mvpup.parsing import GROUP_SEPARATOR, parse_grouped_output  # noqa: E402


def _grouped(a: str, b: str) -> str:
    return f"{GROUP_SEPARATOR}comercial\n{a}\n{GROUP_SEPARATOR}marketing\n{b}"


def test_grouped_output_attributes_scores_per_dimension(valid_output):
    text = _grouped(valid_output.replace("6/10", "4/10"), valid_output.replace("6/10", "8/10"))
    r = parse_grouped_output(text, (D.COMERCIAL, D.MARKETING))
    assert r[D.COMERCIAL].score == 4 and r[D.MARKETING].score == 8


@pytest.mark.parametrize(
    "mutate, msg",
    [
        (lambda t: t.replace(f"{GROUP_SEPARATOR}marketing", f"{GROUP_SEPARATOR}comercial"), "duplicado"),
        (lambda t: t.replace(f"{GROUP_SEPARATOR}marketing", f"{GROUP_SEPARATOR}legal"), "no pedido"),
        (lambda t: t.replace(f"{GROUP_SEPARATOR}marketing", f"{GROUP_SEPARATOR}astros"), "desconocida"),
        (lambda t: t.replace("## Riesgos si no se actúa", "## Riesgos", 1), "comercial: falta"),
    ],
)
def test_grouped_output_errors(valid_output, mutate, msg):
    with pytest.raises(FormatError, match=msg):
        parse_grouped_output(mutate(_grouped(valid_output, valid_output)), (D.COMERCIAL, D.MARKETING))


def test_single_dimension_without_separator(valid_output):
    assert parse_grouped_output(valid_output, (D.TECNICA,))[D.TECNICA].score == 6
