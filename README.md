# Cognitive Friction Engine

**An async, modular, adversarial multi-agent LLM debate engine for rigorous epistemic evaluation of ideas.**

---

## Overview
Most LLM wrappers achieve only superficial diversity by tweaking random seeds or sampling parameters. Cognitive Friction Engine moves beyond this: each agent is assigned a rigorously defined epistemic role—quantitative risk analyst, contrarian adversary, scenario breaker, and more—using modular, fully configurable YAML. This forces the system to actively explore risk, edge-cases, and adversarial stances that consensus-driven sampling would ignore.

You don’t just get reworded opinions or minor disagreements. You get substantive critique from multiple, deeply distinct perspectives—sometimes surfacing dealbreakers or failure modes you’d never get from a single-agent or groupthink model.

Through repeated, randomized runs and cross-examination, it highlights which ideas:
- Consistently survive
- Converge under critique
- Mutate in the same direction
- Collapse under pressure

> ⚠️ Best used as validation tool, not open-ended brainstorming
---

## Core Features

### - Multi-agent, adversarial orchestration
Each agent adopts a specific reasoning or adversarial archetype (e.g. risk, contrarian, scenario-breaker) and critiques ideas independently and in crossfire rounds.

### - Epistemic diversity and role enforcement
YAML-configurable required archetypes and agent selectors ensure no panel degenerates into consensus or groupthink.

### - Meta-agent process governance
A dedicated meta-agent monitors process health, recommends changes if diversity weakens, and halts when debate ceases to yield new information.

### - Modular, async Python core
Portable, readable architecture with clear separation of config, orchestration, and agent logic.

### - Stochastic multi-run evaluation
Full process is repeated across multiple random panel/run permutations to uncover convergence or structural weaknesses.

### - Configurable and extensible
Easily adapt YAMLs for different agent roles, instructions, and debate styles. Integration with additional LLM APIs or frameworks is straightforward.

### - Container-ready
Dockerfile included for easy reproducibility and secure isolation.

---

## Quickstart

### Option 1: Native Python

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your API key

Set `OPENAI_API_KEY` in a `.env` file or as an environment variable.

```env
OPENAI_API_KEY=sk-xxxx
```

### 3. Prepare your configuration

Fill in `config.yaml` (or supply CLI flags):

```yaml
premise: "Describe your idea, project, or proposal here."
process_instruction: "Agent instruction or framing for deliberation, e.g., 'Critique this idea from all possible epistemic standpoints.'"
max_iter: 3          # Number of debate rounds per run
multi_run: 5         # Number of independent Monte-Carlo runs
# Add/point to agent/board/archetype YAMLs as desired — see below
```

Check/edit these YAMLs as needed:
- `archetypes.yaml` (required epistemic roles)
- `agents_board.yaml` (how agent panels are proposed/selected)
- `meta_agent.yaml` (oversight and process health logic)

### 4. Run

```bash
python main.py --config run_config.yaml
# or, with flags:
python main.py --premise "..." --process-instruction "..." --multi-run 7 --max-iter 3 --verbose
```

### 5. Analyze results

Each run is logged as Markdown and JSON in `logs/run_*`.

To aggregate and cluster results across runs:

```bash
python aggregate.py logs/
```

See `aggregate_report.md` for summary, cluster patterns, and unresolved risks.

---

### Option 2: Docker

Containerized runs ensure reproducibility, less local setup, and safe key handling.

#### 1. Build the image

```bash
docker build -t cognitive-friction .
```

#### 2. Configure your API key

Pass as environment variable:

```bash
docker run -e OPENAI_API_KEY=sk-xxxx -v $(pwd)/logs:/app/logs cognitive-friction --config config.yaml
```
- `-e` provides OpenAI API key to container.
- `-v` mounts your local logs so results persist.
- You can pass all CLI flags as normal.
- If using a `.env`, COPY it into your build context, or pass `--env-file` as needed.

---

## Known Gaps and Technical Trade-offs

- Framework-agnostic: No CrewAI/LangChain used; wanted to test pure principles and concept first, but interfaces are written for easy future wrap.

- Sequential Agent Calls, not Parallel: Deliberate (for now) to avoid API quota issues and ensure debate order is transparent for debugging/study.
Parallelization is trivial to add, and is planned for future revisions as infrastructure allows.

- LLM Homogeneity: Currently implemented for OpenAI only (prototzping), multi-model support is on the roadmap and easy to add.

### Containerization

- Dockerfile included for stateless, reproducible launches (locally or in cloud)

### Extending the System

- **More agent types?** → Edit `archetypes.yaml`
- **Different meta-agent logic?** → Rewrite `meta_agent.yaml`
- **Other LLM providers or on-prem models?** → Swap out `gpt_api.py`
- **Agent “memory” or learning?** → Extend agent configs and output handling

---

## Example Use Cases

- Failure mode discovery in early-stage business ideas or technical proposals
- Stress-testing research plans or complex strategic decisions
- Auditing robustness of product features or user flows under adversarial reasoning

> ⚠️ Domain-agnostic: Not limited to business or technical ideas.

---

## Roadmap

- Parallel and distributed agent orchestration
- Plug-and-play agent frameworks (LangChain, CrewAI, etc.)
- Automated verdict classification and advanced risk clustering
- Web dashboard for run inspection and triage (maybe)

