# main.py -- Clean, single-source-of-truth argument/config management

import argparse
import asyncio
import os
from pathlib import Path
from engine.agent_manager import load_board_config, get_panel
from engine.controller import run_full_process, load_meta_agent
from engine.utils import load_yaml, file_hash
# ---- Central default values for all supported config keys ----
DEFAULTS = {
    "config": "config.yaml",
    "max_iter": 5,
    "multi_run": 1,
    "seed": 42,
    "verbose": False,
    "meta_agent": "meta_agent.yaml",
    "board": "agents_board.yaml",
    "agent_cap": 6,
    "board_threshold": 2,
    "board_temp": 0.7,
    "premise": None,
    "process_instruction": None,
    "user_agents": None,  # newly supported: YAML with user-defined initial agents/archetypes
    "required_archetypes": "archetypes.yaml",
}
# ----- Argument-to-config key mapping (for CLI <-> config merge) -----
ARG_TO_CONF = {
    "config": "config",
    "max_iter": "max_iter",
    "multi_run": "multi_run",
    "seed": "seed",
    "verbose": "verbose",
    "meta_agent": "meta_agent",
    "board": "board",
    "agent_cap": "agent_cap",
    "board_threshold": "board_threshold",
    "board_temp": "board_temp",
    "premise": "premise",
    "process_instruction": "process_instruction",
    "user_agents": "user_agents",
    "required_archetypes": "required_archetypes",
}
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="YAML config file")
    parser.add_argument("--max-iter", type=int, default=None)
    parser.add_argument("--multi-run", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true", default=None)
    parser.add_argument("--meta-agent", type=str, default=None)
    parser.add_argument("--board", type=str, default=None)
    parser.add_argument("--agent-cap", type=int, default=None)
    parser.add_argument("--board-threshold", type=int, default=None)
    parser.add_argument("--board-temp", type=float, default=None)
    parser.add_argument("--premise", type=str, default=None)
    parser.add_argument("--process-instruction", type=str, default=None)
    parser.add_argument("--user-agents", type=str, default=None, help="YAML file of initial user agent/archetypes")
    parser.add_argument("--required-archetypes", type=str, default=None, help="YAML file with required archetypes")
    return parser.parse_args()
def merge_config_and_args(cli_args, config: dict):
    """Merges CLI arguments with config, giving CLI priority, then config, then DEFAULTS."""
    final = {}
    for argname, confkey in ARG_TO_CONF.items():
        cli_val = getattr(cli_args, argname.replace('-', '_'), None)
        conf_val = config.get(confkey) if config else None
        default_val = DEFAULTS[confkey]
        final[confkey] = cli_val if cli_val is not None else conf_val if conf_val is not None else default_val
    return final
async def main():
    args = parse_args()
    # Step 1: Identify config file
    config_file = args.config or DEFAULTS["config"]
    if not os.path.isfile(config_file):
        print(f"ERROR: Config file '{config_file}' not found.")
        exit(1)
    config_data = load_yaml(config_file)
    # Step 2: Merge (CLI > config > defaults), all keys
    cfg = merge_config_and_args(args, config_data)
    # Step 3: Validate required keys
    missing_keys = [k for k in ("premise", "process_instruction") if not cfg.get(k)]
    if missing_keys:
        print(f"ERROR: Required fields missing: {', '.join(missing_keys)}. (Supply in config or CLI)")
        exit(1)
    # Step 4: Assemble run parameters
    max_iter = int(cfg["max_iter"])
    num_runs = int(cfg["multi_run"])
    seed = int(cfg["seed"])
    verbose = bool(cfg["verbose"])
    agent_cap = int(cfg["agent_cap"])
    board_threshold = int(cfg["board_threshold"])
    board_temp = float(cfg["board_temp"])
    meta_agent_path = cfg["meta_agent"]
    board_path = cfg["board"]
    premise = cfg["premise"]
    process_instruction = cfg["process_instruction"]
    # Step 5: Load YAML configs
    meta_agent = load_meta_agent(meta_agent_path)
    board_members = load_board_config(board_path)

    # ---- updated: Load user agents and required archetype list
    user_agents_path = cfg.get("user_agents")
    user_agents = []
    if user_agents_path:
        if not os.path.isfile(user_agents_path):
            print(f"ERROR: User agent archetype file '{user_agents_path}' not found.")
            exit(1)
        loaded = load_yaml(user_agents_path)
        if "agents" in loaded:
            user_agents = loaded["agents"]
        else:
            print(f"ERROR: Missing 'agents' key in '{user_agents_path}'")
            exit(1)
    required_archetypes_path = cfg.get("required_archetypes") or DEFAULTS["required_archetypes"]
    if not os.path.isfile(required_archetypes_path):
        print(f"ERROR: Archetypes file '{required_archetypes_path}' not found.")
        exit(1)
    req_arch_loaded = load_yaml(required_archetypes_path)
    if "required_archetypes" not in req_arch_loaded:
        print(f"ERROR: Missing 'required_archetypes' in '{required_archetypes_path}'")
        exit(1)
    required_archetypes = req_arch_loaded["required_archetypes"]

    # Step 6: Run
    for i in range(num_runs):
        run_id = f"run_{i+1:02d}_{file_hash(board_path)[:6]}"
        if verbose:
            print(f"\n***** Starting multi-run {i+1}/{num_runs} (seed={seed+i}) *****", flush=True)
            print("Building agent panel...", flush=True)
        agents, proposals, panel_log = await get_panel(
            board_members, premise, process_instruction, board_temp, agent_cap, board_threshold,
            user_agents=user_agents,
            required_archetypes=required_archetypes,
            verbose=verbose,
        )
        if verbose:
            print("[Panel chosen]:")
            for a in agents:
                print(f" - {a['name']} (archetype={a.get('archetype')}) — {a['system'][:90]}...")
            print("Proceeding to critique/debate process.", flush=True)
        await run_full_process(
            premise, process_instruction, agents, meta_agent,
            max_iter, run_id, seed+i, verbose,
            panel_log=panel_log,
            required_archetypes=required_archetypes,
        )
        if verbose:
            print(f"***** Finished run {i+1} ({run_id}) *****", flush=True)
if __name__ == "__main__":
    asyncio.run(main())