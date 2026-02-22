# Metaculus Forecast Bot (Current-State Summary)

This repo is a practical, script-first Metaculus forecasting bot.

It:
- pulls open questions from one or more tournaments,
- does lightweight web/news research,
- prompts an LLM for forecasts,
- converts outputs into Metaculus API payloads,
- optionally submits forecast + rationale comments.

The code works end-to-end for experimentation, but it is still a monolithic prototype rather than a production-grade system.

## 1) What each main file does

- `forecasting_bot.py`
  - Core bot logic (fetch questions, research, prompt LLM, parse outputs, post forecasts/comments).
  - This is the main entrypoint for tournament or example runs.
- `asknews_research.py`
  - AskNews helper module with thread lock + rate-limit waits.
  - Designed to avoid AskNews free-tier concurrency/rate-limit issues.
- `forecast_custom_question.py`
  - Run the same forecasting logic on your own local JSON question (not from Metaculus).
  - Saves results to `test_results/`.
- `inspect_bot.py`
  - Fetches sample questions and saves forecast snapshots by question type into `forecast_types/`.
- `test.py`
  - Manual, integration-style diagnostic script for env vars, API connectivity, LLM calls, and tournament retrieval.
- `input_questions/`
  - Example custom questions for `forecast_custom_question.py`.
- `forecast_types/`, `question_types/`
  - Saved snapshots/examples from previous inspection/debug runs.

## 2) Runtime flow (how the main bot works)

When you run `forecasting_bot.py`:

1. Parse CLI args:
   - mode: `tournament` or `examples`
   - tournament(s): alias or raw ID/slug
   - submit or dry-run (`--no-submit`)
   - runs per question (`--num-runs`)
   - skip already-forecasted questions (`--skip-previous`)
2. Build question list:
   - `examples` mode uses hardcoded `EXAMPLE_QUESTIONS`.
   - `tournament` mode calls Metaculus `/posts/` and keeps open questions.
3. For each question (concurrently):
   - fetch post details,
   - decide forecast type (`binary`, `numeric`, `discrete`, `multiple_choice`),
   - run research (AskNews > Exa > Perplexity > fallback),
   - call LLM multiple times (`num_runs`),
   - aggregate outputs (median/average),
   - build API payload.
4. If submission enabled:
   - post forecast to Metaculus,
   - post rationale as a private comment.

## 3) Forecasting strategy by question type

- Binary:
  - prompt asks for rationale + final `Probability: ZZ%`.
  - parser extracts last `%` value and clamps to 1..99.
  - median across runs.
- Numeric / Discrete:
  - prompt asks for percentile table (10/20/40/60/80/90).
  - parser extracts percentile-value pairs from text.
  - `NumericDistribution` (Pydantic model) validates and interpolates to Metaculus-style CDF.
  - median CDF across runs.
- Multiple choice:
  - prompt asks for probability per option.
  - parser extracts numbers from response lines.
  - probabilities are normalized to sum to 1.
  - mean probability per option across runs.

## 4) Environment variables and secrets

Core required variables:
- `METACULUS_TOKEN` (required for question fetch + posting)
- `OPENROUTER_API_KEY` (required for LLM calls)

Research provider variables (at least one is useful):
- AskNews: `ASKNEWS_CLIENT_ID` + `ASKNEWS_SECRET`
- Exa: `EXA_API_KEY` (and optional `OPENAI_API_KEY` for `SmartSearcher`)
- Perplexity: `PERPLEXITY_API_KEY`

Important:
- Keep `.env` local only.
- Never commit real keys.
- If any real key was ever exposed, rotate it immediately.

## 5) How to run

Install:
```bash
poetry install
```

Dry run with example questions (safe):
```bash
poetry run python forecasting_bot.py --mode examples --no-submit
```

Tournament run without posting:
```bash
poetry run python forecasting_bot.py --mode tournament --tournament metaculus-cup --no-submit
```

Tournament run with posting:
```bash
poetry run python forecasting_bot.py --mode tournament --tournament metaculus-cup
```

Multiple tournaments:
```bash
poetry run python forecasting_bot.py --mode tournament --tournament metaculus-cup minibench --no-submit
```

Custom local question:
```bash
poetry run python forecast_custom_question.py input_question.json --num-runs 3
```

## 6) Current state (honest assessment)

What is good right now:
- End-to-end automation exists and is usable.
- Supports all major Metaculus question types handled here.
- Includes async calls + basic concurrency control.
- Has practical helper scripts for local inspection and diagnostics.

What is fragile right now:
- Main logic is concentrated in a single large file (`forecasting_bot.py`), hard to maintain.
- Output parsing is regex-based and can break on format drift from LLM responses.
- Error handling is mostly print-based; partial failures do not produce structured retries/reporting.
- Research fallback is simple and provider-specific behavior is not abstracted.
- "Tests" are mostly manual/integration scripts, not deterministic unit tests.

## 7) Key issues to know before extending

1. Reliability risk from prompt-parsing coupling
   Forecast extraction assumes specific output formats.

2. Model/cost accounting mismatch in custom-question script
   `forecast_custom_question.py` exposes `--model` and cost tables, but core LLM call uses model defaults in `forecasting_bot.py` unless refactored to pass model through all layers.

3. Tournament retrieval scope
   Current fetch path is limited by request size and endpoint filtering; pagination/coverage is basic.

4. Mixed sync/async design
   Some calls are sync (`time.sleep`, sync HTTP) in a mostly async workflow, which can reduce throughput and clarity.

5. Limited observability
   No structured logs/metrics, making debugging and cost/rate-limit analysis harder.

6. Repo hygiene debt
   Generated/debug artifacts are present; architecture and naming still reflect iterative prototyping.

## 8) Highest-value improvement plan

1. Split `forecasting_bot.py` into modules
   - `metaculus_client.py`, `research.py`, `llm.py`, `parsers.py`, `forecast_types.py`, `runner.py`.

2. Make LLM output structured
   - force JSON schema responses instead of regex parsing free text.

3. Add robust retry and backoff
   - retry around Metaculus, OpenRouter, and research calls with categorized exceptions.

4. Add true tests
   - unit tests for parsers and CDF generation,
   - mocked integration tests for API client paths.

5. Introduce structured logging
   - question ID, provider, model, latency, token/cost estimate, retry count.

6. Pass model/config explicitly end-to-end
   - remove hidden defaults and make runtime behavior predictable.

## 9) Quick "where to edit" guide for vibe-coding

- Change prompt style:
  - edit `BINARY_PROMPT_TEMPLATE`, `NUMERIC_PROMPT_TEMPLATE`, `MULTIPLE_CHOICE_PROMPT_TEMPLATE` in `forecasting_bot.py`.
- Change model:
  - edit default in `call_llm(...)` in `forecasting_bot.py` (or refactor to CLI arg).
- Change research preference order:
  - edit `run_research(...)` in `forecasting_bot.py`.
- Change tournament aliases:
  - edit constants and `TOURNAMENT_MAPPING` in `forecasting_bot.py`.
- Change submission behavior:
  - use `--no-submit`, and inspect `submit_prediction` handling in `forecast_individual_question(...)`.

## 10) Minimal safety checklist before real submission

1. Run with `--no-submit` first.
2. Inspect at least 3 generated rationales + parsed outputs.
3. Confirm env keys are valid and non-empty.
4. Use smaller `--num-runs` while debugging cost and latency.
5. Submit only after checking question-specific edge cases (bounds, options, resolution criteria).
