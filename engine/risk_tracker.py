# engine/risk_tracker.py

import json

class RiskTracker:
    def __init__(self):
        self.unique_risks = set()
        self.risk_history = []  # per iteration

    def add_risks(self, risk_list):
        """risk_list: list of strings or dicts"""
        flat = [json.dumps(r, sort_keys=True) if isinstance(r, dict) else str(r) for r in risk_list if r]
        self.unique_risks.update(flat)
        self.risk_history.append(set(flat))

    def risk_entropy(self):
        return len(self.unique_risks)

    def recent_novelty(self, n=2):
        """Returns True if any new risk found in past n rounds, else False"""
        if len(self.risk_history) < n + 1:
            return True
        last = self.risk_history[-n:]
        penultimate = set.union(*(self.risk_history[:-n] if len(self.risk_history) > n else set()))
        for rh in last:
            if not rh.issubset(penultimate):
                return True
        return False

    def is_repeat(self, risk_candidate):
        """Check if risk was previously seen"""
        key = json.dumps(risk_candidate, sort_keys=True) if isinstance(risk_candidate, dict) else str(risk_candidate)
        return key in self.unique_risks