# main.py

import argparse
import asyncio
import os
import random
import sys
import hashlib
import traceback
from pathlib import Path

from engine.controller import run_until_exhaustion, load_meta_agent
from engine.utils import (
    write_human_log_markdown, atomic_write_json,
    file_hash, log_exception, validate_agents_config, load_yaml_config
)
from agent_picker import load_board_config, get_agent_panel_from_board   # <<=== (NEW)
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="YAML file with all run arguments")
    parser.add_argument("--static-premise", type=str, default=None, help="Business idea text")
    parser.add_argument("--static-premise-file", type=str, default=None, help="File with business idea")
    parser.add_argument("--process-instruction", type=str, default=None, help="Process instruction")
    parser.add_argument("--process-instruction-file", type=str, default=None, help="File with process instruction")
    parser.add_argument("--max-iter", type=int, default=None)
    parser.add_argument("--multi-run", type=int, default=None)
    parser.add_argument("--agents", type=str, default=None)
    parser.add_argument("--meta-agent", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--board", type=str, default=None, help="YAML for board member config (NEW)")
    parser.add_argument("--agent-cap", type=int, default=6, help="Max number of generated agents (NEW)")
    parser.add_argument("--board-threshold", type=int, default=2, help="Votes needed for an agent to make the panel (NEW)")
    parser.add_argument("--board-temp", type=float, default=0.6, help="LLM temp for board generation (NEW)")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

def get_final_value(args, config, key, file_opt=None):
    v = getattr(args, key)
    if v: return v
    if file_opt:
        file_v = getattr(args, file_opt)
        if file_v:
            with open(file_v, "r", encoding="utf-8") as f:
                return f.read()
    if config and key in config:
        return config[key]
    return None

def build_summary(args, process_instruction, history, seed, config_hashes):
    return {
        "initial": args.static_premise,
        "process_instruction": process_instruction,
        "history": history,
        "final": history[-1]["proposal"] if history else "",
        "meta_agent_summary": [h.get("meta_decision", {}) for h in history],
        "random_seed": seed,
        "config_hashes": config_hashes,
    }

def log_run_output(run_id, summary_dict):
    run_log_dir = Path("logs") / run_id
    run_log_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(run_log_dir / "summary.json", summary_dict)
    write_human_log_markdown(run_log_dir / "summary.pretty.json", summary_dict)

async def single_full_run(run_idx, args, process_instruction, agents, meta_agent, master_seed, config_hashes):
    run_id = f"run_{run_idx:02d}_{str(hashlib.md5(str(master_seed).encode()).hexdigest()[:8])}"
    try:
        history = await run_until_exhaustion(
            static_premise=args.static_premise,
            process_instruction=process_instruction,
            max_iterations=args.max_iter,
            agents=agents,
            meta_agent=meta_agent,
            verbose=args.verbose,
            run_id=run_id,
            master_seed=master_seed
        )
        summary = build_summary(args, process_instruction, history, master_seed, config_hashes)
        log_run_output(run_id, summary)
    except Exception as e:
        log_exception(f"logs/{run_id}_error.log", e)

async def multi_run(args, config):
    # --- Static meta-agent config as before ---
    meta_agent_path = args.meta_agent or (config["meta_agent"] if config and "meta_agent" in config else "meta_agent.yaml")
    meta_agent = load_meta_agent(meta_agent_path)

    # --- NEW: Load Supreme Board, generate agent panel before every run or once ---
    board_path = args.board or (config["board"] if config and "board" in config else "agents_board.yaml")
    board_members = load_board_config(board_path)

    main_seed = args.seed if args.seed is not None else (config["seed"] if config and "seed" in config else int.from_bytes(os.urandom(4), "little"))
    num_runs = args.multi_run or (config["multi_run"] if config and "multi_run" in config else 1)
    agent_cap = args.agent_cap or (config["agent_cap"] if config and "agent_cap" in config else 6)
    board_temp = args.board_temp or (config["board_temp"] if config and "board_temp" in config else 0.6)
    board_threshold = args.board_threshold or (config["board_threshold"] if config and "board_threshold" in config else 2)

    # --- We generate new agents for every run to allow randomness; if you want to use same agents for all, move outside loop. ---

    for run_idx in range(1, int(num_runs)+1):
        sub_seed = int(main_seed) + run_idx * 10007

        # --- Supreme Board: build agent panel for this run ---
        agents, proposals = await get_agent_panel_from_board(
            board_members,
            args.static_premise,
            args.process_instruction,
            temperature=board_temp,
            max_agents=agent_cap,
            voting_threshold=board_threshold
        )
        # For auditability, save the chosen agents and raw proposals
        run_id = f"run_{run_idx:02d}_{str(hashlib.md5(str(sub_seed).encode()).hexdigest()[:8])}"
        run_log_dir = Path("logs") / run_id
        run_log_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(run_log_dir / "board_proposals.json", proposals)
        atomic_write_json(run_log_dir / "agents.yaml", {"agents": agents})

        config_hashes = {
            "agents_board.yaml": file_hash(board_path),
            "meta_agent.yaml": file_hash(meta_agent_path)
        }
        await single_full_run(run_idx, args, args.process_instruction, agents, meta_agent, sub_seed, config_hashes)

if __name__ == "__main__":
    args = parse_args()
    config = None
    if args.config:
        config = load_yaml_config(args.config)
    # Determine static_premise and process_instruction with fallback to files/config
    args.static_premise = get_final_value(args, config, "static_premise", "static_premise_file")
    args.process_instruction = get_final_value(args, config, "process_instruction", "process_instruction_file")
    args.max_iter = args.max_iter or (config["max_iter"] if config and "max_iter" in config else 10)
    args.multi_run = args.multi_run or (config["multi_run"] if config and "multi_run" in config else 1)
    args.verbose = args.verbose or (config["verbose"] if config and "verbose" in config else False)
    args.meta_agent = args.meta_agent or (config["meta_agent"] if config and "meta_agent" in config else None)
    args.seed = args.seed or (config["seed"] if config and "seed" in config else None)
    args.board = args.board or (config["board"] if config and "board" in config else None)
    args.agent_cap = args.agent_cap or (config["agent_cap"] if config and "agent_cap" in config else 6)
    args.board_threshold = args.board_threshold or (config["board_threshold"] if config and "board_threshold" in config else 2)
    args.board_temp = args.board_temp or (config["board_temp"] if config and "board_temp" in config else 0.6)

    if not args.static_premise or not args.process_instruction:
        print("ERROR: static_premise and process_instruction are required, by CLI, file, or config.")
        sys.exit(1)
    try:
        asyncio.run(multi_run(args, config))
    except Exception as e:
        log_exception("logs/fatal_error.log", e)
        sys.exit(1)