# engine/utils.py

import json
import tempfile
import os
import hashlib
import logging
import yaml, re

def atomic_write_json(path, data):
    tmp = tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(path))
    try:
        json.dump(data, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, path)
    finally:
        if os.path.exists(tmp.name): os.remove(tmp.name)

def write_json_human(path, data):
    with open(path, "w",encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def agent_seed(master_seed, agent_id):
    combo = f"{master_seed}:{agent_id}".encode("utf-8")
    return int(hashlib.md5(combo).hexdigest()[:8], 16)

def log_exception(logfile, e):
    import traceback
    with open(logfile, "a") as f:
        f.write(traceback.format_exc())

def validate_agents_config(config_path="agents.yaml"):
    REQUIRED_AGENT_FIELDS = {"name", "system"}
    with open(config_path) as f:
        data = yaml.safe_load(f)
    for agent in data.get("agents", []):
        missing = REQUIRED_AGENT_FIELDS - set(agent)
        if missing:
            raise ValueError(f"Agent missing fields: {missing}")

def load_yaml_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def write_human_log_markdown(path, data):
    """Write a plaintext Markdown log with unescaped newlines, for human reading."""
    def _section(title, content):
        return f"## {title}\n\n{content.strip()}\n\n"

    def _verbatim_block(label, content):
        return f"### {label}\n\n```\n{content.strip()}\n```\n\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Cognitive Friction Engine Human Log\n\n")
        if "initial" in data:
            f.write(_section("Initial Premise", data['initial']))
        if "process_instruction" in data:
            f.write(_section("Process Instruction", data['process_instruction']))
        if "history" in data:
            for step in data['history']:
                iter_num = step.get('iteration', '?')
                f.write(f"\n## Iteration {iter_num}\n\n")
                critiques = step.get('critiques', {})
                crossfire = step.get('crossfire', {})
                synthesis = step.get('synthesis', "")
                meta_decision = step.get('meta_decision', {})

                if critiques:
                    for agent, text in critiques.items():
                        f.write(_verbatim_block(f"Critique by {agent}", text))
                if crossfire:
                    for agent, text in crossfire.items():
                        f.write(_verbatim_block(f"Crossfire by {agent}", text))
                if synthesis:
                    f.write(_verbatim_block("SYNTHESIS", synthesis))
                if meta_decision:
                    f.write(_verbatim_block("META-DECISION", str(meta_decision)))
        if "final" in data:
            f.write(_section("FINAL RESULT", data['final']))