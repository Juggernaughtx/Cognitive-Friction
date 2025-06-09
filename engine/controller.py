# engine/controller.py

import asyncio
from pathlib import Path
from engine.agent_manager import get_panel
from engine.utils import atomic_write_json, write_human_log_markdown
from engine.gpt_api import call_gpt
import yaml

def load_meta_agent(config_path="meta_agent.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)["meta_agent"]

async def run_full_process(
    premise, process_instruction, agents, meta_agent, max_iter, run_id, seed, verbose
):
    history = []
    current = premise
    prev_critiques = None
    for iteration in range(max_iter):
        if verbose:
            print(f"\n=== [RUN: {run_id}] Iteration {iteration+1}/{max_iter} ===", flush=True)
        critiques = {}
        for agent in agents:
            if verbose:
                print(f"\n[Agent: {agent['name']}] | Phase: CRITIQUE", flush=True)
            user_prompt = (
                f"You are {agent['name']}. {agent['system']}\n"
                f"Business proposal: {current}\nProcess: {process_instruction}\n"
                + (f"Prev critiques: {prev_critiques}\n" if prev_critiques else "")
                + "CRITIQUE PHASE: List every risk, flaw, or gap. Output as plaintext."
            )
            critique = await call_gpt(agent["system"], user_prompt, seed=seed)
            critiques[agent['name']] = critique
            if verbose:
                print(f"Output: {(critique[:180] + '...') if len(critique)>180 else critique}", flush=True)

        crossfires = {}
        for agent in agents:
            if verbose:
                print(f"\n[Agent: {agent['name']}] | Phase: CROSSFIRE", flush=True)
            peer_critiques = {k:v for k,v in critiques.items() if k != agent["name"]}
            user_prompt = (
                f"You are {agent['name']}. {agent['system']}\n"
                f"Peer critiques: {peer_critiques}\n"
                f"Your critique: {critiques[agent['name']]}\n"
                "CROSSFIRE PHASE: For each peer, rebut or expand. Output as plaintext."
            )
            crossfire = await call_gpt(agent["system"], user_prompt, seed=seed+1)
            crossfires[agent['name']] = crossfire
            if verbose:
                print(f"Output: {(crossfire[:180] + '...') if len(crossfire)>180 else crossfire}", flush=True)

        # Synthesis Phase
        if verbose:
            print("\n[SYNTHESIS PHASE]", flush=True)
        user_prompt = (
            "SYNTHESIS PHASE: Based on agent critiques and crossfire, refine idea and list all OPEN and ADDRESSED risks."
            "Output as strict JSON: {'refined_idea': ..., 'addressed_risks': [...], 'open_risks': [...]}."
        )
        synthesis = await call_gpt(
            "Synthesis expert", 
            user_prompt + f"\nCritiques: {critiques}\nCrossfires: {crossfires}",
            expect_json=True, 
            seed=seed+2
        )
        if verbose:
            print(f"Refined Idea: {synthesis.get('refined_idea','')[:120]}", flush=True)
            print("Addressed risks:", synthesis.get('addressed_risks', []), flush=True)
            print("Open risks:", synthesis.get('open_risks', []), flush=True)

        # Meta-decision
        if verbose:
            print("[META-AGENT PHASE]", flush=True)
        meta_user_prompt = (
            "Meta-decision: Should we halt further iterations? If all agents substantively agree and all risks are resolved, halt is true."
            "Output only strict JSON: {'halt': true/false, 'rationale': '...'}"
        )
        meta_decision = await call_gpt(
            meta_agent['system'], 
            meta_user_prompt + f"\nCritiques: {critiques}\nCrossfires: {crossfires}",
            expect_json=True, 
            seed=seed+3
        )
        if verbose:
            print(f"META-AGENT DECISION: {'HALT' if meta_decision.get('halt') else 'CONTINUE'}; RATIONALE: {meta_decision.get('rationale','NO RATIONALE')}", flush=True)

        history.append({
            "iteration": iteration+1,
            "critiques": critiques,
            "crossfire": crossfires,
            "synthesis": synthesis,
            "meta_decision": meta_decision
        })
        current = synthesis.get('refined_idea', current)
        prev_critiques = critiques
        if meta_decision.get('halt'):
            if verbose:
                print(f"\n[Exhaustion detected at iteration {iteration+1}], process halts.", flush=True)
            break
    outdir = Path("logs") / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(outdir/"summary.json", {
        "initial": premise,
        "process_instruction": process_instruction,
        "history": history,
        "final": current
    })
    write_human_log_markdown(outdir/"summary.md", {
        "initial": premise,
        "process_instruction": process_instruction,
        "history": history,
        "final": current
    })
    if verbose:
        print(f"\nRun {run_id} COMPLETE. Final idea: {current[:180]}", flush=True)
    return history