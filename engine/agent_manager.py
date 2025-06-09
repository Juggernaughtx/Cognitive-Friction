# engine/agent_manager.py

import yaml
from engine.gpt_api import call_gpt

def load_board_config(path="agents_board.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["board_members"]

def load_user_agents(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)["agents"]

def load_required_archetypes(path="archetypes.yaml"):
    with open(path, "r") as f:
        yamldata = yaml.safe_load(f)
        return yamldata["required_archetypes"]

def _deduplicate_agents(agent_list):
    seen = set()
    out = []
    for agent in agent_list:
        k = (agent["name"].lower(), agent.get("archetype", "").lower())
        if k not in seen:
            out.append(agent)
            seen.add(k)
    return out

def _archetype_coverage(agents):
    # returns set of present archetype codes from all panel agents
    return {a["archetype"] for a in agents if a.get("archetype")}

def _required_archetype_codes(required_archetypes):
    # required_archetypes now is a list of dicts, with .code fields
    return set([a["code"] for a in required_archetypes])

async def check_and_augment_archetypes(agents, required_archetypes, board_members, premise, process_instruction, temperature, verbose=False):
    present = _archetype_coverage(agents)
    required_codes = _required_archetype_codes(required_archetypes)
    missing = required_codes - present
    log = []
    if missing and verbose:
        print("WARNING: Panel is missing required archetypes: ", missing)
    # Try to have the board propose an agent for each missing archetype
    for code in missing:
        # lookup object for logging
        archinfo = next((arc for arc in required_archetypes if arc["code"] == code), {"code": code})
        for bm in board_members:
            prompt = f"Business Premise: {premise}\nProcess: {process_instruction}\n" + \
                     f"A required archetype for deeper critique is missing: [{code}] ({archinfo.get('display','?')})\n" + \
                     f"Description: {archinfo.get('description', '')}\n" + \
                     f"Propose ONE agent with that archetype, strictly with fields: 'name', 'system', 'archetype', 'rationale'."
            try:
                candidate = await call_gpt(bm['system'], prompt, expect_json=True, temperature=temperature)
                if candidate and "archetype" in candidate and candidate["archetype"] == code:
                    log.append({"archetype_added": code, "by": bm["name"]})
                    if verbose:
                        print(f"Archetype `{code}` injected by Board: {candidate.get('name','UNKNOWN')} from {bm['name']}")
                    agents.append(candidate)
                    break
            except Exception:
                continue
    return _deduplicate_agents(agents), log

async def get_panel(board_members, premise, process_instruction, temperature, max_agents, threshold=2,
                    user_agents=None, required_archetypes=None, verbose=False):
    user_agents = user_agents or []
    proposals = []
    # Get codes for archetypes from the current required archetype object list
    present_archetypes = _archetype_coverage(user_agents)
    if verbose and present_archetypes:
        print("User-supplied panel archetypes: ", present_archetypes)
    initial_agents = _deduplicate_agents(user_agents)
    for bm in board_members:
        agents = await propose_agents(
            bm, premise, process_instruction, temperature, max_agents, present_archetypes=present_archetypes
        )
        valid_agents = []
        for a in agents:
            if "name" in a and "system" in a and "archetype" in a:
                valid_agents.append(a)
            else:
                if verbose:
                    print(f"Malformed agent from {bm['name']}: ", a)
        if agents:
            proposals.append({"board_member": bm["name"], "agents": valid_agents})
            initial_agents.extend(valid_agents)
    combined_agents = _deduplicate_agents(initial_agents)
    archetype_log = []
    if required_archetypes:
        combined_agents, archetype_log = await check_and_augment_archetypes(
            combined_agents, required_archetypes, board_members, premise, process_instruction, temperature, verbose=verbose
        )
    all_candidates = {}
    for prop in proposals:
        for agent in prop["agents"]:
            k = agent["name"].strip().lower()
            if k not in all_candidates:
                all_candidates[k] = {"agent": agent, "proposed_by": [prop["board_member"]]}
            else:
                all_candidates[k]["proposed_by"].append(prop["board_member"])
    selected = [v["agent"] for v in all_candidates.values() if len(v["proposed_by"]) >= threshold]
    combined = _deduplicate_agents(selected + combined_agents)
    panel_log = {
        "user_agents": user_agents,
        "board_proposals": proposals,
        "archetype_log": archetype_log,
        "final_panel": combined,
        "final_archetypes": sorted(_archetype_coverage(combined)),
    }
    if len(combined) > max_agents:
        combined = combined[:max_agents]
        if verbose: print(f"Panel truncated to max_agents={max_agents}")
    # Print final panel composition (since this is a core runtime feedback point)
    if verbose:
        print("\nFinal agent panel (archetype: name):")
        for agent in combined:
            print(f"- {agent.get('archetype','?')}: {agent['name']} [{agent.get('rationale','')[:60]}...]")
    return combined, proposals, panel_log

async def propose_agents(board_member, premise, process_instruction, temperature, max_agents, present_archetypes=None):
    pres_arch = list(present_archetypes) if present_archetypes else []
    user_prompt = f"""
    BUSINESS IDEA: {premise}
    PROCESS INSTRUCTION: {process_instruction}
    Already present archetype codes: {pres_arch}
    As {board_member['name']}, propose up to {max_agents} agents for critiquing this idea—
    each with a name, system prompt (one paragraph), rationale (one line), and archetype (one of: scenario_breaker, contrarian_adversary, quant_risk, fact_checker, etc).
    For each agent: object with keys: 'name', 'system', 'rationale', 'archetype'
    Each new archetype must have a rationale: What unique attack surface does it cover vs others?
    Output your answer STRICTLY as a JSON list under the key "panel_agents".
    """
    system_prompt = board_member["system"]
    result = await call_gpt(system_prompt, user_prompt, temperature=temperature, expect_json=True)
    return result.get("panel_agents", [])