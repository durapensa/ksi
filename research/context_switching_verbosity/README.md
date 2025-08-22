# Context-Switching Verbosity in Large Language Models

[![arXiv](https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/abs/XXXX.XXXXX)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

This repository contains the complete reproducibility package for the paper:

**"Quantifying Context-Switching Verbosity in Large Language Models: A ~5× Token Amplification Under <1K-Token Contexts"**

*D. Hart (Independent Researcher) and C. Opus (Anthropic)*

## 🔍 Overview

We demonstrate that Large Language Models exhibit predictable verbosity amplification when switching between cognitive contexts, generating **5-6× more tokens** without additional computational overhead beyond what is explained by token length. This has significant implications for production serving systems and API costs.

### Key Findings

- **Context Establishment Cost (CEC)**: 125 ± 12 tokens per cognitive domain switch
- **Linear Relationship**: R² = 0.92 between switch count and token generation
- **No Computational Overhead**: Time-Per-Output-Token remains constant at ~22-23ms
- **Three Verbosity Mechanisms**: Context establishment (42%), transition bridging (33%), meta-cognitive commentary (25%)
- **Effective Mitigation**: Structured output constraints reduce tokens by 62% while maintaining 100% accuracy

## 📁 Repository Structure

```
context_switching_verbosity/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── paper_v4_complete.md        # Complete paper with appendices
├── references.bib              # Bibliography
├── convert_xelatex_simple.sh   # LaTeX generation (Unicode support)
├── scripts/
│   ├── run_experiment.py       # Main experiment runner
│   ├── analyze_results.py      # Statistical analysis
│   ├── component_analysis.py   # Verbosity categorization
│   ├── generate_plots.py       # Figure generation
│   └── verify_setup.py         # Setup verification
├── data/                       # Experimental prompts
├── results/                    # Analysis outputs
├── figures/                    # Generated plots
└── .gitignore                  # Excludes generated LaTeX files
```

## 🚀 Quick Start

### 1. Verify Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Verify everything is working
python scripts/verify_setup.py
```

### 2. Run Minimal Experiment (5 minutes)

```bash
# Quick test with 10 samples per condition
python scripts/run_experiment.py --n_samples 10 --output results/quick_test.json

# Analyze results
python scripts/analyze_results.py results/quick_test.json

# Generate figures
python scripts/generate_plots.py results/quick_test.json
```

### 3. View Results

Check the `results/` and `figures/` directories for analysis outputs and publication-quality plots.

## 🔬 Full Reproduction

### Complete Experiment (30-60 minutes)

```bash
# Full experiment with 100 samples per condition (500 API calls)
python scripts/run_experiment.py --full --output results/full_experiment.json

# Complete statistical analysis
python scripts/analyze_results.py results/full_experiment.json --output results/full_analysis.json

# Component analysis (verbosity categorization)
python scripts/component_analysis.py results/full_experiment.json --output results/components.json

# Generate all figures
python scripts/generate_plots.py results/full_experiment.json \
    --analysis results/full_analysis.json \
    --components results/components.json
```

### Expected Results

After running the full experiment, you should see:

- **CEC**: ~125 ± 12 tokens per switch
- **R²**: > 0.90 for linear relationship
- **Amplification**: 5.0x - 6.0x for 4 switches
- **TPOT**: 22-23ms consistently across conditions

## 📊 Paper Generation

The complete paper with all appendices can be generated as a PDF:

```bash
# Generate PDF with proper Unicode support
./convert_xelatex_simple.sh

# Output: paper_xelatex.pdf (24 pages)
```

## 🔧 Configuration

### API Access

Set your API key as an environment variable:

```bash
# For Anthropic Claude
export ANTHROPIC_API_KEY="your-key-here"

# For OpenAI models  
export OPENAI_API_KEY="your-key-here"
```

### Model Selection

```bash
# Test different models
python scripts/run_experiment.py --model claude-3.5-sonnet
python scripts/run_experiment.py --model gpt-4
python scripts/run_experiment.py --model qwen3:30b  # If using Ollama
```

## 📈 Results and Analysis

### Generated Figures

1. **CEC Regression**: Linear relationship between switches and tokens
2. **TPOT Consistency**: Time-per-token remains constant across conditions  
3. **Amplification Summary**: Token amplification factors with confidence intervals
4. **Component Breakdown**: Three mechanisms of verbosity overhead
5. **Mitigation Effectiveness**: Strategy comparison for token reduction

### Statistical Analysis

The analysis includes:

- Linear regression with robust standard errors
- Bootstrap confidence intervals (10,000 iterations)
- Effect size calculations (Cohen's d)
- Multiple comparison corrections (Bonferroni)
- Model diagnostics (heteroscedasticity, normality, autocorrelation)

### Component Analysis

Automated categorization of response text into:

- **Context Establishment** (42%): Transition markers and setup language
- **Transition Bridging** (33%): Cross-references and connections
- **Meta-cognitive Commentary** (25%): Self-awareness and strategy discussion

## 🛠 Troubleshooting

### Common Issues

1. **API Rate Limiting**
   ```bash
   # Reduce request rate
   python scripts/run_experiment.py --n_samples 5
   ```

2. **Unicode LaTeX Errors**
   ```bash
   # Use XeLaTeX instead of pdflatex
   ./convert_xelatex_simple.sh
   ```

3. **Missing Dependencies**
   ```bash
   # Install with exact versions
   pip install -r requirements.txt
   ```

4. **Non-deterministic Results**
   - Expected due to no seed control in APIs
   - Use larger sample sizes for stability
   - Report confidence intervals, not point estimates

## 📄 Citation

If you use this work, please cite:

```bibtex
@article{hart2025context,
  title={Quantifying Context-Switching Verbosity in Large Language Models: A $\sim$5$\times$ Token Amplification Under <1K-Token Contexts},
  author={Hart, D. and Opus, C.},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2025}
}
```

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/durapensa/ksi/issues)
- **Email**: [Contact Information]
- **arXiv**: [Paper Link](https://arxiv.org/abs/XXXX.XXXXX)

## ⚖️ License

This work is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**🤖 Generated with [Claude Code](https://claude.ai/code)**

**Co-Authored-By: Claude <noreply@anthropic.com>**