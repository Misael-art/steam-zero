# Final whole-branch review — lote de coesao visual e botoes reais

- Repo: `/home/misael/Projects/Steam Zero/Canonical/2026-09-21`
- Branch: `codex/jornada-fisica-bateria-2026-10-12` — HEAD `6dab8dd6`
- Range reviewed: `2b7eb541b4a54f0930927a2b0f92cb45776ae4c7..6dab8dd6` (43 commits, packaged diff 60.181 lines)
- Role: final reviewer read-only; controller integrates. Contract respected: no file mutations in the tree, no git state changes, no GUI, tests not run.

## Scope — what was read

| Chunk (packaged diff) | Status | Note |
|---|---|---|
| `.github/workflows/ci.yml` @514–553 | READ | Infra fix d55b1397: conditional `pacman -Syu` only when ldconfig misses libsqlite; adjudicated in ledger (no active front claims the workflow; §5 requires a green push-run). Consistent with ACTIVE-WORK. |
| 2026-10-12 evidence `2026-10-12-jornada-fisica-2b7eb541b4a5` @606–20314 | PARTIAL | Bulk is binary captures + prior-round logs; README verdict table, logs/14 and baseline hashes verified from tree (d7c114f9 / 2a37d09a / 81d313df == sha256 in `logs/14-verificacao-final.txt:39-41`; residues honestly disclosed). |
| lote logs 22–28 @21942–22505 | READ | Full read. Log 24 `qml exitCode=124` RESOLVED: `tools/release_host.py:1432-1438` defines 124 (timeout of a GUI that stayed alive the whole 5s window) as the PASS path (`state:"started"`, journal `smokes-passed` at :2100-2108). Not an undisclosed failure. |
| 2026-10-15 round @22506–22835 + logs | READ (key logs via tree) | README honest verdicts; logs 16/17/18/21-delta-final/21-s5-rodape verified: incident loop ends at `7eddd0aa…`, restoration to `d7c114f9…`==baseline certified by hand-2 measurement with the log gap explicitly disclosed; privacy removal S5-6 + orphan manifest line disclosed; focus-race contamination disclosed. |
| ACTIVE-WORK @50076–50098, STATUS @50103–50161, WORKLOG @50162–50213 | READ | Append-only WORKLOG honored; both rounds' claims cross-checked against logs above. |
| Plan body @50355–51163 | SKIPPED | Read in full from tree (`docs/diagnostics/2026-10-13-HANDOFF-...md`); unchanged semantics. |
| COVERAGE @51163–51282 + status items @51282–52624 | READ | 41 digest renewals are hash-only; new items `SZ-EMULATION-KEYS-IMPORT-UNIFICATION` and `SZ-LOTE-COESAO-UI` fully read — no axis promoted (planned/none/blocked), gaps and residuals registered honestly, evidence cites file:line measurements. |
| Workstream cards @52625–52741 | READ | New lote + jornada-fisica cards; donor cards JCT/JLS/JPP carry the mirrored cessões (5a/5b/5c/6/7/8-scoped). |
| `src/**` @52742–55348 | READ (full) | Correctness, error semantics (fail-closed), boundary and injection surface reviewed; no command/SQL injection, socket peer-UID check, path handling and token/secret hygiene clean. |
| `tests/**` @55349–60181 | READ (full) | Test-integrity focus: no assertion weakened anywhere; every re-pin is a measured contract change (D-28 vocabulary; D-10 font-metric re-pin with documented 866<876). Anti-vacuous guards (`_MEASUREMENT_PASS`, `_TOTALS`, FAIL!-absence, returncode, non-vacuity meta-tests in D-10/WCAC/contrast gates) intact and in two cases strengthened (`test_ui_selected_label_contrast` both-direction pins; WCAG gate with `KNOWN_OPEN_AT_MEASURED={}`). |
| Binary captures (png/whl) | SKIPPED | Not text-reviewable; hash-pinned in manifests instead. |
| Ledger `progress.md` + rulings P1–P17 | READ | Basis for adjudicating all deferred minors below. |

## Findings

### Critical — none

### Important

**I-1. Eight files edited under three other ACTIVE fronts' `exclusivePaths` with no cessão (serial handoff) registered anywhere; the card's completeness claim is false at HEAD.**
- Files (branch diff `2b7eb541..6dab8dd6`, 341 insertions, verified by `git diff --stat`):
  - WS-2026-10-JOURNEY-LAUNCHER-SESSION exclusivePaths: `src/steamzero/adapters/desktop_dashboard.py`, `src/steamzero/domain/scene_surfaces.py`, `src/steamzero/schemas/scene-surfaces-v1.schema.json`, `tests/unit/test_scene_surfaces.py`, `tests/unit/test_session_overlay_adapter.py`, `tests/unit/test_session_peripherals.py` (edits in aa65f5f7 D-27, 1ba96588/75a1c5fb D-28, d8c5205d D-20, b1289752 D-23)
  - WS-2026-10-JOURNEY-COMPLETE-TEMPLATE: `src/steamzero/adapters/desktop_contracts.py` (aa65f5f7 D-27 `_action("requirements.verify", ...)` publication)
  - WS-2026-10-STUDIO-DRAFT-HISTORY: `tests/qml/check_theme_editor_asset_recipes.qml` (75a1c5fb fixture re-sync `volume`→`swapDisc`)
- Evidence: parsing every active card's `exclusivePaths` at HEAD attributes each file as shown above; searching all five involved cards' `nextAction` (lote card handoffs (1)–(8) included) finds NONE of the 8 paths ceded. Yet `docs/status/workstreams/lote-coesao-ui-2026-10-13.json:21` asserts "Com as seis linhas de cessao, o mapa inteiro … tem cada defeito alcancado por uma linha que nomeia a frente dona dos paths que a tarefa toca" — false for D-27 contract-side and D-28 core, and the WORKLOG/ACTIVE-WORK repeat the six-lines framing. AGENTS §2 requires the serial handoff prose before editing another front's exclusive path (the (5a)–(6) line proves the mechanism was understood and used elsewhere, including a retrospective variant authorized by the operator).
- Mitigation already present: substance was operator-endorsed per-task (ledger Rulings for Task 6 unit 6b, Task 7/7b scope); no code harm; donor JCT/JLS/JPP cards were themselves edited for the 5-series paths, so the mechanism exists.
- Concrete fix: before/at merge, lavrar cessão lines in the three donor cards (and the lote card) naming these 8 paths with origem/destino/base/escopo/devolucao — mirroring the (5a)–(5c) wording — and correct the lote card's completeness sentence (or replace it with a pointer to a residual list in the Tarefa 15 matrix) so the claim matches the registered set.

### Minor — functional/test

**M-1. `src/steamzero/adapters/session_control.py:652-662`** — `_refuse_if_not_live` labels `E-SESSION-CHANNEL-SUSPENDED` ("A sessão está suspensa" family) even when `current is None` (session already gone, not suspended). Fail-closed is correct; the diagnosis can mislead in the narrow race. Fix: branch the detail (suspended vs. no live session) while keeping one error id, or add `state` to the refusal. [deferred from T2]

**M-2. `src/steamzero/adapters/session_control.py:454-473`** — single `try` covers read → `_dispatch` → `sendall` with one `except OSError` logged as "client disappeared"; an OSError raised inside `_dispatch` (e.g. state-store failure) is mislabeled and the client silently eats its 1 s timeout. Behavior is strictly better than pre-fix; log/diagnosability only. Fix: split `sendall` from `dispatch` in separate try blocks with distinct log messages. [deferred from T3(a)]

**M-3. `src/steamzero/adapters/emulation.py:5012-5034`** — `verify_requirements(platform_id)` echoes the parameter but always filters `_SWITCH_EMULATOR_IDS`; `platform_id="ps5"` would return a switch verdict tagged `platform: "ps5"`. Fix: drop the parameter, or enforce/short-circuit non-switch platforms with an explicit unsupported verdict. [deferred from T6(a)]

**M-4. Slot-range phrase duplicated as literals** — `src/steamzero/adapters/session_control.py:42` (constant), `src/steamzero/launcher/journey_runtime.py:450`, `src/steamzero/adapters/launcher_ui.py:484` + variant at `:784`; the D-20 unification pins message equality across copies. Fix: import the constant at both other sites and reconcile the `:784` variant. [deferred from T5(a)]

**M-5. `tests/unit/test_session_control.py:613-621, 787-810`** — `test_refused_save_state_declares_exists_when_the_file_landed` creates/unlinks a file under the REAL user data home (`paths.saves_dir()/states/Mesen/…state1`); the checkpoint's state-home protection snapshot covers `~/.local/state`, so a stray `Mesen/` dir from `mkdir(parents=True)` would go unnoticed. Fix: monkeypatch `paths.saves_dir` to `tmp_path` in this test. [deferred T4-adjacent]

**M-6. `tests/unit/test_theme_token_contrast.py:40`** — `luminance()` compares `c <= 0.03928` on the raw 0..255 scale (threshold applies only for channel value ≤ 0), diverging from the correct normalized form used at `src/steamzero/domain/dynamic_palette.py:58`. No measured token falls in the affected dark band (margins reported at 3,0 + 0,003–0,006), but the gate should share the domain formula. Fix: import or mirror `dynamic_palette` normalization. [deferred from T8]

**M-7. `tests/unit/test_ui_selected_label_contrast.py:82`** — `test_no_fixed_choice_would_work_for_every_theme` is now literally false (fixed background clears AA in all 4 packaged themes post-D-29). Renaming was deferred (tests/ frozen in Fase 1) and is tracked in `SZ-LOTE-COESAO-UI` nextAction + STATUS. Fix: rename at T15/checkpoint. [deferred from T9]

**M-8. `src/steamzero/domain/scene_layout.py:64,69`** — GLYPHS keeps `achievement`/`network` entries although D-28 retired those OSD actions; no dead-key guard covers this map (the demo-theme orphan check does not). Fix: remove the orphan keys or extend the T7 invariant to glyph sources. [deferred from T7]

**M-9. `tests/unit/test_scene_surfaces.py` (schema-enum test)** — uses frozenset equality only; a `pytest.raises(ValidationError)` on `items=["brightness"]` would make the schema gate self-evident. Optional hardening, non-blocking. [deferred from T7b]

**M-10. `tests/unit/test_session_control.py` vanished-client test** — wall-clock margins (0.3 s handler / 0.6 s wait / 1.0 s timeout) give a rare flake risk on loaded runners. [deferred from T3(b)]

**M-11. `src/steamzero/adapters/session_control.py` `_possible_save_write`** — swallows the probe cause without any log line; a `logging.debug` would aid field diagnosis of `exists` refusals. [deferred from T4(c)]

**M-12. `src/steamzero/adapters/emulation.py:5022-5026` vs `:732-740`/`:795-800`** — 4-line readiness composition duplicated; extract helper when a third caller appears (rule of three already reached — track, do not churn now). [deferred from T6(b)]

### Minor — UX/product-call (from T7, non-blocking)

**M-13.** `list*` OSD buttons tap only triggers refresh (no surface opener — product call); suspended state shows double "Retomar" (pause-relabeled + resume); `rewind` label "Rebobinar" overpromises vs. 1-frame/press ("Rebobinar um quadro" suggested); ephemeral commands each pay `STATE_COMMAND_SETTLE_SECONDS` (watch tap latency on hardware). Belongs to T15 matrix, not a code defect.

### Minor — governance/evidence hygiene

**M-14.** 2026-10-15 round log numbering collision: `logs/21-delta-final.txt` and `logs/21-s5-rodape.md` share index 21 (`README.md:81` cites both). Renumber or document the prefix convention.

**M-15.** Capture `capturas/S5-2-rodape-sessao-ativa.png` shows the footer with NO active session; the name contradicts the content, though `README.md:33` and `logs/21-s5-rodape.md` disclose the reality in full. Rename at next touch.

**M-16.** `docs/09-operations/evidence/2026-10-13-lote-coesao-ui/logs/03-decisao-d23.md:72` keeps the stale line "canal vive dentro da arvore suspensa" in the 3b-rejection section, superseded only by an appended correction; add an inline pointer. [deferred from T3(c)]

**M-17.** `src/steamzero/themes/org.steamzero.asset-recipes-demo/theme.json:170` `dynamicPalette.fallback.darkVibrant:#0e7490` is outside the 11 pins and the WCAG gate (seed, not `tokens.color`); ledger already says to add it to the T15 structural-debt list so a future census does not "rediscovers" it. [deferred from T9]

**M-18.** Harness noise: one added `console.info` in a QML harness (T2) and pre-existing gallery-thumbnail `QNetworkReply` stderr (T5(c)) — cosmetic; confirm the offscreen gate tolerates both (checkpoint logs show it does).

## Verified clean (no findings)

- **Test integrity (focus 1):** all 43 commits' test edits assert strictly more or newly; the only two reversals (D-10 metric re-pin, selected-label contrast both-direction pins) are documented with measurements; no golden relaxed; `xfail(strict)` correctly converted to PASS with anti-vacuous guards; the new emulation-controller gate genuinely compares `requirements.verify`/`firmware.import` and the keys.import exclusion is honestly registered (item + STATUS + COVERAGE + logs/08 with file:line measurements).
- **Fail-closed semantics:** channel refusal before `connect` (`connections == []` proven), listener survives BrokenPipe, `os.killpg` with start_ticks/(pgid,sid) re-verification before SIGCONT, recycled-PID refusals, D-26 `written={slot,path,exists}` never claims more than observed, `_pending_game` fallback bounded to the bridge-launched game and cleared on notStarted/terminal (`launcher_ui.py:601,1270,1440,1465`).
- **Security/privacy:** peer-UID check on the AF_UNIX channel, no secrets/tokens in committed evidence, personal paths are the established convention; `/launch` 409 exposes structured diagnostic without leaking exception text.
- **D-10 golden (focus 5):** GridLayout 6/3 columns + wrapMode matches an environment-independent objective harness (no elide, no clip, wrap, height ≥ implicit, in-window, six session actions in the payload); CI failure root cause (font metrics 866<876) re-pinned with documented stress evidence.
- **Boundaries (focus 2):** `make independence boundaries` green at checkpoint (logs/17) and no `phasezero` prefixes introduced; the ownership-style violation is captured as I-1.
- **Status governance (focus 3):** digest renewals hash-only and tool-generated on the frozen tree; no axis promoted anywhere; item `operation=blocked` matches the authorization reality.
- **`logs/24 qml exitCode=124`** — by-design pass signal of `release_host.py` smoke (`exitCode != 124` raises); WORKLOG claim "instalacao governada convergiu" is accurate. Not a finding.

## Summary

- Critical: 0
- Important: 1 (I-1 unregistered exclusivePaths edits + false completeness claim — governance/claim fix at merge, code substance endorsed per-task)
- Minor: 18 (M-1…M-18; all carry concrete fixes, most are already on the Tarefa 15 open list)

VERDICT: APPROVE_WITH_FINDINGS
