"""Reparto del presupuesto de la instantánea por categorías. Repos y valores FICTICIOS."""

from types import SimpleNamespace

import pytest

from mvpup.anthropic_runner import (
    FILE_MAX_CHARS,
    SNAPSHOT_MAX_CHARS,
    AnthropicRunner,
    SnapshotCategory,
    SnapshotProfile,
    classify,
    repo_snapshot,
    snapshot_profile,
    snapshots_for_tasks,
)
from mvpup.dimensions import Dimension as D
from mvpup.selection import AgentTask

FAKE_KEY = "sk-" + "ant-" + "q" * 40  # ficticia, construida por concatenación
FAKE_VALUE = "valor" + "inventado" + "987654"


def _write(root, rel, text):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def doc_heavy_repo(tmp_path):
    """Como el repo de la primera pasada real: 34 documentos largos y poco código."""
    _write(tmp_path, "README.md", "# Producto ficticio\nMARCA-README\n")
    _write(tmp_path, "STATUS.md", "MARCA-STATUS\n")
    _write(tmp_path, "docs/ARCHITECTURE.md", "MARCA-ARQUITECTURA\n")
    _write(tmp_path, "package.json", '{"name": "demo-ficticia"}\n')
    for i in range(34):
        _write(tmp_path, f"docs/{i:02d}_DOCUMENTO.md", f"MARCA-DOC-{i:02d}\n" + "relleno documental\n" * 600)
    _write(tmp_path, "src/app/api/audits/route.ts", "export async function POST() {} // MARCA-RUTA-API\n")
    _write(tmp_path, "src/lib/rateLimit.ts", "export const limit = 15 // MARCA-LIB\n")
    _write(tmp_path, "supabase/migrations/0001_init.sql", "create table audits (id uuid); -- MARCA-MIGRACION\n")
    _write(tmp_path, "src/app/page.tsx", "export default function Page() {} // MARCA-PAGINA\n")
    _write(tmp_path, ".github/workflows/ci.yml", "name: ci # MARCA-CI\n")
    _write(tmp_path, "tests/audits.test.ts", "test('x', () => {}) // MARCA-TEST\n")
    return tmp_path


@pytest.fixture
def big_repo(doc_heavy_repo):
    """Además de los 34 documentos, código de sobra para agotar cualquier cuota."""
    for i in range(60):
        _write(doc_heavy_repo, f"src/lib/modulo{i:02d}.ts", f"// MARCA-MODULO-{i:02d}\n" + "c" * 3000)
    return doc_heavy_repo


@pytest.mark.parametrize("profile", list(SnapshotProfile))
def test_source_code_reaches_the_snapshot_even_with_many_long_docs(doc_heavy_repo, profile):
    snap = repo_snapshot(doc_heavy_repo, profile=profile)
    for mark in ("MARCA-README", "MARCA-STATUS", "MARCA-ARQUITECTURA", "MARCA-RUTA-API",
                 "MARCA-LIB", "MARCA-MIGRACION", "MARCA-PAGINA", "MARCA-CI"):
        assert mark in snap, f"{mark} ausente con perfil {profile.value}"
    assert len(snap) <= SNAPSHOT_MAX_CHARS


def test_each_profile_spends_its_budget_on_what_its_agent_needs(big_repo):
    code = repo_snapshot(big_repo, profile=SnapshotProfile.CODE)
    docs = repo_snapshot(big_repo, profile=SnapshotProfile.DOCS)
    assert 0 < code.count("MARCA-DOC-") < docs.count("MARCA-DOC-") < 34  # los docs tienen tope propio
    assert 0 < docs.count("MARCA-MODULO-") < code.count("MARCA-MODULO-") < 60
    for snap in (code, docs):  # lo esencial entra con cualquier perfil, aunque el repo desborde
        for mark in ("MARCA-README", "MARCA-RUTA-API", "MARCA-MIGRACION", "MARCA-PAGINA", "MARCA-CI", "MARCA-TEST"):
            assert mark in snap
        assert len(snap) <= SNAPSHOT_MAX_CHARS


def test_header_line_counts_included_per_category_and_omitted_by_budget(doc_heavy_repo):
    snap = repo_snapshot(doc_heavy_repo, profile=SnapshotProfile.CODE)
    header = next(ln for ln in snap.splitlines() if ln.startswith("Incluidos/candidatos"))
    assert "núcleo 4/4" in header  # README, STATUS, ARCHITECTURE y package.json
    assert "código 4/4" in header
    assert "configuración 1/1" in header
    assert "tests 1/1" in header
    n_docs = snap.count("MARCA-DOC-")
    assert f"documentación {n_docs}/34" in header
    assert f"omitidos por presupuesto: {34 - n_docs}" in header
    assert "perfil código" in snap.split("\n", 1)[0]


def test_files_omitted_by_budget_are_listed_as_not_read(doc_heavy_repo):
    snap = repo_snapshot(doc_heavy_repo, profile=SnapshotProfile.CODE)
    assert "NO se han leído" in snap  # el agente no debe puntuar sobre lo que no vio


def test_unused_quota_is_not_wasted(tmp_path):
    """Sin código ni tests, su cuota pasa a los documentos: no se deja presupuesto sin usar."""
    for i in range(30):
        _write(tmp_path, f"docs/{i:02d}.md", f"MARCA-DOC-{i:02d}\n" + "x" * 9000)
    snap = repo_snapshot(tmp_path, profile=SnapshotProfile.CODE)
    assert snap.count("MARCA-DOC-") >= 10  # con solo la cuota de docs del perfil código cabrían 1-2
    assert len(snap) <= SNAPSHOT_MAX_CHARS


def test_api_routes_do_not_starve_lib_and_schema(tmp_path):
    """Dentro del código se rota entre rutas API, lib y esquema: ninguna carpeta se lo come todo."""
    for i in range(60):
        _write(tmp_path, f"src/app/api/r{i:02d}/route.ts", f"// MARCA-API-{i:02d}\n" + "a" * 3000)
    _write(tmp_path, "src/lib/core.ts", "// MARCA-LIB\n")
    _write(tmp_path, "db/migrations/001.sql", "-- MARCA-SQL\n")
    snap = repo_snapshot(tmp_path, max_chars=40_000, profile=SnapshotProfile.CODE)
    assert "MARCA-LIB" in snap and "MARCA-SQL" in snap and "MARCA-API-00" in snap
    assert snap.count("MARCA-API-") < 60


def test_per_file_cap_still_applies(tmp_path):
    _write(tmp_path, "src/lib/big.py", "y = 2\n" * 10_000 + "MARCA-FINAL\n")
    snap = repo_snapshot(tmp_path)
    assert "MARCA-FINAL" not in snap and "[... recortado ...]" in snap
    assert snap.count("y = 2") <= FILE_MAX_CHARS // len("y = 2\n") + 1


def test_lockfiles_never_spend_budget(tmp_path):
    _write(tmp_path, "package-lock.json", '{"MARCA-LOCK": 1}\n' * 500)
    _write(tmp_path, "app.py", "print('MARCA-APP')\n")
    snap = repo_snapshot(tmp_path)
    assert "MARCA-APP" in snap and '"MARCA-LOCK"' not in snap


@pytest.mark.parametrize("rel, category", [
    ("README.md", SnapshotCategory.CORE),
    ("STATUS.md", SnapshotCategory.CORE),
    ("docs/ARCHITECTURE.md", SnapshotCategory.CORE),
    ("pyproject.toml", SnapshotCategory.CORE),
    ("packages/web/README.md", SnapshotCategory.DOCS),  # solo el README raíz es núcleo
    ("docs/16_OFERTA.md", SnapshotCategory.DOCS),
    ("src/app/api/x/route.ts", SnapshotCategory.SOURCE),
    ("src/lib/db.ts", SnapshotCategory.SOURCE),
    ("supabase/migrations/0001.sql", SnapshotCategory.SOURCE),
    (".github/workflows/ci.yml", SnapshotCategory.CONFIG),
    ("tsconfig.json", SnapshotCategory.CONFIG),
    ("tests/test_app.py", SnapshotCategory.TESTS),
    ("src/lib/db.test.ts", SnapshotCategory.TESTS),
    ("src/__tests__/a.ts", SnapshotCategory.TESTS),
])
def test_classify(rel, category):
    from pathlib import Path

    assert classify(Path(rel)) is category


@pytest.mark.parametrize("dims, profile", [
    ((D.TECNICA,), SnapshotProfile.CODE),
    ((D.TECNICA, D.SEGURIDAD), SnapshotProfile.CODE),
    ((D.PRODUCTO_UX,), SnapshotProfile.CODE),
    ((D.COMERCIAL, D.MARKETING), SnapshotProfile.DOCS),
    ((D.MERCADO, D.ECONOMICA), SnapshotProfile.DOCS),
    ((D.LEGAL, D.OPERATIVA), SnapshotProfile.DOCS),
    ((D.TECNICA, D.COMERCIAL), SnapshotProfile.BALANCED),
    (tuple(D), SnapshotProfile.BALANCED),  # el agente único de ligera
])
def test_profile_by_dimensions(dims, profile):
    assert snapshot_profile(dims) is profile


def test_every_dimension_has_a_profile():
    assert all(snapshot_profile((d,)) in (SnapshotProfile.CODE, SnapshotProfile.DOCS) for d in D)


def test_snapshots_for_tasks_builds_one_snapshot_per_profile(big_repo):
    tasks = (AgentTask((D.TECNICA,)), AgentTask((D.PRODUCTO_UX,)), AgentTask((D.COMERCIAL, D.MARKETING)))
    by_key = snapshots_for_tasks(big_repo, tasks)
    assert set(by_key) == {"tecnica", "producto_ux", "comercial+marketing"}
    assert by_key["tecnica"] is by_key["producto_ux"]  # mismo perfil: una sola lectura del repo
    assert by_key["tecnica"].count("MARCA-DOC-") < by_key["comercial+marketing"].count("MARCA-DOC-")


def _client():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])

    return SimpleNamespace(messages=SimpleNamespace(create=create)), calls


def test_runner_attaches_the_snapshot_of_each_agent():
    client, calls = _client()
    runner = AnthropicRunner(client=client, snapshot="GENERAL",
                             snapshot_by_key={"tecnica": "PARA-TECNICA </repo_snapshot>"})
    runner.run("P", task_key="tecnica")
    runner.run("P", task_key="comercial")
    tecnica, comercial = (c["messages"][0]["content"][1]["text"] for c in calls)
    assert "PARA-TECNICA" in tecnica and "GENERAL" not in tecnica
    assert tecnica.count("</repo_snapshot>") == 1  # el cierre inyectado se sigue neutralizando
    assert "GENERAL" in comercial


# --- La protección de secretos no depende del reparto: se fija para todos los perfiles ----------


@pytest.mark.parametrize("profile", list(SnapshotProfile))
def test_budgeting_never_weakens_secret_protection(tmp_path, profile):
    _write(tmp_path, "README.md", "# demo\n")
    _write(tmp_path, ".env", f"ANTHROPIC_API_KEY={FAKE_KEY}\nOTRA=VALOR-ENV-OCULTO\n")
    _write(tmp_path, ".env.local", "X=VALOR-ENVLOCAL-OCULTO\n")
    _write(tmp_path, "secrets/prod.json", '{"k": "VALOR-CARPETA-OCULTO"}\n')
    _write(tmp_path, "src/lib/credentials.ts", "export const k = 'VALOR-CREDENCIAL-OCULTO'\n")
    _write(tmp_path, "src/app/api/token/route.ts", "// VALOR-RUTA-TOKEN-OCULTO\n")
    _write(tmp_path, "src/app/api/pay/route.ts", f'const client = new Client({{ api_key: "{FAKE_VALUE}" }})\n')
    _write(tmp_path, "src/lib/keys.ts", f"export const anthropic = '{FAKE_KEY}'\n")
    _write(tmp_path, "docs/operativa.md", f"Conexión: postgres://admin:{FAKE_VALUE}@db.example.invalid/app\n")
    _write(tmp_path, "tests/test_keys.py", f'TOKEN = "{FAKE_VALUE}"\n')
    outside = tmp_path.parent / f"fuera-{profile.value}"
    outside.mkdir()
    (outside / "ajeno.ts").write_text("// VALOR-FUERA-DEL-REPO", encoding="utf-8")
    (tmp_path / "src" / "lib" / "enlace.ts").symlink_to(outside / "ajeno.ts")
    snap = repo_snapshot(tmp_path, profile=profile)
    for leaked in ("VALOR-ENV-OCULTO", "VALOR-ENVLOCAL-OCULTO", "VALOR-CARPETA-OCULTO",
                   "VALOR-CREDENCIAL-OCULTO", "VALOR-RUTA-TOKEN-OCULTO", "VALOR-FUERA-DEL-REPO",
                   FAKE_KEY, FAKE_VALUE):
        assert leaked not in snap, f"fuga de {leaked!r} con perfil {profile.value}"
    assert "[REDACTADO]" in snap
    assert "excluidos por posible secreto" in snap
    # Los excluidos por secreto no aparecen ni como candidatos ni como omitidos por presupuesto.
    header = next(ln for ln in snap.splitlines() if ln.startswith("Incluidos/candidatos"))
    assert "código 2/2" in header and "omitidos por presupuesto: 0" in header


def test_secret_helpers_are_the_shared_ones():
    """El reparto reutiliza `is_secret_file` y `redact`: no hay una segunda lista más laxa."""
    from mvpup import anthropic_runner, redaction

    assert anthropic_runner.redact is redaction.redact
    assert anthropic_runner.is_secret_file(".env") and anthropic_runner.is_secret_file("a/secrets/b.json")
    assert anthropic_runner.is_secret_file("src/api_token.ts")


def test_a_secret_straddling_the_per_file_cut_does_not_leak_partially(tmp_path):
    """Se redacta ANTES de recortar: un recorte no puede dejar media clave sin reconocer."""
    _write(tmp_path, "src/lib/largo.ts", "x" * (FILE_MAX_CHARS - 12) + " " + FAKE_KEY + "\n")
    snap = repo_snapshot(tmp_path)
    assert "sk-" + "ant-" + "qq" not in snap


def test_cli_builds_the_real_runner_with_one_snapshot_per_agent(big_repo, tmp_path_factory, monkeypatch):
    """Sin red: el cliente de la API no se crea hasta la primera llamada, que aquí no ocurre."""
    from mvpup import cli
    from mvpup.selection import build_plan

    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))  # sin .env que cargar
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-ficticia-de-test")
    args = cli.build_parser().parse_args([
        "run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos", "--repo", str(big_repo),
    ])
    intake = cli._intake(args)
    plan = build_plan(intake)
    runner = cli._runner(args, intake, plan)
    assert set(runner.snapshot_by_key) == {t.key for t in plan.tasks}
    tecnica = runner.build_content("P", "tecnica")[1]["text"]
    comercial = runner.build_content("P", "comercial+marketing")[1]["text"]
    assert "perfil código" in tecnica and "perfil documentación" in comercial
    assert "MARCA-RUTA-API" in tecnica and "MARCA-RUTA-API" in comercial


def test_cli_ligera_agent_also_gets_its_snapshot(doc_heavy_repo, tmp_path_factory, monkeypatch):
    """El agente único de ligera se llama con la clave «ligera», no con la de su tarea."""
    from mvpup import cli
    from mvpup.orchestrator import LIGERA_TASK_KEY
    from mvpup.selection import build_plan

    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-ficticia-de-test")
    args = cli.build_parser().parse_args([
        "run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos", "--mode", "ligera",
        "--repo", str(doc_heavy_repo),
    ])
    intake = cli._intake(args)
    runner = cli._runner(args, intake, build_plan(intake))
    blocks = runner.build_content("P", LIGERA_TASK_KEY)
    assert len(blocks) == 2 and "MARCA-README" in blocks[1]["text"] and "MARCA-RUTA-API" in blocks[1]["text"]
    assert "perfil equilibrado" in blocks[1]["text"]


def test_an_agent_without_an_assigned_snapshot_fails_loudly_instead_of_auditing_blind():
    """Con instantáneas por agente y sin la de reserva, una clave desconocida no puede pasar en silencio."""
    client, calls = _client()
    runner = AnthropicRunner(client=client, snapshot_by_key={"tecnica": "PARA-TECNICA"})
    with pytest.raises(RuntimeError, match="sin instantánea asignada"):
        runner.run("P", task_key="comercial")
    assert calls == []  # no se llega a llamar (ni a pagar)


def test_runner_without_any_snapshot_still_works():
    """Producto sin repo (--repo ausente): no hay instantánea que exigir."""
    client, calls = _client()
    assert AnthropicRunner(client=client).run("P", task_key="comercial") == "ok"
    assert len(calls[0]["messages"][0]["content"]) == 1


# --- Careo ronda 1: el presupuesto es TOTAL y una ruta inválida no es una instantánea -----------


@pytest.mark.parametrize("max_chars", [1_000, 5_000, 20_000])
def test_total_budget_holds_even_when_tree_and_log_are_large(tmp_path, max_chars):
    for i in range(400):
        _write(tmp_path, f"src/modulos/carpeta_con_nombre_largo_{i:03d}/fichero_{i:03d}.py", "x = 1\n")
    snap = repo_snapshot(tmp_path, max_chars=max_chars)
    assert len(snap) <= max_chars
    assert "rutas más" in snap  # se dice que la estructura está recortada
    assert snap.startswith("## Instantánea")  # la cabecera de reparto nunca se sacrifica


def test_tree_is_complete_when_it_fits(doc_heavy_repo):
    snap = repo_snapshot(doc_heavy_repo)
    assert "rutas más" not in snap and "docs/33_DOCUMENTO.md" in snap.split("## git log")[0]


@pytest.mark.parametrize("kind", ["missing", "file", "symlink"])
def test_cli_refuses_an_invalid_repo_before_building_any_runner(tmp_path, capsys, monkeypatch, kind):
    """Antes se lanzaban (y pagaban) los agentes con el texto «(ruta no encontrada…)» como repo."""
    from mvpup import cli

    real = tmp_path / "real"
    real.mkdir()
    target = tmp_path / "repo"
    if kind == "file":
        target.write_text("no soy un directorio", encoding="utf-8")
    elif kind == "symlink":
        target.symlink_to(real, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-ficticia-de-test")

    def never(*a, **kw):
        raise AssertionError("no debe construirse ningún runner")

    monkeypatch.setattr("mvpup.anthropic_runner.AnthropicRunner", never)
    code = cli.main(["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos",
                     "--repo", str(target), "--out", str(tmp_path / "informes")])
    assert code == 2
    assert "--repo" in capsys.readouterr().err
    assert not (tmp_path / "informes").exists()


# --- Careo ronda 2 -----------------------------------------------------------------------------


def test_git_log_has_its_own_budget(tmp_path):
    """Diez asuntos de commit enormes no pueden comerse la instantánea."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for i in range(10):
        _write(tmp_path, f"f{i}.py", f"x = {i}\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=demo@example.invalid", "-c", "user.name=Demo",
                        "commit", "-q", "-m", f"commit {i} " + "asunto muy largo " * 300], check=True)
    max_chars = 30_000
    snap = repo_snapshot(tmp_path, max_chars=max_chars)
    log = snap.split("## git log --oneline -10\n", 1)[1].split("\n\n## Fichero:", 1)[0]
    assert len(log) <= max_chars // 10
    assert "recortado por presupuesto" in log
    assert "x = 9" in snap  # y por eso los ficheros siguen entrando


@pytest.mark.parametrize("extra", [["--dry-run"], ["--runner", "fake", "--fake-responses", "r.json"], []])
def test_invalid_repo_is_refused_on_every_run_path_before_anything_else(tmp_path, capsys, monkeypatch, extra):
    """También con dry-run/fake, y ANTES de leer .env o pedir la API key."""
    from mvpup import cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")

    def never(*a, **kw):
        raise AssertionError("no debe leerse .env ni construirse ningún runner")

    monkeypatch.setattr("mvpup.config.load_dotenv", never)
    monkeypatch.setattr(cli, "_runner", never)
    code = cli.main(["run", "--product", "Demo", "--stage", "mvp", "--objective", "ingresos",
                     "--repo", str(tmp_path / "no-existe"), "--out", str(tmp_path / "informes"), *extra])
    err = capsys.readouterr().err
    assert code == 2 and "--repo" in err and "ANTHROPIC_API_KEY" not in err
    assert not (tmp_path / "informes").exists()
