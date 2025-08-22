#!/usr/bin/env python3
"""
Statistical Analysis for Context-Switching Verbosity Experiment

This script reproduces the statistical analysis from:
"Quantifying Context-Switching Verbosity in Large Language Models: 
A ~5× Token Amplification Under <1K-Token Contexts"

Usage:
    python scripts/analyze_results.py results/experiment.json
    python scripts/analyze_results.py results/experiment.json --output results/analysis.txt
"""

import argparse
import json
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, shapiro
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson
from sklearn.metrics import r2_score
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContextSwitchingAnalysis:
    """Statistical analysis for context-switching verbosity experiment."""
    
    def __init__(self, data_file: str):
        """Initialize with experimental data."""
        self.data_file = data_file
        self.data = self.load_data()
        self.df = self.prepare_dataframe()
        
    def load_data(self) -> Dict[str, Any]:
        """Load experimental data from JSON file."""
        logger.info(f"Loading data from {self.data_file}")
        
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data['results'])} samples")
        logger.info(f"Model: {data['experiment_info']['model']}")
        
        return data
    
    def prepare_dataframe(self) -> pd.DataFrame:
        """Convert results to pandas DataFrame for analysis."""
        df = pd.DataFrame(self.data['results'])
        
        # Add derived variables
        df['amplification_factor'] = df['output_tokens'] / df['output_tokens'][df['switch_count'] == 0].mean()
        df['tpot_ms'] = df['total_time_ms'] / df['output_tokens']  # Time per output token
        
        logger.info(f"Prepared DataFrame with {len(df)} observations")
        logger.info(f"Conditions: {sorted(df['switch_count'].unique())}")
        
        return df
    
    def linear_regression_analysis(self) -> Dict[str, Any]:
        """
        Perform linear regression: Output_Tokens = β₀ + β₁ × N_switches + ε
        
        This is the core analysis for Context Establishment Cost (CEC).
        """
        logger.info("Performing linear regression analysis")
        
        # Prepare data for regression
        X = self.df['switch_count']
        y = self.df['output_tokens']
        X_with_const = sm.add_constant(X)
        
        # Fit OLS model with robust standard errors
        model = sm.OLS(y, X_with_const).fit(cov_type='HC3')
        
        # Extract key statistics
        intercept = model.params[0]  # β₀
        slope = model.params[1]      # β₁ (Context Establishment Cost)
        r_squared = model.rsquared
        p_value = model.pvalues[1]
        
        # Confidence intervals
        conf_int = model.conf_int(alpha=0.05)  # 95% CI
        slope_ci = (conf_int.iloc[1, 0], conf_int.iloc[1, 1])
        
        # Diagnostic tests
        residuals = model.resid
        
        # Breusch-Pagan test for heteroscedasticity
        bp_stat, bp_pvalue, _, _ = het_breuschpagan(residuals, X_with_const)
        
        # Durbin-Watson test for autocorrelation
        dw_stat = durbin_watson(residuals)
        
        # Shapiro-Wilk test for normality of residuals
        sw_stat, sw_pvalue = shapiro(residuals)
        
        results = {
            "intercept": intercept,
            "slope_cec": slope,
            "slope_ci_lower": slope_ci[0],
            "slope_ci_upper": slope_ci[1],
            "r_squared": r_squared,
            "p_value": p_value,
            "n_observations": len(self.df),
            "diagnostics": {
                "breusch_pagan_stat": bp_stat,
                "breusch_pagan_pvalue": bp_pvalue,
                "durbin_watson": dw_stat,
                "shapiro_wilk_stat": sw_stat,
                "shapiro_wilk_pvalue": sw_pvalue
            },
            "equation": f"Output_Tokens = {intercept:.1f} + {slope:.1f} × N_switches"
        }
        
        logger.info(f"CEC (Context Establishment Cost): {slope:.1f} ± {(slope_ci[1] - slope_ci[0])/2:.1f} tokens per switch")
        logger.info(f"R² = {r_squared:.3f}, p < {p_value:.3f}")
        
        return results
    
    def descriptive_statistics(self) -> Dict[str, Any]:
        """Calculate descriptive statistics by condition."""
        logger.info("Calculating descriptive statistics")
        
        desc_stats = {}
        
        for condition in sorted(self.df['switch_count'].unique()):
            condition_data = self.df[self.df['switch_count'] == condition]
            
            # Token statistics
            output_tokens = condition_data['output_tokens']
            input_tokens = condition_data['input_tokens']
            tpot = condition_data['tpot_ms']
            ttft = condition_data['ttft_ms']
            
            # Calculate amplification factor relative to baseline
            baseline_mean = self.df[self.df['switch_count'] == 0]['output_tokens'].mean()
            amplification = output_tokens.mean() / baseline_mean if baseline_mean > 0 else 1.0
            
            stats_dict = {
                "n_samples": len(condition_data),
                "output_tokens": {
                    "mean": output_tokens.mean(),
                    "std": output_tokens.std(),
                    "median": output_tokens.median(),
                    "min": output_tokens.min(),
                    "max": output_tokens.max()
                },
                "input_tokens": {
                    "mean": input_tokens.mean(),
                    "std": input_tokens.std()
                },
                "timing": {
                    "tpot_ms_mean": tpot.mean(),
                    "tpot_ms_std": tpot.std(),
                    "ttft_ms_mean": ttft.mean(),
                    "ttft_ms_std": ttft.std()
                },
                "amplification_factor": amplification
            }
            
            desc_stats[f"condition_{condition}"] = stats_dict
        
        return desc_stats
    
    def effect_size_analysis(self) -> Dict[str, Any]:
        """Calculate Cohen's d effect sizes between conditions."""
        logger.info("Calculating effect sizes (Cohen's d)")
        
        baseline_condition = self.df[self.df['switch_count'] == 0]['output_tokens']
        effect_sizes = {}
        
        for condition in sorted(self.df['switch_count'].unique()):
            if condition == 0:
                continue
            
            condition_data = self.df[self.df['switch_count'] == condition]['output_tokens']
            
            # Calculate Cohen's d
            pooled_std = np.sqrt((baseline_condition.var() + condition_data.var()) / 2)
            cohens_d = (condition_data.mean() - baseline_condition.mean()) / pooled_std
            
            effect_sizes[f"condition_{condition}_vs_baseline"] = {
                "cohens_d": cohens_d,
                "interpretation": self.interpret_effect_size(cohens_d)
            }
        
        return effect_sizes
    
    def interpret_effect_size(self, d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(d)
        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        elif abs_d < 2.0:
            return "large"
        else:
            return "very large"
    
    def multiple_comparisons_correction(self) -> Dict[str, Any]:
        """Apply Bonferroni correction for multiple comparisons."""
        logger.info("Applying Bonferroni correction")
        
        baseline_data = self.df[self.df['switch_count'] == 0]['output_tokens']
        n_comparisons = len(self.df['switch_count'].unique()) - 1  # Exclude baseline
        alpha_corrected = 0.05 / n_comparisons if n_comparisons > 0 else 0.05
        
        comparisons = {}
        
        for condition in sorted(self.df['switch_count'].unique()):
            if condition == 0:
                continue
            
            condition_data = self.df[self.df['switch_count'] == condition]['output_tokens']
            
            # Independent t-test
            t_stat, p_value = stats.ttest_ind(condition_data, baseline_data)
            significant_corrected = p_value < alpha_corrected
            
            comparisons[f"condition_{condition}_vs_baseline"] = {
                "t_statistic": t_stat,
                "p_value": p_value,
                "alpha_corrected": alpha_corrected,
                "significant_corrected": significant_corrected
            }
        
        return {
            "n_comparisons": n_comparisons,
            "alpha_corrected": alpha_corrected,
            "comparisons": comparisons
        }
    
    def bootstrap_confidence_intervals(self, n_bootstrap: int = 10000) -> Dict[str, Any]:
        """Calculate bootstrap confidence intervals for CEC estimate."""
        logger.info(f"Calculating bootstrap CI with {n_bootstrap} iterations")
        
        X = self.df['switch_count'].values
        y = self.df['output_tokens'].values
        n = len(X)
        
        bootstrap_slopes = []
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            indices = np.random.choice(n, n, replace=True)
            X_boot = X[indices]
            y_boot = y[indices]
            
            # Fit linear regression
            slope, intercept, _, _, _ = stats.linregress(X_boot, y_boot)
            bootstrap_slopes.append(slope)
        
        # Calculate percentile confidence intervals
        ci_lower = np.percentile(bootstrap_slopes, 2.5)
        ci_upper = np.percentile(bootstrap_slopes, 97.5)
        
        return {
            "bootstrap_slopes": bootstrap_slopes,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n_bootstrap": n_bootstrap
        }
    
    def run_complete_analysis(self) -> Dict[str, Any]:
        """Run the complete statistical analysis pipeline."""
        logger.info("Running complete statistical analysis")
        
        analysis_results = {
            "experiment_info": self.data['experiment_info'],
            "descriptive_statistics": self.descriptive_statistics(),
            "linear_regression": self.linear_regression_analysis(),
            "effect_sizes": self.effect_size_analysis(),
            "multiple_comparisons": self.multiple_comparisons_correction(),
            "bootstrap_ci": self.bootstrap_confidence_intervals()
        }
        
        return analysis_results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print a summary of key findings."""
        print("\n" + "="*60)
        print("CONTEXT-SWITCHING VERBOSITY ANALYSIS SUMMARY")
        print("="*60)
        
        # Key findings
        lr = results['linear_regression']
        print(f"\n📊 LINEAR REGRESSION RESULTS:")
        print(f"   Context Establishment Cost (CEC): {lr['slope_cec']:.1f} tokens/switch")
        print(f"   95% Confidence Interval: [{lr['slope_ci_lower']:.1f}, {lr['slope_ci_upper']:.1f}]")
        print(f"   R² = {lr['r_squared']:.3f}")
        print(f"   p-value = {lr['p_value']:.3e}")
        print(f"   Equation: {lr['equation']}")
        
        # Amplification factors
        print(f"\n🔍 AMPLIFICATION BY CONDITION:")
        desc = results['descriptive_statistics']
        for condition, stats in desc.items():
            condition_num = condition.split('_')[1]
            amp = stats['amplification_factor']
            print(f"   {condition_num} switches: {amp:.1f}× amplification")
        
        # Timing consistency
        print(f"\n⏱️  TIMING ANALYSIS:")
        for condition, stats in desc.items():
            condition_num = condition.split('_')[1]
            tpot = stats['timing']['tpot_ms_mean']
            print(f"   {condition_num} switches: {tpot:.1f} ms/token (TPOT)")
        
        # Effect sizes
        print(f"\n📈 EFFECT SIZES (Cohen's d):")
        effects = results['effect_sizes']
        for comparison, effect in effects.items():
            condition = comparison.split('_')[1]
            d = effect['cohens_d']
            interp = effect['interpretation']
            print(f"   {condition} vs baseline: d = {d:.2f} ({interp})")
        
        # Model validation
        diag = lr['diagnostics']
        print(f"\n🔬 MODEL DIAGNOSTICS:")
        print(f"   Heteroscedasticity (Breusch-Pagan): p = {diag['breusch_pagan_pvalue']:.3f}")
        print(f"   Autocorrelation (Durbin-Watson): {diag['durbin_watson']:.3f}")
        print(f"   Normality (Shapiro-Wilk): p = {diag['shapiro_wilk_pvalue']:.3f}")
        
        print("\n" + "="*60)
    
    def save_results(self, results: Dict[str, Any], output_path: str):
        """Save analysis results to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Analysis results saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Analyze context-switching verbosity experiment results")
    parser.add_argument("data_file", help="JSON file with experimental results")
    parser.add_argument("--output", type=str, default="results/analysis.json",
                       help="Output file for analysis results (default: results/analysis.json)")
    parser.add_argument("--bootstrap", type=int, default=10000,
                       help="Number of bootstrap iterations (default: 10000)")
    
    args = parser.parse_args()
    
    # Run analysis
    analyzer = ContextSwitchingAnalysis(args.data_file)
    results = analyzer.run_complete_analysis()
    
    # Print summary
    analyzer.print_summary(results)
    
    # Save results
    analyzer.save_results(results, args.output)
    
    logger.info(f"Analysis complete. Results saved to {args.output}")

if __name__ == "__main__":
    main()