# Web Extraction Manager

A full-stack job management system (register / list / start / stop web extraction jobs against a monthly credit allowance), built as a demonstration of **risk-based QE strategy** and **directing an AI coding agent to execute against that strategy**.

This repo is less "here's an app" and more "here's how I lead quality engineering when an agentic AI is the one typing the code."

---

## My Role: QE Lead Directing an AI Coding Agent

I did not prompt an agent to "build a job manager" and ship what came back. The workflow was strategy-first, agent-executed:

1. **Defined the test strategy before any code existed** — see [`Web Extraction Manager Strategy.md`](Web%20Extraction%20Manager%20Strategy.md). Identified the highest-risk areas up front: concurrent job-limit enforcement (race conditions on a system-wide cap), credit boundary conditions (behavior at exactly 0), and job state-transition correctness — then made the layering decision (services independent of HTTP) *because* it was the only way to unit-test business logic without a browser or a socket in the loop.
2. **Wrote a persistent operating contract for the agent** — [`CLAUDE.md`](CLAUDE.md) encodes the architecture rules, business rules, and test-layer responsibilities as a standing spec, not a one-off prompt. Every agent session reads it before touching code, which is what kept a large, multi-session build internally consistent.
3. **Directed the agent to solve testability problems, not just features.** Two examples that show up directly in the code:
   - The UI's delete flow deliberately avoids `window.confirm()` — a native browser dialog blocks Playwright automation — in favor of an inline confirm/cancel swap, so the E2E suite could drive it without hacks.
   - The 100ms job simulation uses `threading.Event().wait()` instead of `time.sleep()` specifically because unit tests patch `time.sleep` to a no-op; using `Event.wait` keeps that patch from silently breaking the async completion tests.
4. **Set the release criteria before the agent generated a single test** — five go/no-go gates (suite pass rate, coverage thresholds, individually-blocking business-rule tests, an E2E golden path, and a P0–P3 defect severity scale) codified in [`TESTS.md`](TESTS.md), so "done" was defined by risk coverage, not by test count.
5. **Reviewed AI-generated coverage with a tester's skepticism, not a rubber stamp.** The known-gaps table in [`ARCHITECTURE.md`](ARCHITECTURE.md) — the credit-deduction race condition, missing job-ownership checks, untested config boundary values — exists because I asked "what would a real QA audit flag that the green test suite hides?" and had the agent document the answer instead of quietly shipping false confidence.

The result: 131 tests across three layers, a documented risk model, and an explicit list of what's *not* covered and why — the kind of artifact a test lead produces, generated at agent speed.

---

## Test Strategy Highlights

| Layer | Purpose | Tests | Run time |
|---|---|---|---|
| Unit | Service logic in isolation — no HTTP, no browser | 52 | < 1s |
| Integration | Full HTTP request/response cycle via Flask test client | 42 | < 1s |
| E2E | Real Chromium browser via Playwright, including operator data-isolation checks | 37 | ~30s |
| **Total** | | **131** | |

**Risk-based prioritization** — the areas most likely to break in production got the most scrutiny:
- Concurrent job-limit enforcement (`USER_MAX_JOBS`, `SYSTEM_MAX_JOBS`) at the exact boundary
- Credit accounting at zero (starting a job at 0 credits, deducting past 0, confirming stop does *not* refund)
- Job state-machine transitions (only `pending` jobs can start; deleting a `running` job must cleanly abort its background thread)
- Operator data isolation (one user must never see or affect another's jobs or credits)

**Release gates** (full detail in [`TESTS.md`](TESTS.md)) — no release without all five satisfied: 100% suite pass rate, coverage thresholds enforced with `--cov-fail-under`, a named set of business-rule tests treated as individually release-blocking, a scripted E2E golden path, and zero open P0/P1 defects against a project-specific severity scale.

**Honest gaps, documented on purpose** — the thread-safety hole in credit deduction and the lack of job-ownership checks are called out explicitly rather than hidden behind a passing suite. A QE lead's job includes saying what *isn't* tested.

---

## Architecture Snapshot

Strictly layered so business logic is unit-testable without HTTP:

```
Browser (SPA)  →  API Layer (Flask Blueprints)  →  Service Layer  →  In-Memory Store
```

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask 3.x |
| UI | Plain HTML / CSS / JS — no framework, no build step |
| Browser automation | Playwright (pytest-playwright) |
| Test runner | pytest |

Full breakdown of the data model, service contracts, API error-to-status mapping, and job state machine: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Getting Started

```bash
# Activate the virtual environment (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
playwright install chromium

# Run the development server
python run.py
```

The app is served at `http://127.0.0.1:5000/`. Interactive API docs (Swagger UI) at `/apidocs/`.

---

## Running the Tests

```bash
# Unit + integration (fast, no browser)
pytest tests/unit tests/integration

# E2E (spins up a live server automatically)
pytest tests/e2e

# Coverage report
pytest tests/unit --cov=app --cov-report=term-missing
```

Full test inventory — every test class and what business rule it guards — is in [`TESTS.md`](TESTS.md).

---

## Documentation

| File | Contents |
|---|---|
| [`Web Extraction Manager Strategy.md`](Web%20Extraction%20Manager%20Strategy.md) | Testing strategy and the reasoning behind it, written before implementation |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design, layering, data model, state machine, known limitations |
| [`TESTS.md`](TESTS.md) | Full test inventory, coverage targets, release gates, defect severity scale |

---

## License

[MIT](LICENSE)
