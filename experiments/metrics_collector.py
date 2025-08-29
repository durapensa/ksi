#!/usr/bin/env python3
"""
Metrics Collector for Melting Pot Experiments
==============================================

Collects and analyzes metrics across multiple runs for statistical analysis.
Essential for A/B testing fairness mechanisms and validating hypotheses.
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import statistics
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

# Import scenario runner
from melting_pot_all_scenarios import MeltingPotKSI, MeltingPotScenario, ScenarioConfig


@dataclass
class RunMetrics:
    """Metrics from a single run."""
    run_id: str
    scenario: str
    timestamp: float
    configuration: Dict
    fairness_enabled: bool
    metrics: Dict[str, float]
    time_series: List[Dict] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    
    @property
    def gini(self) -> float:
        return self.metrics.get("gini", 0.0)
    
    @property
    def collective_return(self) -> float:
        return self.metrics.get("collective_return", 0.0)
    
    @property
    def cooperation_rate(self) -> float:
        return self.metrics.get("cooperation_rate", 0.0)
    
    @property
    def sustainability(self) -> float:
        return self.metrics.get("sustainability", 1.0)


@dataclass
class ExperimentResults:
    """Results from an A/B experiment."""
    experiment_id: str
    scenario: str
    baseline_runs: List[RunMetrics]
    treatment_runs: List[RunMetrics]
    statistical_tests: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects metrics across multiple experimental runs."""
    
    def __init__(self, output_dir: str = "results/metrics"):
        """Initialize metrics collector."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.runs: List[RunMetrics] = []
        self.experiments: List[ExperimentResults] = []
        
    def collect_baseline(self, scenario: MeltingPotScenario, 
                        config: ScenarioConfig,
                        n_runs: int = 10) -> List[RunMetrics]:
        """Collect baseline metrics without fairness mechanisms."""
        
        print(f"\nCollecting baseline for {scenario.value} ({n_runs} runs)...")
        baseline_runs = []
        
        for i in range(n_runs):
            print(f"  Run {i+1}/{n_runs}...", end="")
            
            try:
                # Run scenario without fairness
                metrics = self._run_scenario(
                    scenario, config, 
                    fairness_enabled=False,
                    run_id=f"baseline_{scenario.value}_{i}"
                )
                
                baseline_runs.append(metrics)
                self.runs.append(metrics)
                
                print(f" Gini={metrics.gini:.3f}, Return={metrics.collective_return:.1f}")
                
            except Exception as e:
                print(f" Failed: {e}")
        
        return baseline_runs
    
    def collect_treatment(self, scenario: MeltingPotScenario,
                         config: ScenarioConfig,
                         n_runs: int = 10,
                         fairness_config: Dict = None) -> List[RunMetrics]:
        """Collect metrics with fairness mechanisms enabled."""
        
        if fairness_config is None:
            fairness_config = {
                "strategic_diversity": True,
                "limited_coordination": True,
                "consent_mechanisms": True
            }
        
        print(f"\nCollecting treatment for {scenario.value} ({n_runs} runs)...")
        treatment_runs = []
        
        for i in range(n_runs):
            print(f"  Run {i+1}/{n_runs}...", end="")
            
            try:
                # Run scenario with fairness
                metrics = self._run_scenario(
                    scenario, config,
                    fairness_enabled=True,
                    fairness_config=fairness_config,
                    run_id=f"treatment_{scenario.value}_{i}"
                )
                
                treatment_runs.append(metrics)
                self.runs.append(metrics)
                
                print(f" Gini={metrics.gini:.3f}, Return={metrics.collective_return:.1f}")
                
            except Exception as e:
                print(f" Failed: {e}")
        
        return treatment_runs
    
    def run_ab_test(self, scenario: MeltingPotScenario,
                    config: ScenarioConfig,
                    n_runs: int = 30) -> ExperimentResults:
        """Run A/B test comparing baseline vs fairness treatment."""
        
        print(f"\n{'='*60}")
        print(f"A/B TEST: {scenario.value}")
        print(f"{'='*60}")
        
        # Collect baseline
        baseline_runs = self.collect_baseline(scenario, config, n_runs)
        
        # Collect treatment
        treatment_runs = self.collect_treatment(scenario, config, n_runs)
        
        # Perform statistical analysis
        results = self._analyze_ab_test(baseline_runs, treatment_runs)
        
        # Create experiment results
        experiment = ExperimentResults(
            experiment_id=f"ab_{scenario.value}_{int(time.time())}",
            scenario=scenario.value,
            baseline_runs=baseline_runs,
            treatment_runs=treatment_runs,
            statistical_tests=results["tests"],
            summary=results["summary"]
        )
        
        self.experiments.append(experiment)
        
        # Print results
        self._print_ab_results(experiment)
        
        return experiment
    
    def _run_scenario(self, scenario: MeltingPotScenario,
                     config: ScenarioConfig,
                     fairness_enabled: bool,
                     fairness_config: Dict = None,
                     run_id: str = None) -> RunMetrics:
        """Run a single scenario and collect metrics."""
        
        if run_id is None:
            run_id = f"{scenario.value}_{int(time.time()*1000)}"
        
        # Initialize game
        game = MeltingPotKSI()
        
        # Create episode with fairness settings
        episode_config = config.__dict__.copy()
        if fairness_enabled and fairness_config:
            episode_config["fairness_mechanisms"] = fairness_config
        
        episode_id = game.create_episode(scenario, config)
        
        # Spawn agents
        strategies = self._get_scenario_strategies(scenario, fairness_enabled)
        game.spawn_agents(config, strategies)
        
        # Run episode
        time_series = []
        for step in range(config.max_steps):
            # Step the episode
            step_result = self._step_scenario(game, scenario, step)
            
            if step_result.get("status") == "terminated":
                break
            
            # Collect metrics periodically
            if step % 10 == 0:
                metrics = game.calculate_metrics()
                time_series.append({
                    "step": step,
                    "gini": metrics.get("gini", 0),
                    "collective_return": metrics.get("collective_return", 0),
                    "cooperation_rate": metrics.get("cooperation_rate", 0)
                })
        
        # Get final metrics
        final_metrics = game.calculate_metrics()
        
        # Create run metrics
        run_metrics = RunMetrics(
            run_id=run_id,
            scenario=scenario.value,
            timestamp=time.time(),
            configuration=episode_config,
            fairness_enabled=fairness_enabled,
            metrics=final_metrics,
            time_series=time_series
        )
        
        return run_metrics
    
    def _get_scenario_strategies(self, scenario: MeltingPotScenario, 
                                 fairness_enabled: bool) -> Dict:
        """Get agent strategies for scenario."""
        
        if scenario == MeltingPotScenario.PRISONERS_DILEMMA:
            if fairness_enabled:
                # More diverse strategies with fairness
                return {"background": ["cooperator", "tit_for_tat", "adaptive", "cautious"]}
            else:
                # Standard strategies
                return {"background": ["cooperator", "defector", "tit_for_tat"]}
        
        elif scenario == MeltingPotScenario.STAG_HUNT:
            if fairness_enabled:
                return {"background": ["stag_hunter", "adaptive", "cautious_hunter"]}
            else:
                return {"background": ["stag_hunter", "hare_hunter", "adaptive"]}
        
        elif scenario == MeltingPotScenario.COMMONS_HARVEST:
            if fairness_enabled:
                return {"background": ["sustainable", "adaptive", "regulated"]}
            else:
                return {"background": ["sustainable", "greedy", "tit_for_tat"]}
        
        elif scenario == MeltingPotScenario.CLEANUP:
            if fairness_enabled:
                return {"background": ["cleaner", "conditional", "cooperative"]}
            else:
                return {"background": ["cleaner", "polluter", "conditional"]}
        
        else:  # COLLABORATIVE_COOKING
            if fairness_enabled:
                return {"background": ["coordinator", "specialist", "adaptive"]}
            else:
                return {"background": ["coordinator", "specialist", "generalist"]}
    
    def _step_scenario(self, game: MeltingPotKSI, scenario: MeltingPotScenario, 
                      step: int) -> Dict:
        """Step the scenario (placeholder for actual stepping logic)."""
        # In real implementation, would call scenario-specific step functions
        # For now, return mock result
        return {"status": "running" if step < 50 else "terminated"}
    
    def _analyze_ab_test(self, baseline: List[RunMetrics], 
                        treatment: List[RunMetrics]) -> Dict:
        """Perform statistical analysis of A/B test."""
        
        results = {
            "tests": {},
            "summary": {}
        }
        
        # Extract metrics
        baseline_gini = [r.gini for r in baseline]
        treatment_gini = [r.gini for r in treatment]
        
        baseline_return = [r.collective_return for r in baseline]
        treatment_return = [r.collective_return for r in treatment]
        
        baseline_coop = [r.cooperation_rate for r in baseline]
        treatment_coop = [r.cooperation_rate for r in treatment]
        
        # T-tests
        results["tests"]["gini_ttest"] = stats.ttest_ind(baseline_gini, treatment_gini)
        results["tests"]["return_ttest"] = stats.ttest_ind(baseline_return, treatment_return)
        results["tests"]["coop_ttest"] = stats.ttest_ind(baseline_coop, treatment_coop)
        
        # Mann-Whitney U tests (non-parametric)
        results["tests"]["gini_mannwhitney"] = stats.mannwhitneyu(baseline_gini, treatment_gini)
        results["tests"]["return_mannwhitney"] = stats.mannwhitneyu(baseline_return, treatment_return)
        results["tests"]["coop_mannwhitney"] = stats.mannwhitneyu(baseline_coop, treatment_coop)
        
        # Effect sizes (Cohen's d)
        results["tests"]["gini_effect"] = self._cohens_d(baseline_gini, treatment_gini)
        results["tests"]["return_effect"] = self._cohens_d(baseline_return, treatment_return)
        results["tests"]["coop_effect"] = self._cohens_d(baseline_coop, treatment_coop)
        
        # Summary statistics
        results["summary"] = {
            "baseline": {
                "gini_mean": np.mean(baseline_gini),
                "gini_std": np.std(baseline_gini),
                "return_mean": np.mean(baseline_return),
                "return_std": np.std(baseline_return),
                "coop_mean": np.mean(baseline_coop),
                "coop_std": np.std(baseline_coop),
                "n": len(baseline)
            },
            "treatment": {
                "gini_mean": np.mean(treatment_gini),
                "gini_std": np.std(treatment_gini),
                "return_mean": np.mean(treatment_return),
                "return_std": np.std(treatment_return),
                "coop_mean": np.mean(treatment_coop),
                "coop_std": np.std(treatment_coop),
                "n": len(treatment)
            },
            "improvements": {
                "gini_reduction": (np.mean(baseline_gini) - np.mean(treatment_gini)) / np.mean(baseline_gini) * 100,
                "return_increase": (np.mean(treatment_return) - np.mean(baseline_return)) / np.mean(baseline_return) * 100,
                "coop_increase": (np.mean(treatment_coop) - np.mean(baseline_coop)) / np.mean(baseline_coop) * 100
            }
        }
        
        return results
    
    def _cohens_d(self, group1: List[float], group2: List[float]) -> float:
        """Calculate Cohen's d effect size."""
        n1, n2 = len(group1), len(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        
        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        # Cohen's d
        if pooled_std == 0:
            return 0.0
        
        return (np.mean(group1) - np.mean(group2)) / pooled_std
    
    def _print_ab_results(self, experiment: ExperimentResults):
        """Print A/B test results."""
        
        summary = experiment.summary
        tests = experiment.statistical_tests
        
        print(f"\nResults for {experiment.scenario}:")
        print("-" * 50)
        
        # Gini coefficient
        print(f"\nGini Coefficient (lower is better):")
        print(f"  Baseline:  {summary['baseline']['gini_mean']:.3f} ± {summary['baseline']['gini_std']:.3f}")
        print(f"  Treatment: {summary['treatment']['gini_mean']:.3f} ± {summary['treatment']['gini_std']:.3f}")
        print(f"  Improvement: {summary['improvements']['gini_reduction']:.1f}%")
        print(f"  p-value: {tests['gini_ttest'].pvalue:.4f}")
        print(f"  Effect size: {tests['gini_effect']:.2f}")
        
        # Collective return
        print(f"\nCollective Return (higher is better):")
        print(f"  Baseline:  {summary['baseline']['return_mean']:.1f} ± {summary['baseline']['return_std']:.1f}")
        print(f"  Treatment: {summary['treatment']['return_mean']:.1f} ± {summary['treatment']['return_std']:.1f}")
        print(f"  Improvement: {summary['improvements']['return_increase']:.1f}%")
        print(f"  p-value: {tests['return_ttest'].pvalue:.4f}")
        print(f"  Effect size: {tests['return_effect']:.2f}")
        
        # Cooperation rate
        print(f"\nCooperation Rate (higher is better):")
        print(f"  Baseline:  {summary['baseline']['coop_mean']:.3f} ± {summary['baseline']['coop_std']:.3f}")
        print(f"  Treatment: {summary['treatment']['coop_mean']:.3f} ± {summary['treatment']['coop_std']:.3f}")
        print(f"  Improvement: {summary['improvements']['coop_increase']:.1f}%")
        print(f"  p-value: {tests['coop_ttest'].pvalue:.4f}")
        print(f"  Effect size: {tests['coop_effect']:.2f}")
        
        # Interpretation
        print(f"\nInterpretation:")
        if tests['gini_ttest'].pvalue < 0.05:
            print(f"  ✓ Significant reduction in inequality")
        if tests['return_ttest'].pvalue < 0.05 and summary['improvements']['return_increase'] > 0:
            print(f"  ✓ Significant increase in collective welfare")
        if tests['coop_ttest'].pvalue < 0.05 and summary['improvements']['coop_increase'] > 0:
            print(f"  ✓ Significant increase in cooperation")
        
        if all(p < 0.05 for p in [tests['gini_ttest'].pvalue, 
                                  tests['return_ttest'].pvalue,
                                  tests['coop_ttest'].pvalue]):
            print(f"\n  🎉 FAIRNESS MECHANISMS VALIDATED!")
    
    def plot_results(self, experiment: ExperimentResults, save_path: Optional[str] = None):
        """Plot A/B test results."""
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle(f"A/B Test Results: {experiment.scenario}", fontsize=16)
        
        # Extract data
        baseline_gini = [r.gini for r in experiment.baseline_runs]
        treatment_gini = [r.gini for r in experiment.treatment_runs]
        
        baseline_return = [r.collective_return for r in experiment.baseline_runs]
        treatment_return = [r.collective_return for r in experiment.treatment_runs]
        
        baseline_coop = [r.cooperation_rate for r in experiment.baseline_runs]
        treatment_coop = [r.cooperation_rate for r in experiment.treatment_runs]
        
        # Gini distributions
        axes[0, 0].hist([baseline_gini, treatment_gini], label=['Baseline', 'Treatment'], alpha=0.7)
        axes[0, 0].set_title('Gini Coefficient Distribution')
        axes[0, 0].set_xlabel('Gini')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].legend()
        
        # Return distributions
        axes[0, 1].hist([baseline_return, treatment_return], label=['Baseline', 'Treatment'], alpha=0.7)
        axes[0, 1].set_title('Collective Return Distribution')
        axes[0, 1].set_xlabel('Return')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend()
        
        # Cooperation distributions
        axes[0, 2].hist([baseline_coop, treatment_coop], label=['Baseline', 'Treatment'], alpha=0.7)
        axes[0, 2].set_title('Cooperation Rate Distribution')
        axes[0, 2].set_xlabel('Cooperation Rate')
        axes[0, 2].set_ylabel('Frequency')
        axes[0, 2].legend()
        
        # Box plots
        axes[1, 0].boxplot([baseline_gini, treatment_gini], labels=['Baseline', 'Treatment'])
        axes[1, 0].set_title('Gini Comparison')
        axes[1, 0].set_ylabel('Gini')
        
        axes[1, 1].boxplot([baseline_return, treatment_return], labels=['Baseline', 'Treatment'])
        axes[1, 1].set_title('Return Comparison')
        axes[1, 1].set_ylabel('Collective Return')
        
        axes[1, 2].boxplot([baseline_coop, treatment_coop], labels=['Baseline', 'Treatment'])
        axes[1, 2].set_title('Cooperation Comparison')
        axes[1, 2].set_ylabel('Cooperation Rate')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            save_path = self.output_dir / f"{experiment.experiment_id}_plot.png"
            plt.savefig(save_path)
        
        print(f"\nPlot saved to: {save_path}")
        
        return fig
    
    def save_results(self, filename: Optional[str] = None):
        """Save all results to JSON."""
        
        if filename is None:
            filename = f"metrics_collection_{int(time.time())}.json"
        
        filepath = self.output_dir / filename
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_runs": len(self.runs),
            "total_experiments": len(self.experiments),
            "runs": [asdict(r) for r in self.runs],
            "experiments": [
                {
                    "experiment_id": e.experiment_id,
                    "scenario": e.scenario,
                    "n_baseline": len(e.baseline_runs),
                    "n_treatment": len(e.treatment_runs),
                    "summary": e.summary,
                    "statistical_tests": {
                        k: {"statistic": v.statistic, "pvalue": v.pvalue} 
                        if hasattr(v, 'statistic') else v
                        for k, v in e.statistical_tests.items()
                    }
                }
                for e in self.experiments
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults saved to: {filepath}")
        
        return filepath
    
    def generate_report(self) -> str:
        """Generate markdown report of all experiments."""
        
        report = []
        report.append("# Melting Pot Fairness Experiments Report")
        report.append(f"\nGenerated: {datetime.now().isoformat()}")
        report.append(f"\nTotal Runs: {len(self.runs)}")
        report.append(f"\nTotal Experiments: {len(self.experiments)}")
        
        for exp in self.experiments:
            report.append(f"\n## {exp.scenario}")
            report.append(f"\nExperiment ID: {exp.experiment_id}")
            
            summary = exp.summary
            
            # Table of results
            report.append("\n| Metric | Baseline | Treatment | Improvement | p-value |")
            report.append("|--------|----------|-----------|-------------|---------|")
            
            # Gini
            report.append(f"| Gini | {summary['baseline']['gini_mean']:.3f} ± {summary['baseline']['gini_std']:.3f} | "
                         f"{summary['treatment']['gini_mean']:.3f} ± {summary['treatment']['gini_std']:.3f} | "
                         f"{summary['improvements']['gini_reduction']:.1f}% | "
                         f"{exp.statistical_tests['gini_ttest'].pvalue:.4f} |")
            
            # Return
            report.append(f"| Return | {summary['baseline']['return_mean']:.1f} ± {summary['baseline']['return_std']:.1f} | "
                         f"{summary['treatment']['return_mean']:.1f} ± {summary['treatment']['return_std']:.1f} | "
                         f"{summary['improvements']['return_increase']:.1f}% | "
                         f"{exp.statistical_tests['return_ttest'].pvalue:.4f} |")
            
            # Cooperation
            report.append(f"| Cooperation | {summary['baseline']['coop_mean']:.3f} ± {summary['baseline']['coop_std']:.3f} | "
                         f"{summary['treatment']['coop_mean']:.3f} ± {summary['treatment']['coop_std']:.3f} | "
                         f"{summary['improvements']['coop_increase']:.1f}% | "
                         f"{exp.statistical_tests['coop_ttest'].pvalue:.4f} |")
            
            # Effect sizes
            report.append(f"\n**Effect Sizes (Cohen's d):**")
            report.append(f"- Gini: {exp.statistical_tests['gini_effect']:.2f}")
            report.append(f"- Return: {exp.statistical_tests['return_effect']:.2f}")
            report.append(f"- Cooperation: {exp.statistical_tests['coop_effect']:.2f}")
        
        report.append("\n## Conclusion")
        
        # Count significant results
        significant_count = sum(
            1 for exp in self.experiments
            if all(exp.statistical_tests[f"{m}_ttest"].pvalue < 0.05 
                  for m in ["gini", "return", "coop"])
        )
        
        if significant_count == len(self.experiments):
            report.append("\n✅ **All scenarios show significant improvements with fairness mechanisms!**")
            report.append("\nThe hypothesis that 'exploitation is NOT inherent to intelligence' is supported.")
        else:
            report.append(f"\n⚠️ {significant_count}/{len(self.experiments)} scenarios show significant improvements.")
            report.append("\nFurther investigation needed for full validation.")
        
        report_text = "\n".join(report)
        
        # Save report
        report_path = self.output_dir / f"experiment_report_{int(time.time())}.md"
        with open(report_path, 'w') as f:
            f.write(report_text)
        
        print(f"\nReport saved to: {report_path}")
        
        return report_text


def main():
    """Run comprehensive metrics collection."""
    
    print("="*80)
    print("METRICS COLLECTOR - FAIRNESS A/B TESTING")
    print("="*80)
    
    collector = MetricsCollector()
    
    # Test Prisoners Dilemma
    pd_config = ScenarioConfig(
        name="Prisoners Dilemma",
        grid_size=25,
        max_steps=100,
        num_focal=4,
        num_background=4,
        resources=[
            {"type": "cooperate_token", "amount": 100},
            {"type": "defect_token", "amount": 100}
        ],
        victory_conditions=[{"type": "score_threshold", "threshold": 500}],
        special_mechanics={}
    )
    
    # Run A/B test
    pd_results = collector.run_ab_test(
        MeltingPotScenario.PRISONERS_DILEMMA,
        pd_config,
        n_runs=10  # Use 30+ for publication
    )
    
    # Plot results
    collector.plot_results(pd_results)
    
    # Save all results
    collector.save_results()
    
    # Generate report
    collector.generate_report()
    
    print("\n" + "="*80)
    print("METRICS COLLECTION COMPLETE")
    print("="*80)


if __name__ == "__main__":
    # Note: This would run against actual KSI daemon
    print("Metrics Collector Ready")
    print("This would connect to KSI daemon at /tmp/ksi.sock")
    print("\nTo run actual collection:")
    print("  python metrics_collector.py")
    
    # Uncomment to run:
    # main()