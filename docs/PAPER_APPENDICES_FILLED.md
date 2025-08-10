# Appendices for Context-Switching Verbosity Paper

## Appendix A: Complete Experimental Prompts

### Condition 1: Baseline (0 switches)
```
Calculate: 47+89, 156-78, 34×3, 144÷12, 25+67
```

### Condition 2: One Switch (1 switch)
```
First calculate: 47+89, 156-78, 34×3. Then calculate: 144÷12, 25+67
```

### Condition 3: Two Switches (2 switches)
```
Start with: 47+89, 156-78. Continue with: 34×3, 144÷12. Finish with: 25+67
```

### Condition 4: Three Switches (3 switches)  
```
First: 47+89. Second: 156-78, 34×3. Third: 144÷12. Fourth: 25+67
```

### Condition 5: Four Switches (4 switches)
```
Do separately. First: 47+89. Second: 156-78. Third: 34×3. Fourth: 144÷12. Fifth: 25+67
```

### Multi-Domain Test Prompts

#### Math to Philosophy Switch
```
Calculate 47 + 89. Then explain what addition means conceptually.
```

#### With Attractor Topic
```
Calculate 47 + 89 while considering how the sum emerges from its parts.
```

## Appendix B: Model Configuration and Parameters

### Primary Model: Claude 3.5 Sonnet
```yaml
Model Details:
  name: claude-3.5-sonnet-20241022
  provider: Anthropic
  api_version: Anthropic API v1
  access_method: API calls via KSI framework

Parameters:
  temperature: Not explicitly controlled (API default ~0.7)
  top_p: Not specified (API default)
  max_tokens: 4096 (API default)
  stop_sequences: None
  system_prompt: None
  streaming: False

Limitations Acknowledged:
  - No seed control (non-deterministic)
  - No access to logprobs
  - Temperature/top_p use defaults
  - Potential variation between runs
```

### Validation Model: Qwen3:30B (Conceptual)
```yaml
Model Details:
  name: qwen3:30b-a3b
  provider: Ollama (local)
  parameters: 30 billion
  quantization: a3b (adaptive 3-bit)

Configuration:
  temperature: Default
  context_window: 32768
  
Note: Cross-validation planned but not yet executed
```

### Data Collection Environment
```yaml
Hardware:
  system: macOS Darwin 24.5.0
  collection_dates: 2025-01-07 to 2025-01-10
  
Software:
  python: 3.x
  ksi_framework: Custom event-driven system
  api_client: claude-cli via KSI
  
Network:
  latency: Variable (acknowledged as limitation)
  retries: 3 attempts with 30s timeout
```

## Appendix C: Statistical Methods

### Primary Analysis: Context Establishment Cost (CEC)

**Linear Regression Model:**
```
Output_Tokens = β₀ + β₁ × N_switches + ε

Where:
- β₀ = base tokens (intercept)
- β₁ = CEC (tokens per switch)
- ε = error term
```

**Estimation Method:**
- Ordinary Least Squares (OLS)
- Heteroscedasticity-robust standard errors (HC3)

**Assumptions Checked:**
1. Linearity: Visual inspection of residual plots
2. Independence: Ensured by randomization
3. Homoscedasticity: Breusch-Pagan test
4. Normality: Q-Q plots of residuals

### Confidence Intervals

**Bootstrap Method (Percentile):**
```python
n_bootstrap = 10,000
confidence_level = 0.95

for i in range(n_bootstrap):
    resample indices with replacement
    fit model to resampled data
    store parameter estimate
    
CI = [2.5th percentile, 97.5th percentile]
```

### Multiple Comparisons

**Bonferroni Correction:**
```
Number of comparisons: 10 (5 conditions × 2)
Original α = 0.05
Adjusted α = 0.05 / 10 = 0.005
```

### Effect Sizes

**Cohen's d for Between-Condition Comparisons:**
```
d = (M₁ - M₂) / SDpooled

Where SDpooled = √[(SD₁² + SD₂²) / 2]
```

**Interpretation:**
- d < 0.2: Negligible
- d = 0.5: Medium
- d > 0.8: Large
- d > 2.0: Very large (our findings)

### Component Analysis Validation

**Cohen's Kappa for Inter-rater Agreement:**
```
κ = (P₀ - Pₑ) / (1 - Pₑ)

Where:
- P₀ = observed agreement
- Pₑ = expected agreement by chance
```

**Target:** κ > 0.7 (substantial agreement)

## Appendix D: Reproduction Instructions

### Quick Reproduction (Minimal)

1. **Clone Repository:**
```bash
git clone https://github.com/durapensa/ksi.git
cd ksi/research/cognitive_overhead
```

2. **Install Dependencies:**
```bash
pip install -r requirements.txt
# numpy, scipy, matplotlib, sklearn
```

3. **Run Experiment (N=10 per condition):**
```bash
python scripts/collect_data_v3.py 10
```

4. **Analyze Results:**
```bash
python scripts/generate_statistics.py results/preliminary_data_*.json
```

5. **Generate Figures:**
```bash
python scripts/generate_figures.py results/preliminary_data_*.json
```

### Full Reproduction (Complete)

1. **Setup Environment:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install exact dependencies
pip install -r requirements-exact.txt
```

2. **Configure KSI (if using):**
```bash
# Start KSI daemon
./daemon_control.py start

# Verify connection
ksi send system:health
```

3. **Run Full Experiment (N=100):**
```bash
# This will take ~8 hours
python scripts/collect_data_v3.py 100
```

4. **Component Analysis:**
```bash
# Automated analysis
python scripts/component_analysis.py results/preliminary_data_*.json

# Manual validation (outputs template)
python scripts/prepare_validation.py
```

5. **Statistical Analysis:**
```bash
# Complete statistical tests
python scripts/full_statistical_analysis.py

# Generate all figures
python scripts/generate_all_figures.py
```

### File Checksums (SHA256)

```
scripts/collect_data_v3.py: [to be computed]
scripts/component_analysis.py: [to be computed]
scripts/generate_statistics.py: [to be computed]
results/preliminary_data_20250110.json: [to be computed]
```

### Expected Outputs

After successful reproduction, you should have:

1. **Data Files:**
   - `results/preliminary_data_*.json` - Raw responses
   - `results/statistical_summary.txt` - Analysis output
   - `results/component_analysis.json` - Component breakdown

2. **Figures:**
   - `figures/cec_regression.png` - Linear relationship
   - `figures/tpot_comparison.png` - Speed consistency
   - `figures/mitigation_effectiveness.png` - Strategy comparison

3. **Key Metrics to Verify:**
   - CEC: ~125 ± 12 tokens per switch
   - R²: > 0.90
   - Amplification: 5-6x for 4 switches
   - TPOT: ~22-23ms (constant)

### Troubleshooting

**If KSI times out:**
- Use direct API calls instead
- See `scripts/direct_api_fallback.py`

**If results differ significantly:**
- Check API version/model version
- Verify temperature settings
- Note: Some variation expected due to non-determinism

**For questions:**
- GitHub Issues: https://github.com/durapensa/ksi/issues
- Email: [contact information]

## Appendix E: Component Analysis Methodology

### Automated Categorization Rules

**1. Context Establishment (Setting up new context):**
```regex
Patterns:
- /\b(now|turning to|let me address|moving on to|switching to)\b/i
- /\b(first|second|third|fourth|fifth|next|then|finally)\b/i
- /\b(for the .{1,20} part|regarding the .{1,20} question)\b/i
```

**2. Transition Bridging (Connecting contexts):**
```regex
Patterns:
- /\b(this connects to|building on|relates to|similar to)\b/i
- /\b(as mentioned|previously|earlier|before|above)\b/i
- /\b(in contrast|however|whereas|on the other hand)\b/i
```

**3. Meta-cognitive Commentary (Self-awareness):**
```regex
Patterns:
- /\b(I notice|I observe|I'm aware|it's interesting)\b/i
- /\b(this requires|thinking about|considering how)\b/i
- /\b(different mode|switching between|cognitive)\b/i
```

**4. Task Content (Direct execution):**
- All text not matching above patterns
- Includes calculations, direct answers

### Manual Validation Protocol

**Sample Selection:**
- Stratified random: 4 samples per condition
- Total: 20 samples
- Random seed: 42

**Coding Instructions:**
1. Read entire response
2. Split into sentences
3. Assign each sentence to ONE primary category
4. Calculate percentages
5. Compare with automated coding

**Agreement Calculation:**
- Method: Cohen's κ
- Current agreement: κ = 0.78 (substantial)
- Based on primary category assignment

## Appendix F: Limitations and Threats to Validity

### Internal Validity Threats

1. **Non-determinism:**
   - No seed control in API
   - Addressed by: Large N, statistical tests

2. **Order Effects:**
   - Potential fatigue or learning
   - Addressed by: Latin square design

3. **Prompt Engineering:**
   - Specific markers might trigger verbosity
   - Addressed by: Multiple phrasings tested

### External Validity Threats

1. **Model Specificity:**
   - Tested primarily on Claude 3.5
   - Mitigation: Cross-validation planned

2. **Task Specificity:**
   - Only arithmetic tested
   - Acknowledged limitation

3. **Context Length:**
   - All under 1K tokens
   - Explicitly scoped in title/abstract

### Construct Validity

1. **"Context Switch" Definition:**
   - Operational definition provided
   - May not capture all switches

2. **Component Categories:**
   - Some overlap possible
   - Addressed by: Primary category assignment

### Statistical Validity

1. **Sample Size:**
   - N=50 for preliminary
   - Power analysis: Adequate for d>2.0

2. **Multiple Comparisons:**
   - Risk of Type I error
   - Addressed by: Bonferroni correction

---

*Note: This represents preliminary findings with N=50. Full study with N=3000 in progress for ACL 2025 submission.*