# MVP-UP 🚀

**A multi-agent product-scaling orchestrator for Claude Code.**
It audits any product, project or service across **10 dimensions**, runs the agents
in parallel, consolidates the findings into an **impact × effort matrix** and returns
a **prioritized scaling roadmap**. Re-run it and it compares with the previous pass
and **measures your progress**. It is a loop, not a snapshot.

> Status: v1.1 methodology (calibrated on 11 real projects) + Python implementation
> 0.2.0 (green test suite, strict mypy, zero runtime dependencies, MIT).

## The problem

When you build a product it is easy to improve only what you enjoy improving — code,
design — while pricing, legal, analytics or the sales process stay at zero. MVP-UP
forces you to look at the **whole board at once** and tells you where the next
highest-leverage point is.

## Principles

1. **Analysis only.** Agents never modify anything: no files, no commits, no paid APIs.
2. **The human authorizes.** MVP-UP diagnoses and proposes a TOP-5; you decide what runs.
3. **Evidence or nothing.** Every finding cites its proof (file, URL, datum). Economic
   figures without a source are marked N/D — they are never invented.
4. **Loop, not snapshot.** Reports are versioned by date; each re-audit shows the Δ of
   every score and which actions from the previous roadmap were done (or ignored).
5. **Cost-aware.** Always triggered manually. Three modes: *express* (3-5 dimensions for
   the current stage), *full* (all 10, requires confirmation) and *light* (one agent for
   seeds, utilities and frozen projects).

## The 10 dimensions

| # | Dimension | What it looks at |
|---|---|---|
| 1 | Technical | Code, architecture, tech debt, tests, does it hold 10×? |
| 2 | Security | Credentials, auth, inputs, rate limiting, CVEs |
| 3 | Legal | GDPR, notices, cookies, IP, contracts, licenses |
| 4 | Product / UX | Value proposition in 5 seconds, friction, onboarding, feature creep |
| 5 | Commercial | Offer, pricing, guarantees, channels, repeatable sales process |
| 6 | Marketing & hype | Positioning, ICP, content engine, social proof, narrative |
| 7 | Market | Niche, competitors with prices, real gap, trends, risks |
| 8 | Economics | Recurring costs, unit margin, break-even, revenue |
| 9 | Operations | Founder dependency, documented processes, support, automatable work |
| 10 | Data & measurement | Analytics, the 3-5 metrics that matter, feedback loop |

## Install

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev,anthropic]"
```

Requires Python ≥ 3.11. The core has **no runtime dependencies**; `anthropic` is an
optional extra used only by the real runner. As a Claude Code skill:

```bash
cp -r skill ~/.claude/skills/strategy-mvp-up
```

Read the *Adaptation* section of `README.md` before installing the skill: the original
references the author's own knowledge folder and helper skills.

## Usage

```bash
# Plan: no network, no cost. Shows selection, batches and a cost hint.
mvpup plan --product "My product" --stage mvp --objective ingresos --show-prompts

# Dry run: the whole pipeline with synthetic agents. No API key, no cost.
mvpup run --product "My product" --stage mvp --objective ingresos --dry-run

# Real run (Sonnet by default; expensive models are policy-blocked)
mvpup run --product "My product" --stage mvp --objective ingresos --repo ~/code/my-product

# Later passes
mvpup compare informes/my-product/2026-10-01.md informes/my-product/2026-11-01.md
mvpup html informes/my-product/2026-11-01.md
```

See [`examples/`](examples) for a real dry-run report (synthetic data, fictional product).

## How it works

```
INTAKE → agents in parallel → consolidation (weighted score, impact × effort)
       → roadmap (H1 week / H2 month / H3 quarter) → comparison → report
```

`plan` is deterministic and offline; `run` needs an API key and a snapshot of the repo;
`compare` and `html` work only with the saved reports.

## Safety properties

| Property | Where |
|---|---|
| Agents have **no tools**: they read a read-only snapshot | `anthropic_runner.repo_snapshot` |
| Snapshot does not follow symlinks and skips secret-looking files | `anthropic_runner` |
| Secrets are redacted (`api_key=…`, `"token": "…"`, credentials in URLs) | `redaction.py` |
| Fail-closed parser: unknown format → retry once → "not evaluated", never a guessed score | `parsing.py` |
| `--repo` must be a real directory (no symlink) | `cli.check_repo_path` |
| Inside a git repo, the report folder must be `.gitignore`d or nothing is written | `cli.check_out_dir` |
| Model policy: only allowed models; expensive ones need explicit confirmation | `config.py` |

Redaction is *best-effort*: do not audit a repo with exotic hard-coded secrets without
reviewing it first.

## Development

```bash
.venv/bin/python3 -m pytest -q            # suite completa en verde
ruff check src tests                      # red mínima: E, F, W, I, B
mypy --check-untyped-defs src             # strict in pyproject
```

`tests/test_typing.py` is the type gate; `tests/test_actions.py` checks the prompts
against `skill/references/dimensiones.md` and `tests/test_report.py` checks the report
against its template. All tests use fictional data.

## License

MIT. See [LICENSE](LICENSE).
