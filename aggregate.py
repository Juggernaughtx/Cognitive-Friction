# aggregate.py

import json
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def load_final_structs(log_dir: Path):
    runs = []
    for run_path in sorted(log_dir.glob("run_*/summary.json")):
        with open(run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            runs.append({
                "name": run_path.parent.name, 
                "final": data.get("final", ""), 
                "history": data.get("history", []),
                "converged": data.get("meta_agent_converged", False),
                "risks": data.get("risk_summary", [])
            })
    return runs

def summarize_meta_agent(runs, file_handle):
    file_handle.write("\n## Meta-Agent Process Insights Across Runs:\n")
    meta_decisions = []
    recommendations = []
    escalation_counts = 0
    for run in runs:
        meta_log = run.get("meta_agent_summary", [])
        for entry in meta_log:
            meta_decisions.append(entry.get("meta_decision", ""))
            rec = entry.get("recommendation", "")
            if rec:
                recommendations.append(rec)
                # Count escalation/changes suggested
                if "add" in rec or "escalate" in rec or "change" in rec:
                    escalation_counts += 1

    # Top meta-agent observations
    from collections import Counter
    dec_counter = Counter(meta_decisions)
    rec_counter = Counter(recommendations)

    file_handle.write("### Meta-Agent Decision Frequency:\n")
    for dec, ct in dec_counter.most_common():
        file_handle.write(f"- {dec}: {ct}x\n")
    file_handle.write("### Recommendations:\n")
    for rec, ct in rec_counter.most_common():
        file_handle.write(f"- {rec}: {ct}x\n")
    file_handle.write(f"\nEscalation/Process tweaks suggested by meta-agent in {escalation_counts} instances.\n")

    # Flag if certain types of panel dysfunction (e.g. premature convergence, excessive consensus) are common
    if escalation_counts > 0:
        file_handle.write("\n**Pattern Detected:** Meta-agent frequently requested more diversity/adversarial pressure. Consider increasing role or scenario randomization.\n")
def summarize_aggregate(runs, out_path):
    final_texts = [r["final"] for r in runs if r["final"] and len(r["final"].strip()) > 40]
    if not final_texts or len(final_texts) < 2:
        print("Not enough valid final proposals for aggregation—review agent and meta-agent configs.")
        return
    # Auto-cluster by final proposal similarity
    vect = TfidfVectorizer().fit_transform([r["final"] for r in runs])
    sim_matrix = cosine_similarity(vect)
    clusters, cluster_map = {}, {}
    cluster_id = 0
    threshold = 0.85
    for idx, final in enumerate([r["final"] for r in runs]):
        assigned = False
        for cid, members in clusters.items():
            if any(sim_matrix[idx, m] > threshold for m in members):
                clusters[cid].append(idx)
                cluster_map[idx] = cid
                assigned = True
                break
        if not assigned:
            clusters[cluster_id] = [idx]
            cluster_map[idx] = cluster_id
            cluster_id += 1

    # Flatten/aggregate major risk pattern
    all_unsolved = Counter(risk for r in runs for risk in r["risks"] if risk["status"] == "unresolved")
    # Compose report
    with open(out_path, "w") as f:
        f.write("# Cognitive Friction Engine: Aggregate Executive Summary\n\n")
        # Run-level summary table
        f.write("| Run | Converged? | Final Cluster | #Unsolved Risks |\n")
        for idx, r in enumerate(runs):
            cid = cluster_map[idx]
            f.write(f"| {r['name']} | {r['converged']} | {cid} | {len([x for x in r['risks'] if x['status']=='unresolved'])} |\n")
        f.write("\n## Recurrent Unresolved Risks Across Runs:\n")
        for risk, count in all_unsolved.most_common(10):
            f.write(f"- {risk} (in {count} runs)\n")
        f.write("\n## Proposal Clusters:\n")
        for cid, members in clusters.items():
            repr_idx = members[0]
            f.write(f"\n### Cluster {cid}: {len(members)} runs\n")
            f.write(f"Example Final Proposal:\n{runs[repr_idx]['final']}\n\n")
            summarize_meta_agent(runs, f)
        # Optionally detail logs behind a "Details" collapsible if you want

# In your actual workflow
def aggregate_and_save(log_dir, out_path="aggregate_report.md"):
    log_dir = Path(log_dir)
    runs = load_final_structs(log_dir)
    if not runs:
        print("No runs found.")
        return
    summarize_aggregate(runs, out_path)
    print(f"Aggregate report written to {out_path}")
