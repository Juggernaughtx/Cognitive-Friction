# engine/agent_manager.py

import yaml
from engine.gpt_api import call_gpt

def load_board_config(path="agents_board.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["board_members"]

async def propose_agents(board_member, premise, process_instruction, temperature, max_agents):
    user_prompt = f"""
    BUSINESS IDEA: {premise}
    PROCESS INSTRUCTION: {process_instruction}

    As {board_member['name']}, propose up to {max_agents} agents for critiquing this idea—
    each with a name, system prompt (one paragraph), and rationale (one line).
    Include agents of diverse, *quantitative or adversarial specialties* (no legal, HR, PR, etc).
    Output your answer STRICTLY as a JSON list under the key "panel_agents".
    For each agent, output as an object with keys: 'name', 'system' (the system prompt, 1 paragraph), 'rationale' (1 line)
    """
    system_prompt = board_member["system"]
    result = await call_gpt(system_prompt, user_prompt, temperature=temperature, expect_json=True)
    return result.get("panel_agents", [])

async def get_panel(board_members, premise, process_instruction, temperature, max_agents, threshold=2):
    proposals = []
    for bm in board_members:
        agents = await propose_agents(bm, premise, process_instruction, temperature, max_agents)
        valid_agents = []
        for agent in agents:
            if "name" in agent and "system" in agent:
                valid_agents.append(agent)
            else:
                # Log or raise detailed error here
                raise ValueError(f"Malformed agent definition: {agent}")
        if agents:
            proposals.append({"board_member": bm["name"], "agents": agents})

    all_candidates = {}
    for prop in proposals:
        for agent in prop["agents"]:
            k = agent["name"].strip().lower()
            if k not in all_candidates:
                all_candidates[k] = {"agent": agent, "proposed_by": [prop["board_member"]]}
            else:
                all_candidates[k]["proposed_by"].append(prop["board_member"])

    selected = [v["agent"] for v in all_candidates.values() if len(v["proposed_by"]) >= threshold]
    if len(selected) > max_agents:
        selected = selected[:max_agents]
    if len(selected) < 2:
        selected = [v["agent"] for v in sorted(all_candidates.values(), key=lambda x: len(x["proposed_by"]), reverse=True)][:max_agents]
    return selected, proposals