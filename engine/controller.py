# engine/controller.py

import asyncio
from pathlib import Path
from engine.agent_manager import get_panel
from engine.utils import atomic_write_json, write_human_log_markdown, prompt_user_for_answers
from engine.gpt_api import call_gpt
from engine.utils import agent_seed
import yaml
import json

def load_meta_agent(config_path="meta_agent.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["meta_agent"]

def _serialize_question_for_id(question):
    """
    Return a string that is hashable and represents the question uniquely.
    If the question is a dict, convert to a compact JSON string (sorted keys).
    If the question is a string, return as-is.
    """
    if isinstance(question, dict):
        return json.dumps(question, sort_keys=True, separators=(',', ':'))
    return str(question)

async def run_full_process(
    premise, process_instruction, agents, meta_agent, max_iter, run_id, master_seed, verbose,
    panel_log=None, required_archetypes=None, critique_crossfire_temp=0.7
):
    history = []
    current = premise
    prev_critiques = None
    ground_truths = {}    # new: all user Q&A
    risk_clusters = {}    # new: iterative risk clustering/survivorship
    board_entropy = []    # entropy (risk novelness) per round

    for iteration in range(max_iter):
        if verbose:
            print(f"\n=== [RUN: {run_id}] Iteration {iteration+1}/{max_iter} ===", flush=True)
        critiques = {}
        info_requests = []
        # CRITIQUE PHASE (with adversarial/entropy induction)
        for agent in agents:
            if verbose:
                print(f"\n[Agent: {agent['name']}] | Phase: CRITIQUE", flush=True)
            user_prompt = (
                f"You are {agent['name']} [{agent.get('archetype','?')}].\n"
                f"{agent['system']}\n"
                f"Business proposal: {current}\nProcess: {process_instruction}\n"
                f"{'Ground truths/clarifications from project owner: ' + str(ground_truths) if ground_truths else ''}\n"
                f"{'Prev critiques: ' + str(prev_critiques) if prev_critiques else ''}\n"
                "CRITIQUE PHASE: Give all risks (unusual edge cases too), cluster into: [mainstream, low-probability/catastrophic, resolved]. "
                "For any critique, if you lack a key fact, output a question (req_user=True, with Q). Output strict JSON: {'critiques':[...],'user_questions':[...]}."
            )
            agent_specific_seed = agent_seed(master_seed, agent['name'])
            out = await call_gpt(agent['system'], user_prompt, seed=agent_specific_seed, temperature=critique_crossfire_temp, expect_json=True)
            critiques[agent['name']] = out.get("critiques", [])
            if verbose:
                preview = out.get('critiques', out)
                printable_preview = str(preview)[:180] + ('...' if len(str(preview)) > 180 else '')
                print(f"Output: {printable_preview}", flush=True)
            for q in out.get("user_questions", []):
                # Ignore blank questions
                if not q:
                    continue
                # The agent can output a string or a dict as a question
                text_for_id = _serialize_question_for_id(q)
                info_requests.append({
                    "agent": agent['name'],
                    "question": q if isinstance(q, str) else json.dumps(q, ensure_ascii=False, indent=None),
                    "id": f"{iteration}_{agent['name']}_{hash(text_for_id)}"
                })
        # USER-IN-THE-LOOP Q&A
        user_answers = {}
        if info_requests:
            user_answers = prompt_user_for_answers(info_requests, verbose)
            ground_truths.update({q["id"]: user_answers[q["id"]] for q in info_requests})
        crossfires = {}
        for agent in agents:
            if verbose:
                print(f"\n[Agent: {agent['name']}] | Phase: CROSSFIRE", flush=True)
            peer_critiques = {k:v for k,v in critiques.items() if k != agent["name"]}
            user_prompt = (
                f"You are {agent['name']}. {agent['system']}\n"
                f"Peer critiques: {peer_critiques}\n"
                f"Your critique: {critiques[agent['name']]}\n"
                f"Ground truths/clarifications: {user_answers}\n"
                "CROSSFIRE PHASE: For each peer, rebut or expand. Output as plaintext."
            )
            crossfire_seed = agent_seed(master_seed, f"{agent['name']}_crossfire")
            crossfire = await call_gpt(agent["system"], user_prompt, temperature=critique_crossfire_temp, seed=crossfire_seed)
            crossfires[agent['name']] = crossfire
            if verbose:
                printable_preview = crossfire[:180] + ('...' if len(crossfire) > 180 else '')
                print(f"Output: {printable_preview}", flush=True)
        # SYNTHESIS + RISK CLUSTER/PROGRESS
        if verbose:
            print("\n[SYNTHESIS PHASE]", flush=True)
        user_prompt = (
            "SYNTHESIS PHASE: Based on all critiques and crossfire, output as JSON: "
            "{'refined_idea': ..., 'addressed_risks': [...], 'open_risks': [...], 'risk_clusters': {theme: [risks]}, 'progress': ...}.\n"
            "Summarize: are open risks truly novel or clustering to past ones? Which (if any) are only infinite regress or low-value? What degree of convergence?"
        )
        synthesis_seed = agent_seed(master_seed, f"{agent['name']}_synthesis")
        synthesis = await call_gpt(
            "Synthesis expert",
            user_prompt + f"\nCritiques: {critiques}\nCrossfires: {crossfires}\nGround truths: {ground_truths}\n",
            expect_json=True,
            seed=synthesis_seed,
        )
        if verbose:
            print(f"Refined Idea: {synthesis.get('refined_idea','')[:120]}", flush=True)
            print("Addressed risks:", synthesis.get('addressed_risks', []), flush=True)
            print("Open risks:", synthesis.get('open_risks', []), flush=True)
        risk_clusters = synthesis.get("risk_clusters", {})
        entropy = len({r for g in risk_clusters.values() for r in g})  # number of unique surviving risks
        board_entropy.append(entropy)
        # META-AGENT: CONVERGENCE/ENTROPY GOVERNANCE
        if verbose:
            print("[META-AGENT PHASE]", flush=True)
        meta_user_prompt = (
            "Meta-decision: Based on all critiques, risk clusters, and progress over all rounds so far:\n"
            "- Are new objections emerging that are truly orthogonal/novel?\n"
            "- Is entropy (number/diversity of open risks) increasing pointlessly, or converging to robust synthesis?\n"
            "- Are agents/roles covering all required epistemic archetypes?\n"
            "Output strict JSON: {'halt': true/false, 'rationale': '...', 'entropy': ..., 'coverage_audit': {...}}"
        )
        past_risks = [h.get('risk_clusters', {}) for h in history]
        meta_decision = await call_gpt(
            meta_agent['system'],
            meta_user_prompt +
            f"\nCurrent risk clusters: {risk_clusters}\nPast entropy: {board_entropy}" +
            f"\nRequired archetypes: {required_archetypes}\nPanel: {[a.get('archetype') for a in agents]}",
            expect_json=True,
            seed=seed+3,
        )
        if verbose:
            print(f"META-AGENT DECISION: {'HALT' if meta_decision.get('halt') else 'CONTINUE'}; RATIONALE: {meta_decision.get('rationale','NO RATIONALE')}", flush=True)
        # HISTORY/LOGGING
        history.append({
            "iteration": iteration+1,
            "critiques": critiques,
            "crossfire": crossfires,
            "synthesis": synthesis,
            "meta_decision": meta_decision,
            "user_answers": user_answers,
            "risk_clusters": risk_clusters,
            "entropy": entropy,
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
        "panel_log": panel_log,
        "history": history,
        "final": current,
        "required_archetypes": required_archetypes,
    })
    write_human_log_markdown(outdir/"summary.md", {
        "initial": premise,
        "process_instruction": process_instruction,
        "panel_log": panel_log,
        "history": history,
        "final": current,
    })
    if verbose:
        print(f"\nRun {run_id} COMPLETE. Final idea: {current[:180]}", flush=True)
    return history