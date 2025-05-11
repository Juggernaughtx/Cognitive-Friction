# main.py

import asyncio
import yaml
from pathlib import Path

from engine.utils import atomic_write_json, write_human_log_markdown, agent_seed
from engine.gpt import call_gpt

def load_agents(config_path="agents.yaml"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config["agents"]

def load_meta_agent(config_path="meta_agent.yaml"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config["meta_agent"]

async def run_until_exhaustion(
    static_premise, process_instruction, max_iterations=10,
    agents=None, meta_agent=None, verbose=False, run_id=None, master_seed=None
):
    memory, history = {}, []
    current_idea = static_premise
    previous_critiques = None

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n===== ITERATION {iteration + 1} =====\n")

        critiques = await critique_phase(
            current_idea, process_instruction, agents, memory, previous_critiques, verbose, master_seed, iteration
        )

        crossfires = await crossfire_phase(
            critiques, process_instruction, agents, verbose, master_seed, iteration
        )

        synthesis = await synthesis_phase(
            critiques, crossfires, process_instruction, verbose, master_seed, iteration
        )

        meta_decision = await meta_decision_phase(
            critiques, crossfires, history, process_instruction, meta_agent, verbose, master_seed, iteration
        )

        history.append({
            "iteration": iteration + 1,
            "critiques": critiques,
            "crossfire": crossfires,
            "synthesis": synthesis,
            "meta_decision": meta_decision
        })

        previous_critiques = critiques
        current_idea = synthesis

        if meta_decision.get("halt", False):
            if verbose:
                print(f"\n[Meta-Agent] Exhaustion reached at iteration {iteration + 1}\n")
            break

    outdir = Path("logs") / str(run_id)
    outdir.mkdir(parents=True, exist_ok=True)
    run_json = {
        "static_premise": static_premise,
        "process_instruction": process_instruction,
        "history": history
    }
    atomic_write_json(outdir / "summary.json", run_json)
    write_human_log_markdown(outdir / "summary.md", run_json)
    return history

async def critique_phase(idea, process_instruction, agents, memory, previous_critiques, verbose, master_seed, iteration):
    tasks = []
    for i, agent in enumerate(agents):
        background = agent.get("system", "")
        agent_name = agent["name"]
        prior = memory.get(agent_name, "")

        user_prompt = (
            f"You are acting as {agent_name}. Your role: {background}\n"
            f"Business idea to assess: {idea}\n"
            f"Process expectations: {process_instruction}\n"
            +
            (
                f"\nPrevious critiques and fixes (if any):\n{previous_critiques}\n"
                if previous_critiques else ""
            )
            +
            (
                "\nCRITIQUE PHASE: Be unreasonably rigorous, adversarial, and risk-focused. "
                "Surface every feasible risk, flaw, data gap, or edge-destroying factor relevant to your persona. "
                "Do not pander or agree—your job is to shoot holes, not propose fixes yet."
            )
        )

        seed_val = agent_seed(master_seed, f"critique-{agent_name}-{iteration}") if master_seed is not None else None
        tasks.append(call_gpt(background, user_prompt, seed=seed_val, max_tokens=32))
    results = await asyncio.gather(*tasks)
    agent_critiques = {a["name"]: r for a, r in zip(agents, results)}

    if verbose:
        print("\n--- Agent Critiques ---")
        for agent in agents:
            print(f"\033[94m[{agent['name']}]:\033[0m\n{agent_critiques[agent['name']]}\n")
    return agent_critiques

async def crossfire_phase(critiques, process_instruction, agents, verbose, master_seed, iteration):
    tasks = []
    for i, agent in enumerate(agents):
        agent_name = agent["name"]
        background = agent.get("system", "")
        peer_critiques = {k: v for k, v in critiques.items() if k != agent_name}
        own_critique = critiques[agent_name]
        user_prompt = (
            f"You are {agent_name}. Your role: {background}\n"
            "Below are peer critiques of the portfolio idea. Your original critique:\n"
            f"{own_critique}\n"
            "Peer critiques:\n" +
            "\n".join(f"{k}: {v}" for k, v in peer_critiques.items()) +
            (
                "\nCROSSFIRE PHASE: Act as an adversarial panelist. For each peer critique:\n"
                "- Rebut, counter, strengthen, or escalate the critique.\n"
                "- If critique is valid but can be mitigated, propose a concrete fix.\n"
                "- If you disagree, provide evidence or logic why.\n"
                "- If you missed something another agent found, acknowledge and elaborate.\n"
                "Be concise but don't hold back. Your job is to create maximum constructive cognitive friction."
            ) +
            f"\nProcess expectations: {process_instruction}"
        )
        seed_val = agent_seed(master_seed, f"crossfire-{agent_name}-{iteration}") if master_seed is not None else None
        tasks.append(call_gpt(background, user_prompt, seed=seed_val, max_tokens=32))
    results = await asyncio.gather(*tasks)
    crossfire_responses = {a["name"]: r for a, r in zip(agents, results)}

    if verbose:
        print("\n--- Agent Crossfire ---")
        for agent in agents:
            print(f"\033[91m[{agent['name']}]:\033[0m\n{crossfire_responses[agent['name']]}\n")
    return crossfire_responses

async def synthesis_phase(critiques, crossfires, process_instruction, verbose, master_seed, iteration):
    crossfire_text = "\n".join([f"{k}: {v}" for k, v in crossfires.items()])
    critique_text = "\n".join([f"{k}: {v}" for k, v in critiques.items()])
    user_prompt = (
        "SYNTHESIS PHASE: Acting as a synthesis/refinement expert for portfolio design.\n"
        "Given the following:\n"
        f"1. Agent Critiques:\n{critique_text}\n"
        f"2. Agent Crossfire Responses:\n{crossfire_text}\n"
        f"Process expectations: {process_instruction}\n"
        "Your task: \n"
        "- Refine the business/architecture/portfolio idea as needed.\n"
        "- List all risks you consider *addressed* (with rationale), those that remain *open* or unsolved, and any *new* risks raised.\n"
        "- Clearly state any structural mutations to the idea.\n"
        "Do not gloss over unresolved dangers. Prioritize candor and specificity."
    )
    seed_val = agent_seed(master_seed, f"synthesis-{iteration}") if master_seed is not None else None
    result = await call_gpt(
        "You are a rigorous synthesis/refinement expert specializing in adversarial improvement.",
        user_prompt,
        seed=seed_val
    )
    if verbose:
        print(f"\n\033[92m[SYNTHESIS]\033[0m\n{result}\n")
    return result

async def meta_decision_phase(critiques, crossfires, history, process_instruction, meta_agent, verbose, master_seed, iteration):
    prompt = (
        "META-DECISION PHASE:\n"
        "Below is the full process context so far (history omitted for brevity in the call):\n"
        f"- Latest agent critiques: {critiques}\n"
        f"- Latest crossfire: {crossfires}\n"
        "Your job: Declare EXHAUSTION (halt) ONLY if:\n"
        "* All agents are in substantive agreement,\n"
        "* No critical risks or dissent remain,\n"
        "* Every risk has a plausible, concrete mitigation the panel accepts.\n"
        "Otherwise, recommend another iteration.\n"
        "Output JSON: {\"halt\": true/false, \"rationale\": \"...\"}\n"
        f"Process expectations: {process_instruction}\n"
    )
    seed_val = agent_seed(master_seed, f"meta-{iteration}") if master_seed is not None else None
    result = await call_gpt(meta_agent["system"], prompt, seed=seed_val)
    import json
    try:
        decision = json.loads(result)
        if not isinstance(decision, dict) or "halt" not in decision:
            decision = {"halt": False, "rationale": "Parse error or missing 'halt'—continuing by default."}
    except Exception:
        decision = {"halt": False, "rationale": "Failed to parse meta decision as JSON—default to continue."}
    if verbose:
        print(f"\n\033[93m[Meta-Agent Decision]\033[0m\n{decision}\n")
    return decision