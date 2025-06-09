# agent_picker.py

import asyncio
import yaml
from engine.gpt import call_gpt
from engine.utils import atomic_write_json
import re

def load_board_config(path="agents_board.yaml"):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["board_members"]

def clean_markdown_fence(text):
    """
    Removes leading/trailing markdown codefences (``` or ```yaml) from text.
    Handles leading/trailing whitespace.
    """
    # Remove leading ```
    text = re.sub(r"^\s*```(?:yaml)?\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    # Remove trailing ```
    text = re.sub(r"\s*```\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text.strip()

async def propose_agents(board_member, premise, process_instruction, temperature=0.6, max_agents=6):
    user_prompt = f"""
    Business idea: {premise}
    Process instruction: {process_instruction}

    You are a member of the Supreme Board tasked with creating the initial debate panel (panel of agents/personas). 
    Your mission: Propose up to {max_agents} distinct personas (roles), each with a name and a one-paragraph 
    system prompt. Each should justify their relevance for maximizing epistemic friction and adversarial discovery.
    For each, give:
    - name
    - system prompt
    - rationale (one line)

    Format as a YAML list under 'panel_agents'.
    Avoid silly, irrelevant, or redundant roles. 

    IMPORTANT: ABSOLUTELY DO NOT propose or include any agent/persona whose primary focus is legal, regulatory, compliance, HR/human resources, public relations, marketing, customer service, user experience, or any other commercial, policy, or external stakeholder perspective.
    Each agent must have a *clearly stated technical, quantitative, financial, data-driven, modeling, system reliability, or adversarial reasoning specialty* directly relevant to the internal epistemic analysis of the business idea.

    This system is strictly for private, non-commercial technical/quant investigation. Commercial, legal, HR, PR, and public/customer-facing viewpoints are prohibited.
    """

    # user_prompt = f"""
    # Business idea: {premise}
    # Process instruction: {process_instruction}

    # You are a member of the Supreme Board tasked with creating the initial debate panel (panel of agents/personas). 
    # Your mission: Propose up to {max_agents} distinct personas (roles), each with a name and a system prompt. 
    # Each system prompt and each rationale must be NO MORE THAN ONE SENTENCE.
    # Each should justify their relevance for maximizing epistemic friction and adversarial discovery.
    # For each, give:
    # - name
    # - system prompt (ONE SENTENCE)
    # - rationale (ONE SENTENCE)

    # Format as a YAML list under 'panel_agents'.
    # Avoid silly, irrelevant, or redundant roles. 
    # """

    system_prompt = board_member["system"]
    resp = await call_gpt(system_prompt, user_prompt, temperature=temperature)
    # --- Validate YAML format ---
    safe_resp = clean_markdown_fence(resp)
    try:
        data = yaml.safe_load(safe_resp)
        return data["panel_agents"]
    except Exception as e:
        print(f"Error parsing agent proposal YAML: {e}")
        print("--- Raw output was ---\n", resp)
        return []
    
async def get_agent_panel_from_board(board_members, premise, process_instruction, temperature, max_agents, voting_threshold=2):
    proposals = []
    # Step 1: Each board member proposes a panel
    for bm in board_members:
        agents = await propose_agents(bm, premise, process_instruction, temperature=temperature, max_agents=max_agents)
        if agents:
            proposals.append({"board_member": bm["name"], "agents": agents})
    # Step 2: (Optional) Aggregate/cross-examine/vote. For brevity, just take union and prune near-duplicates.
    all_candidates = {}
    for prop in proposals:
        for agent in prop["agents"]:
            k = agent["name"].strip().lower()
            # De-duplicate by name (improve: hash on role/desc)
            if k not in all_candidates:
                all_candidates[k] = {"agent": agent, "proposed_by": [prop["board_member"]]}
            else:
                all_candidates[k]["proposed_by"].append(prop["board_member"])
    # Keep only agents proposed by at least N board members (voting_threshold) -- adjust as desired
    selected = [
        v["agent"] for v in all_candidates.values()
        if len(v["proposed_by"]) >= voting_threshold
    ]
    # Cap if needed
    if len(selected) > max_agents:
        selected = selected[:max_agents]
    # If not enough approved, fallback: take agents proposed by the most members, then fill with singles as needed
    if len(selected) < 2:
        selected = [v["agent"] for v in sorted(all_candidates.values(), key=lambda x: len(x["proposed_by"]), reverse=True)][:max_agents]
    return selected, proposals
