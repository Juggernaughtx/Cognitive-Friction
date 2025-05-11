# Cognitive Friction Engine

An AI-driven idea evolution and validation system using multiple simulated expert personas.

## 🎯 Purpose
This system stress-tests a single idea by letting multiple AI agents with different reasoning styles analyze, debate, and evolve it through several rounds, across multiple independent runs with varied randomness. The goal is to:

- Explore idea robustness
- Discover structural weaknesses
- Observe convergent outcomes
- Collect and compare idea mutations

---

## 🗂️ Project Structure

```
cognitive_friction_engine/
├── main.py                 # CLI entry point for single or multi-run
├── aggregate.py            # Analyzer for summarizing multi-run output
├── engine/
│   ├── controller.py       # Main orchestration logic
│   ├── gpt.py              # OpenAI GPT async wrapper
├── logs/                   # Auto-created per run (run_01, run_02, etc.)
│   └── ...
├── requirements.txt        # Required dependencies
├── README.md               # You are here
```

---

## 🧪 Usage

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key
Create a `.env` file:
```
OPENAI_API_KEY=sk-xxxxxx
```
Or set as environment variable:
```bash
export OPENAI_API_KEY=sk-xxxxxx
```

### 3. Run the engine

#### Single Run:
```bash
python main.py "Your business idea here"
```

#### Multi-Run (N stochastic variants):
```bash
python main.py "Your idea here" --multi-run 10 --iter 3
```

### 4. Analyze Results:
```bash
python aggregate.py logs/
```
Outputs:
- Final ideas from each run
- Cosine similarity matrix
- Insight into convergence or drift

---

## 🧠 Agents Used (Hardcoded in `controller.py`)
- Empirical Analyst
- Theoretical Strategist
- Risk Maximizer
- Risk Minimizer
- Contrarian Reframer

---

## ✅ Coming Enhancements
- Cluster detection of final ideas
- Verdict classifier (viable/broken/transformed)
- YAML-based agent configuration

---

## 🤝 Author Notes
Built for cognitive stress-testing of business ideas with reproducible and multi-angle reasoning.
