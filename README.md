# NIM Release Risk Agent

A NAT-native ReAct agent — built on NVIDIA's NeMo Agent Toolkit, running on NVIDIA's NIM-hosted Llama 3.1 70B — that gathers live GitHub signals for a repository and scores release risk using a production ensemble ML model.

This is a companion project to [AI-Based Release Risk Predictor](https://github.com/nanantha17/AI-release-risk-predictor), which uses Claude + MCP for the same problem. This version swaps the orchestration framework (NAT instead of a hand-rolled agentic loop) and the reasoning model (NVIDIA NIM/Llama 3.1 instead of Claude), as a deliberate comparison of both stacks on the same underlying task.

---

## Status

**Complete:** end-to-end agentic loop, Phoenix observability with a measured performance fix, a custom evaluation suite, and deployment as a servable REST API via `nat serve`.

This is an NVIDIA NeMo Agent Toolkit learning project, not a production system. It's the counterpart to my production Claude + MCP system, built to gain direct, hands-on experience with NVIDIA's own agentic tooling.

---

## What It Does

Given a natural-language question like *"What's the release risk for microsoft/vscode?"*, the agent:

1. Reasons about which signals it needs (ReAct loop: Thought → Action → Observation)
2. Calls live GitHub REST API tools to gather PR velocity, code churn, and contributor data
3. Falls back to sensible stated defaults for signals GitHub can't directly provide (test coverage, code complexity, etc.)
4. Sends the mapped metrics to a production ensemble ML risk-scoring API
5. Returns a Go/NoGo-style assessment with explainable risk factors — or, for narrower questions ("how many contributors on X"), answers just that signal directly without running the full pipeline

---

## Architecture

<img width="1884" height="1075" alt="NIM_Rel_Agent" src="https://github.com/user-attachments/assets/b6c961c0-c25c-4930-8064-ec077a3ce176" />


---

## Tools

| Tool | Source | Returns |
|---|---|---|
| `get_pr_velocity` | GitHub REST API | Recent closed PR count (proxy for merge velocity) |
| `get_commit_stats` | GitHub REST API | Lines changed + unique contributor count, from a single commit scan |
| `score_release_risk` | Risk Predictor API | Risk score, level, confidence, and ranked risk factors |

For signals GitHub can't directly provide (test coverage, cyclomatic complexity, defect history), the agent is instructed to use stated neutral defaults rather than infer or fabricate values — kept explicit in the system prompt for transparency.

---

## Observability: Phoenix Tracing

Every run is traced end-to-end with [Arize Phoenix](https://phoenix.arize.com/), giving per-tool-call spans, timing, and the full reasoning trace.

**Tracing surfaced a real inefficiency, which I fixed:**

`get_lines_of_code_changed` and `get_unique_contributor_count` were originally two separate tools, each independently calling the same underlying GitHub commit-fetch helper — visible in the trace as two ~9.5s spans doing near-identical work. Merging them into a single `get_commit_stats` tool eliminated the duplicate API scan.

**Measured result** (from Phoenix trace comparison, same query, before/after):
- Before: ~66s total workflow latency
- After: ~51s total workflow latency
- **~20% reduction**, matching the expected savings from removing one redundant ~9.5s GitHub API scan plus one fewer agent reasoning cycle

| Before (two tools) | After (merged tool) |
|---|---|
| `get_lines_of_code_changed`: 9.5s / `get_unique_contributor_count`: 9.7s | `get_commit_stats`: 9.7s |

---
<img width="1169" height="880" alt="NIM_agent" src="https://github.com/user-attachments/assets/52bc242b-1684-48f4-8f39-db0608bb5e24" />

## Evaluation

Uses a custom NAT-registered evaluator (`grounded_correctness`) — an LLM-judge that checks whether each response is specific, grounded in real tool output, and correctly scoped to the question asked.

**Why a custom evaluator instead of a stock Ragas metric:** initial attempts with Ragas's `AnswerAccuracy` metric returned a flat 0.0 across every question, regardless of answer quality. Investigation showed `AnswerAccuracy` is built for RAG pipelines and scores against `retrieved_contexts` — a field that's structurally empty for a tool-calling agent that never does retrieval. The metric wasn't measuring the wrong thing; it couldn't measure this workflow at all. Rather than force-fit a mismatched metric, I wrote a custom evaluator scoring directly against what actually matters here: specificity, groundedness in real tool output, and correct scope.

**Current result: 0.8 / 1.0** across 5 test questions covering both full risk assessments and narrow single-signal queries.

The one gap is understood, not a mystery: it involves a contributor-count question where the judge flagged the answer as an unverified "guess," even though manual verification against the GitHub API confirmed the agent's number was correct at the time it ran. This is a known limitation of LLM-as-judge evaluation — it can't always independently verify a specific factual claim without being given ground truth to check against.

Run it:
```bash
nat eval --config_file configs/config.yml
```

---

## Stack

- **NVIDIA NeMo Agent Toolkit (NAT)** — agent orchestration, ReAct loop, tool and evaluator registration
- **NVIDIA NIM** — hosted `meta/llama-3.1-70b-instruct` as the reasoning model
- **Arize Phoenix** — OpenTelemetry-based tracing and observability
- **GitHub REST API** — live repository signal collection
- **FastAPI** — risk predictor backend (see [companion repo](https://github.com/nanantha17/AI-release-risk-predictor) for the ML details: PyTorch RiskNet + Sklearn Gradient Boosting + DistilBERT NLP ensemble)

---

## Quick Start

### Prerequisites
- Python 3.9+
- NVIDIA API key ([build.nvidia.com](https://build.nvidia.com))
- GitHub personal access token (classic, `public_repo` scope)
- The [Risk Predictor API](https://github.com/nanantha17/AI-release-risk-predictor) running locally on port 8000

### Setup

```bash
git clone https://github.com/nanantha17/nim-release-risk-agent.git
cd nim-release-risk-agent
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -e .
```

Set environment variables:
```bash
$env:NVIDIA_API_KEY = "nvapi-..."
$env:GITHUB_TOKEN = "ghp_..."
```

### Run

```bash
# Optional: start Phoenix for tracing (separate terminal)
phoenix serve

nat run --config_file configs/config.yml --input "What's the release risk for microsoft/vscode?"
```

### Evaluate

```bash
nat eval --config_file configs/config.yml
```

### Deploy as a REST API

```bash
nat serve --config_file configs/config.yml --port 8001
```

This exposes the agent as a FastAPI service with auto-generated docs at `http://localhost:8001/docs`. Example request (PowerShell):

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/generate" -Method Post `
  -ContentType "application/json" `
  -Body (@{ input_message = "What is the release risk for microsoft/vscode?" } | ConvertTo-Json)
```

Returns a real, tool-grounded response from the live agent, e.g.:

> "The release risk for microsoft/vscode is MEDIUM, with a risk score of 29.0 and a confidence level of 0.953. The top risk factors are Changeset Size, Test Coverage, and Code Coverage..."

Note: port 8001 is used deliberately since port 8000 is occupied by the Risk Predictor API.

---

## Why NAT + NIM, Separate from the Production Claude System

The [production Agentic Program Health System](https://github.com/nanantha17/Agentic-AI-Program-Health-System) uses Claude + MCP and is what's actually deployed and adopted internally at ASML. This project is a deliberately separate, NVIDIA-native rebuild of the same core pattern — same problem, same signal sources, different orchestration engine and reasoning model — built to gain direct, hands-on experience with NVIDIA's own agentic tooling.

---

## Roadmap

- [x] Phoenix tracing for per-tool-call observability
- [x] Custom NAT evaluation suite with LLM-judge scoring
- [x] Deployed as a servable REST API via `nat serve`

---

## License

See repository for license terms.
