# NIM Release Risk Agent

A NAT-native ReAct agent — built on NVIDIA's NeMo Agent Toolkit, running on NVIDIA's NIM-hosted Llama 3.1 70B — that gathers live GitHub signals for a repository and scores release risk using a production ensemble ML model.

This is a companion project to [AI-Based Release Risk Predictor](https://github.com/nanantha17/AI-release-risk-predictor), which uses Claude + MCP for the same problem. This version swaps the orchestration framework (NAT instead of a hand-rolled agentic loop) and the reasoning model (NVIDIA NIM/Llama 3.1 instead of Claude), as a deliberate comparison of both stacks on the same underlying task.

---

## Status

**Working:** end-to-end agentic loop — live GitHub API calls, tool-based reasoning, risk scoring against a real ML backend.

**Not yet built:** Phoenix observability tracing, automated evaluation suite. These are next.

This is an active NVIDIA NeMo Agent Toolkit learning project, not a production system.

---

## What It Does

Given a natural-language question like *"What's the release risk for microsoft/vscode?"*, the agent:

1. Reasons about which signals it needs (ReAct loop: Thought → Action → Observation)
2. Calls live GitHub REST API tools to gather PR velocity, code churn, and contributor data
3. Falls back to sensible stated defaults for signals GitHub can't directly provide (test coverage, code complexity, etc.)
4. Sends the mapped metrics to a production ensemble ML risk-scoring API
5. Returns a Go/NoGo-style assessment with explainable risk factors

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  User question (CLI / nat run)               │
└───────────────────────┬───────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────┐
│  NAT ReAct Agent                             │
│  LLM: NVIDIA NIM — meta/llama-3.1-70b-instruct│
└───────────────────────┬───────────────────────┘
                         │ tool calls
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌─────────────┐┌──────────────┐┌─────────────────┐
   │ get_pr_      ││ get_lines_of ││ get_unique_      │
   │ velocity     ││ _code_changed││ contributor_count│
   └──────┬───────┘└──────┬───────┘└────────┬─────────┘
          │  GitHub REST API calls           │
          └──────────────┬───────────────────┘
                         ▼
              ┌─────────────────────┐
              │ score_release_risk  │
              │ → POST /predict      │
              └──────────┬───────────┘
                         ▼
          ┌───────────────────────────────┐
          │ Risk Predictor API (FastAPI)  │
          │ PyTorch + Sklearn + DistilBERT│
          │ ensemble → risk score, level, │
          │ confidence, explained factors │
          └───────────────────────────────┘
```

---

## Tools

| Tool | Source | Returns |
|---|---|---|
| `get_pr_velocity` | GitHub REST API | Recent closed PR count (proxy for merge velocity) |
| `get_lines_of_code_changed` | GitHub REST API | Aggregate additions + deletions across recent commits |
| `get_unique_contributor_count` | GitHub REST API | Distinct commit authors in recent history |
| `score_release_risk` | Risk Predictor API | Risk score, level, confidence, and ranked risk factors |

For signals GitHub can't directly provide (test coverage, cyclomatic complexity, defect history), the agent is instructed to use stated neutral defaults rather than infer or fabricate values — kept explicit in the system prompt for transparency.

---

## Stack

- **NVIDIA NeMo Agent Toolkit (NAT)** — agent orchestration, ReAct loop, tool registration
- **NVIDIA NIM** — hosted `meta/llama-3.1-70b-instruct` as the reasoning model
- **GitHub REST API** — live repository signal collection
- **FastAPI** — risk predictor backend (see [companion repo](https://github.com/nanantha17/AI-release-risk-predictor) for the ML details: PyTorch RiskNet + Sklearn Gradient Boosting + DistilBERT NLP ensemble)

---

## Quick Start

### Prerequisites
- Python 3.9+
- NVIDIA API key ([build.nvidia.com](https://build.nvidia.com))
- GitHub personal access token
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
nat run --config_file configs/config.yml --input "What's the release risk for microsoft/vscode?"
```

---

## Why NAT + NIM, Separate from the Production Claude System

The [production Agentic Program Health System](https://github.com/nanantha17/Agentic-AI-Program-Health-System) uses Claude + MCP and is what's actually deployed and adopted internally at ASML. This project is a deliberately separate, NVIDIA-native rebuild of the same core pattern — same problem, same signal sources, different orchestration engine and reasoning model — built to gain direct, hands-on experience with NVIDIA's own agentic tooling.

---

## Roadmap

- [ ] Phoenix tracing for per-tool-call observability
- [ ] NAT evaluation suite — test cases scoring tool selection accuracy and answer groundedness
- [ ] Expand GitHub signal coverage (CI build status, issue labels)
- [ ] `nat serve` deployment with NAT UI

---

## License

See repository for license terms.
