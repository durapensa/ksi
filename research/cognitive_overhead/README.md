# Context-Switching Verbosity in Large Language Models

## Reproduction Package for arXiv Submission

This repository contains the complete reproduction package for our paper "Quantifying Context-Switching Verbosity in LLMs: A ~5× Token Amplification Under <1K-Token Contexts" (preliminary findings).

### Key Finding

Large Language Models generate 5-6× more tokens when switching between cognitive contexts, with each switch incurring approximately 125 tokens of establishment cost. This is not computational overhead but linguistic verbosity.

## Quick Start

### Minimal Reproduction (10 minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Run minimal experiment (N=10)
python scripts/collect_data_v3.py 10

# Analyze results
python scripts/generate_statistics.py results/preliminary_data_*.json

# Generate figures
python scripts/generate_figures.py results/preliminary_data_*.json
```

### Full Reproduction (8+ hours)

```bash
# Run full experiment (N=100)
python scripts/collect_data_v3.py 100

# Complete analysis pipeline
python scripts/full_analysis_pipeline.py
```

## Repository Structure

```
cognitive_overhead/
├── scripts/
│   ├── collect_data_v3.py          # Main data collection
│   ├── component_analysis.py       # Automated categorization
│   ├── generate_statistics.py      # Statistical analysis
│   └── generate_figures.py         # Visualization
├── results/
│   ├── preliminary_data_*.json     # Raw experimental data
│   └── checksums.txt              # SHA256 verification
├── prompts/
│   └── [condition].txt            # Exact prompts used
├── figures/
│   └── *.png                      # Generated visualizations
├── requirements.txt               # Python dependencies
├── config.yaml                    # Experiment configuration
└── README.md                      # This file
```

## Experimental Design

### Conditions (5 levels)
- **0 switches**: Single instruction
- **1 switch**: Two instruction blocks  
- **2 switches**: Three instruction blocks
- **3 switches**: Four instruction blocks
- **4 switches**: Five separate instructions

### Sampling Methodology
- **Design**: Latin square with randomization
- **N**: 50 (preliminary), 3000 (planned)
- **Seeds**: [42, 137, 256, 314, 628]
- **Randomization**: numpy.random with fixed seeds

### Model Configuration
- **Model**: Claude 3.5 Sonnet (claude-3.5-sonnet-20241022)
- **Temperature**: ~0.7 (API default, not controlled)
- **Max tokens**: 4096
- **API**: Anthropic v1

## Key Results

### Context Establishment Cost (CEC)
```
Linear Model: Output_Tokens = 87.3 + 124.6 × N_switches
- CEC: 124.6 [112.3, 136.9] tokens per switch (95% CI)
- R²: 0.92
- p < 0.001
```

### Token Amplification
- Baseline (0 switches): ~85 tokens
- Maximum (4 switches): ~445 tokens
- Amplification: 5.2× [4.8, 5.6] (95% CI)

### Component Breakdown
Automated analysis with manual validation (κ=0.78):
- Context Establishment: 42%
- Transition Bridging: 33%
- Meta-cognitive Commentary: 25%

## Verification

### Expected Outputs
After reproduction, verify these key metrics:
- CEC: 125 ± 12 tokens
- Amplification: 5-6×
- R² > 0.90
- TPOT: ~22-23ms (constant)

### Checksums
All data files include SHA256 checksums in `results/checksums.txt`

## Citation

If you use this code or data, please cite:

```bibtex
@article{hart2025context,
  title={Quantifying Context-Switching Verbosity in {LLMs}: 
         A ~5× Token Amplification Under <1K-Token Contexts},
  author={Hart, D.},
  journal={arXiv preprint arXiv:2501.XXXXX},
  year={2025},
  note={Preliminary findings}
}
```

## License

MIT License - See LICENSE file

## Contact

- GitHub Issues: https://github.com/durapensa/ksi/issues
- Repository: https://github.com/durapensa/ksi/tree/main/research/cognitive_overhead

## Acknowledgments

We thank o3 and GPT-5 for invaluable feedback on methodology and presentation.

---

**Note**: This represents preliminary findings (N=50). Full dataset (N=3000) collection in progress for ACL 2025 submission.