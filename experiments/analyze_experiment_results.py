#!/usr/bin/env python3
"""
Analyze results from empirical laboratory experiments.
Provides statistical analysis and visualization of metrics.
"""

import json
import numpy as np
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


class ExperimentAnalyzer:
    """Analyze experiment results for patterns and insights."""
    
    def __init__(self):
        self.client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
        self.results = []
    
    def load_experiment_data(self, experiment_id: str) -> Dict[str, Any]:
        """Load data from a specific experiment."""
        # Query metric snapshots
        result = self.client.send_event("state:entity:query", {
            "type": "metric_snapshot",
            "filter": {"experiment_id": experiment_id}
        })
        
        snapshots = result.get("entities", [])
        
        # Query interaction history
        result = self.client.send_event("state:entity:query", {
            "type": "interaction",
            "filter": {"experiment_id": experiment_id}
        })
        
        interactions = result.get("entities", [])
        
        return {
            "experiment_id": experiment_id,
            "snapshots": snapshots,
            "interactions": interactions,
            "timestamp": datetime.now().isoformat()
        }
    
    def analyze_fairness_evolution(self, snapshots: List[Dict]) -> Dict[str, Any]:
        """Analyze how fairness metrics evolved over time."""
        gini_values = []
        timestamps = []
        
        for snap in snapshots:
            if snap.get("metric_type") == "gini":
                result = snap.get("result", {})
                if "gini" in result:
                    gini_values.append(result["gini"])
                    timestamps.append(snap.get("timestamp"))
        
        if not gini_values:
            return {"error": "No Gini data found"}
        
        # Calculate trends
        gini_array = np.array(gini_values)
        
        return {
            "initial_gini": gini_values[0] if gini_values else None,
            "final_gini": gini_values[-1] if gini_values else None,
            "mean_gini": float(np.mean(gini_array)),
            "std_gini": float(np.std(gini_array)),
            "max_gini": float(np.max(gini_array)),
            "min_gini": float(np.min(gini_array)),
            "trend": "increasing" if len(gini_values) > 1 and gini_values[-1] > gini_values[0] else "stable",
            "samples": len(gini_values)
        }
    
    def analyze_dominance_patterns(self, interactions: List[Dict]) -> Dict[str, Any]:
        """Analyze dominance and hierarchy patterns."""
        dominance_counts = {}
        submission_counts = {}
        
        for interaction in interactions:
            props = interaction.get("properties", {})
            outcome = props.get("outcome")
            from_agent = props.get("agent_from")
            to_agent = props.get("agent_to")
            
            if outcome in ["won", "dominated"]:
                dominance_counts[from_agent] = dominance_counts.get(from_agent, 0) + 1
                submission_counts[to_agent] = submission_counts.get(to_agent, 0) + 1
            elif outcome in ["lost", "submitted"]:
                submission_counts[from_agent] = submission_counts.get(from_agent, 0) + 1
                dominance_counts[to_agent] = dominance_counts.get(to_agent, 0) + 1
        
        # Identify hierarchy
        all_agents = set(dominance_counts.keys()) | set(submission_counts.keys())
        agent_scores = {}
        
        for agent in all_agents:
            wins = dominance_counts.get(agent, 0)
            losses = submission_counts.get(agent, 0)
            total = wins + losses
            agent_scores[agent] = wins / total if total > 0 else 0.5
        
        # Sort by dominance score
        hierarchy = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "hierarchy": hierarchy,
            "dominant_agent": hierarchy[0][0] if hierarchy else None,
            "subordinate_agent": hierarchy[-1][0] if hierarchy else None,
            "dominance_spread": hierarchy[0][1] - hierarchy[-1][1] if len(hierarchy) > 1 else 0,
            "total_interactions": len(interactions)
        }
    
    def detect_exploitation_signals(self, data: Dict[str, Any]) -> List[str]:
        """Detect signals of exploitation in the data."""
        signals = []
        
        # Check fairness metrics
        fairness = data.get("fairness_analysis", {})
        if fairness.get("final_gini", 0) > 0.4:
            signals.append("high_inequality")
        
        if fairness.get("trend") == "increasing" and fairness.get("final_gini", 0) > fairness.get("initial_gini", 0) + 0.2:
            signals.append("rapidly_increasing_inequality")
        
        # Check dominance patterns
        dominance = data.get("dominance_analysis", {})
        if dominance.get("dominance_spread", 0) > 0.7:
            signals.append("extreme_dominance")
        
        # Check resource concentration
        if "resource_hoarding" in str(data):
            signals.append("resource_hoarding_detected")
        
        return signals
    
    def generate_summary_report(self, experiment_id: str) -> Dict[str, Any]:
        """Generate a comprehensive summary report."""
        # Load data
        data = self.load_experiment_data(experiment_id)
        
        # Analyze different aspects
        fairness_analysis = self.analyze_fairness_evolution(data["snapshots"])
        dominance_analysis = self.analyze_dominance_patterns(data["interactions"])
        exploitation_signals = self.detect_exploitation_signals({
            "fairness_analysis": fairness_analysis,
            "dominance_analysis": dominance_analysis
        })
        
        # Generate report
        report = {
            "experiment_id": experiment_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_interactions": len(data["interactions"]),
                "total_snapshots": len(data["snapshots"]),
                "initial_gini": fairness_analysis.get("initial_gini"),
                "final_gini": fairness_analysis.get("final_gini"),
                "inequality_change": fairness_analysis.get("final_gini", 0) - fairness_analysis.get("initial_gini", 0),
                "dominant_agent": dominance_analysis.get("dominant_agent"),
                "exploitation_detected": len(exploitation_signals) > 0,
                "exploitation_signals": exploitation_signals
            },
            "fairness_analysis": fairness_analysis,
            "dominance_analysis": dominance_analysis,
            "key_findings": self.generate_key_findings(fairness_analysis, dominance_analysis, exploitation_signals)
        }
        
        return report
    
    def generate_key_findings(self, fairness: Dict, dominance: Dict, signals: List[str]) -> List[str]:
        """Generate key findings from the analysis."""
        findings = []
        
        # Fairness findings
        if fairness.get("trend") == "increasing":
            findings.append(f"Inequality increased from {fairness.get('initial_gini', 0):.3f} to {fairness.get('final_gini', 0):.3f}")
        else:
            findings.append("Inequality remained stable throughout experiment")
        
        # Dominance findings
        if dominance.get("dominance_spread", 0) > 0.5:
            findings.append(f"Clear hierarchy emerged with {dominance.get('dominant_agent')} as dominant")
        else:
            findings.append("No clear dominance hierarchy emerged")
        
        # Exploitation findings
        if signals:
            findings.append(f"Exploitation signals detected: {', '.join(signals)}")
        else:
            findings.append("No clear exploitation patterns detected")
        
        # Overall assessment
        if fairness.get("final_gini", 0) < 0.2 and not signals:
            findings.append("System maintained fairness - cooperation appears possible")
        elif len(signals) >= 2:
            findings.append("Multiple exploitation indicators - suggests inherent tendency")
        else:
            findings.append("Mixed results - exploitation may be conditional")
        
        return findings
    
    def compare_experiments(self, exp_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple experiments to identify patterns."""
        comparisons = []
        
        for exp_id in exp_ids:
            report = self.generate_summary_report(exp_id)
            comparisons.append({
                "id": exp_id,
                "final_gini": report["summary"]["final_gini"],
                "inequality_change": report["summary"]["inequality_change"],
                "exploitation": report["summary"]["exploitation_detected"],
                "dominant_agent": report["summary"]["dominant_agent"]
            })
        
        # Analyze patterns across experiments
        gini_values = [c["final_gini"] for c in comparisons if c["final_gini"] is not None]
        exploitation_rate = sum(1 for c in comparisons if c["exploitation"]) / len(comparisons) if comparisons else 0
        
        return {
            "experiments_compared": len(exp_ids),
            "mean_final_gini": np.mean(gini_values) if gini_values else None,
            "exploitation_rate": exploitation_rate,
            "comparisons": comparisons,
            "pattern": self.identify_pattern(exploitation_rate, gini_values)
        }
    
    def identify_pattern(self, exploitation_rate: float, gini_values: List[float]) -> str:
        """Identify overall pattern from experiments."""
        mean_gini = np.mean(gini_values) if gini_values else 0
        
        if exploitation_rate < 0.3 and mean_gini < 0.3:
            return "Cooperation dominant - exploitation not inherent"
        elif exploitation_rate > 0.7 and mean_gini > 0.4:
            return "Exploitation dominant - may be inherent tendency"
        elif exploitation_rate > 0.5:
            return "Mixed with exploitation tendency - conditional factors important"
        else:
            return "Mixed with cooperation tendency - design matters"


def print_report(report: Dict[str, Any]):
    """Pretty print an analysis report."""
    print("\n" + "="*60)
    print("📊 EXPERIMENT ANALYSIS REPORT")
    print("="*60)
    
    summary = report.get("summary", {})
    print(f"\nExperiment ID: {report.get('experiment_id', 'Unknown')}")
    print(f"Timestamp: {report.get('timestamp', 'Unknown')}")
    
    print("\n📈 Key Metrics:")
    print(f"  • Initial Gini: {summary.get('initial_gini', 0):.3f}")
    print(f"  • Final Gini: {summary.get('final_gini', 0):.3f}")
    print(f"  • Change: {summary.get('inequality_change', 0):+.3f}")
    print(f"  • Interactions: {summary.get('total_interactions', 0)}")
    
    print("\n⚠️ Exploitation Analysis:")
    if summary.get("exploitation_detected"):
        print(f"  • DETECTED - Signals: {', '.join(summary.get('exploitation_signals', []))}")
    else:
        print("  • Not detected")
    
    print("\n🔍 Key Findings:")
    for finding in report.get("key_findings", []):
        print(f"  • {finding}")
    
    print("\n" + "="*60)


def main():
    """Main analysis function."""
    analyzer = ExperimentAnalyzer()
    
    print("🔬 Empirical Laboratory - Experiment Analysis Tool")
    print("="*50)
    
    # In a real scenario, you would:
    # 1. Load experiment IDs from a database or file
    # 2. Analyze each experiment
    # 3. Compare results across experiments
    # 4. Generate insights about exploitation vs cooperation
    
    # For demo, analyze a test experiment
    print("\nAnalyzing test experiment data...")
    
    # Generate mock report for demonstration
    mock_report = {
        "experiment_id": "test_demo",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "initial_gini": 0.0,
            "final_gini": 0.35,
            "inequality_change": 0.35,
            "total_interactions": 50,
            "exploitation_detected": True,
            "exploitation_signals": ["high_inequality", "extreme_dominance"],
            "dominant_agent": "agent_alpha"
        },
        "key_findings": [
            "Inequality increased from 0.000 to 0.350",
            "Clear hierarchy emerged with agent_alpha as dominant",
            "Exploitation signals detected: high_inequality, extreme_dominance",
            "Multiple exploitation indicators - suggests inherent tendency"
        ]
    }
    
    print_report(mock_report)
    
    print("\n💡 Analysis complete!")
    print("\nThis tool helps answer:")
    print("  • Is exploitation inherent or conditional?")
    print("  • What conditions trigger cooperation vs competition?")
    print("  • Can system design prevent exploitation?")


if __name__ == "__main__":
    main()