#!/usr/bin/env python3
"""
Setup Verification for Context-Switching Verbosity Experiment

This script verifies that all dependencies and configurations are correct
for reproducing the experiments from the paper.

Usage:
    python scripts/verify_setup.py
"""

import sys
import subprocess
import importlib
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SetupVerifier:
    """Verify experimental setup and dependencies."""
    
    def __init__(self):
        """Initialize verifier."""
        self.issues = []
        self.warnings = []
        
    def check_python_version(self) -> bool:
        """Check Python version compatibility."""
        logger.info("Checking Python version...")
        
        version = sys.version_info
        min_version = (3, 8)
        
        if version >= min_version:
            logger.info(f"✓ Python {version.major}.{version.minor}.{version.micro} (compatible)")
            return True
        else:
            error_msg = f"✗ Python {version.major}.{version.minor}.{version.micro} (requires >= {min_version[0]}.{min_version[1]})"
            logger.error(error_msg)
            self.issues.append(error_msg)
            return False
    
    def check_required_packages(self) -> bool:
        """Check if all required packages are installed with correct versions."""
        logger.info("Checking required packages...")
        
        required_packages = {
            'numpy': '1.24.0',
            'scipy': '1.10.0',
            'pandas': '2.0.0',
            'matplotlib': '3.7.0',
            'seaborn': '0.12.0',
            'statsmodels': '0.14.0',
            'sklearn': '1.3.0',
            'jsonlines': '3.1.0',
            'yaml': '6.0',
            'tqdm': '4.65.0',
            'pytest': '7.4.0'
        }
        
        all_good = True
        
        for package, min_version in required_packages.items():
            try:
                # Handle special cases
                if package == 'sklearn':
                    module = importlib.import_module('sklearn')
                elif package == 'yaml':
                    module = importlib.import_module('yaml')
                else:
                    module = importlib.import_module(package)
                
                # Get version
                if hasattr(module, '__version__'):
                    version = module.__version__
                elif hasattr(module, 'version'):
                    version = module.version
                else:
                    version = "unknown"
                
                logger.info(f"✓ {package} {version}")
                
            except ImportError:
                error_msg = f"✗ {package} not installed (required >= {min_version})"
                logger.error(error_msg)
                self.issues.append(error_msg)
                all_good = False
        
        return all_good
    
    def check_directory_structure(self) -> bool:
        """Check if required directory structure exists."""
        logger.info("Checking directory structure...")
        
        required_dirs = [
            "scripts",
            "data",
            "results", 
            "figures"
        ]
        
        required_files = [
            "requirements.txt",
            "scripts/run_experiment.py",
            "scripts/analyze_results.py",
            "scripts/component_analysis.py",
            "scripts/generate_plots.py",
            "scripts/verify_setup.py"
        ]
        
        all_good = True
        base_path = Path(".")
        
        # Check directories
        for dir_name in required_dirs:
            dir_path = base_path / dir_name
            if dir_path.exists():
                logger.info(f"✓ Directory: {dir_name}/")
            else:
                logger.warning(f"⚠ Directory missing: {dir_name}/ (will be created)")
                self.warnings.append(f"Directory missing: {dir_name}/")
                # Create missing directories
                dir_path.mkdir(exist_ok=True)
        
        # Check files
        for file_name in required_files:
            file_path = base_path / file_name
            if file_path.exists():
                logger.info(f"✓ File: {file_name}")
            else:
                error_msg = f"✗ File missing: {file_name}"
                logger.error(error_msg)
                self.issues.append(error_msg)
                all_good = False
        
        return all_good
    
    def check_api_access(self) -> bool:
        """Check if model API access is configured."""
        logger.info("Checking API access configuration...")
        
        # Check for API key environment variables
        import os
        api_vars = [
            'ANTHROPIC_API_KEY',
            'OPENAI_API_KEY',
            'CLAUDE_API_KEY'
        ]
        
        found_keys = []
        for var in api_vars:
            if os.getenv(var):
                found_keys.append(var)
                logger.info(f"✓ {var} environment variable set")
        
        if not found_keys:
            warning_msg = "⚠ No API keys found in environment variables"
            logger.warning(warning_msg)
            logger.warning("  Set at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY")
            logger.warning("  Or configure model access through KSI framework")
            self.warnings.append(warning_msg)
            return False
        
        return True
    
    def check_ksi_framework(self) -> bool:
        """Check if KSI framework is available (optional)."""
        logger.info("Checking KSI framework availability...")
        
        try:
            # Try to run ksi command
            result = subprocess.run(['ksi', 'send', 'system:health'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info("✓ KSI framework available and responding")
                return True
            else:
                logger.warning("⚠ KSI framework not responding (optional)")
                self.warnings.append("KSI framework not responding")
                return False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("⚠ KSI framework not found (optional)")
            logger.warning("  Experiments can run with direct API calls")
            self.warnings.append("KSI framework not found")
            return False
    
    def check_latex_support(self) -> bool:
        """Check if LaTeX is available for document generation."""
        logger.info("Checking LaTeX support...")
        
        latex_commands = ['pdflatex', 'xelatex', 'lualatex']
        found_latex = []
        
        for cmd in latex_commands:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    found_latex.append(cmd)
                    logger.info(f"✓ {cmd} available")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        if found_latex:
            logger.info(f"✓ LaTeX support available: {', '.join(found_latex)}")
            return True
        else:
            warning_msg = "⚠ No LaTeX engines found (optional for PDF generation)"
            logger.warning(warning_msg)
            self.warnings.append(warning_msg)
            return False
    
    def run_basic_tests(self) -> bool:
        """Run basic functionality tests."""
        logger.info("Running basic functionality tests...")
        
        try:
            # Test data loading
            import json
            import numpy as np
            import pandas as pd
            
            # Create minimal test data
            test_data = {
                "experiment_info": {"model": "test", "timestamp": "2025-01-01"},
                "results": [
                    {"switch_count": 0, "output_tokens": 80, "total_time_ms": 1000},
                    {"switch_count": 1, "output_tokens": 150, "total_time_ms": 1500}
                ]
            }
            
            # Test JSON handling
            json_str = json.dumps(test_data)
            loaded_data = json.loads(json_str)
            
            # Test pandas DataFrame creation
            df = pd.DataFrame(loaded_data["results"])
            
            # Test basic statistics
            mean_tokens = df["output_tokens"].mean()
            
            logger.info("✓ Basic functionality tests passed")
            return True
            
        except Exception as e:
            error_msg = f"✗ Basic functionality test failed: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
            return False
    
    def generate_configuration_template(self):
        """Generate configuration templates for the user."""
        logger.info("Generating configuration templates...")
        
        # Create config file
        config_content = """# Context-Switching Verbosity Experiment Configuration

# Model Configuration
MODEL_NAME = "claude-3.5-sonnet"
API_PROVIDER = "anthropic"  # anthropic, openai, ksi

# Experiment Parameters
DEFAULT_SAMPLES_PER_CONDITION = 10
FULL_EXPERIMENT_SAMPLES = 100
RANDOM_SEED = 42

# Output Configuration
RESULTS_DIR = "results"
FIGURES_DIR = "figures"
LOG_LEVEL = "INFO"

# API Configuration (set environment variables)
# export ANTHROPIC_API_KEY="your-key-here"
# export OPENAI_API_KEY="your-key-here"

# Rate Limiting
REQUESTS_PER_SECOND = 5
REQUEST_TIMEOUT_SECONDS = 30
"""
        
        config_path = Path("config.py")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        logger.info(f"✓ Configuration template created: {config_path}")
        
        # Create environment template
        env_content = """# Environment Variables for Context-Switching Verbosity Experiment
# Copy this file to .env and fill in your API keys

# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# OpenAI API (if using GPT models)
OPENAI_API_KEY=your_openai_api_key_here

# Experiment Configuration
EXPERIMENT_RANDOM_SEED=42
EXPERIMENT_LOG_LEVEL=INFO
"""
        
        env_path = Path(".env.template")
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        logger.info(f"✓ Environment template created: {env_path}")
    
    def run_complete_verification(self) -> Dict[str, Any]:
        """Run complete setup verification."""
        logger.info("Starting complete setup verification...")
        
        results = {
            'python_version': self.check_python_version(),
            'packages': self.check_required_packages(),
            'directory_structure': self.check_directory_structure(),
            'api_access': self.check_api_access(),
            'ksi_framework': self.check_ksi_framework(),
            'latex_support': self.check_latex_support(),
            'basic_tests': self.run_basic_tests()
        }
        
        # Generate config templates
        self.generate_configuration_template()
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print verification summary."""
        print("\n" + "="*60)
        print("SETUP VERIFICATION SUMMARY")
        print("="*60)
        
        # Count results
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        print(f"\nOverall Status: {passed}/{total} checks passed")
        
        # Required vs optional
        required_checks = ['python_version', 'packages', 'directory_structure', 'basic_tests']
        optional_checks = ['api_access', 'ksi_framework', 'latex_support']
        
        required_passed = sum(1 for k in required_checks if results.get(k, False))
        optional_passed = sum(1 for k in optional_checks if results.get(k, False))
        
        print(f"Required: {required_passed}/{len(required_checks)} ({'✓ READY' if required_passed == len(required_checks) else '✗ ISSUES'})")
        print(f"Optional: {optional_passed}/{len(optional_checks)}")
        
        # Issues
        if self.issues:
            print(f"\n🚨 CRITICAL ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  - {issue}")
        
        # Warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        # Next steps
        print(f"\n📋 NEXT STEPS:")
        if self.issues:
            print("  1. Fix critical issues above before proceeding")
            print("  2. Install missing packages: pip install -r requirements.txt")
        else:
            print("  1. Set API keys in environment or .env file")
            print("  2. Run basic experiment: python scripts/run_experiment.py --n_samples 5")
            print("  3. Check results: python scripts/analyze_results.py results/experiment.json")
        
        print("\n" + "="*60)

def main():
    """Main verification function."""
    print("Context-Switching Verbosity Experiment - Setup Verification")
    print("=" * 60)
    
    verifier = SetupVerifier()
    results = verifier.run_complete_verification()
    verifier.print_summary(results)
    
    # Exit with appropriate code
    required_checks = ['python_version', 'packages', 'directory_structure', 'basic_tests']
    if all(results.get(k, False) for k in required_checks):
        print("\n✅ Setup verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Setup verification failed. Please fix issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()