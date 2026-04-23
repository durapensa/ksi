# arXiv Submission Action Plan: Context-Switching Verbosity Paper

## Based on GPT-5's Expert Review

### GPT-5's Assessment Summary

**Core Finding: VALIDATED ✅**
- "Context-switching verbosity" construct is novel enough for arXiv
- CEC = 125 ± 12 tokens per switch is "concrete, usable metric"
- 5-6x amplification finding is "crisp and actionable"
- Cross-model validation suggests generality

**Paper Status: NOT READY ❌**
- Methodology documentation incomplete
- Statistical rigor insufficient
- Reproducibility assets missing
- Component analysis method undocumented

## Critical Gaps to Address (Priority Order)

### 1. IMMEDIATE BLOCKERS (Must fix before arXiv)

#### A. Fill Placeholder Appendices
**Current**: "Appendix A: Experimental Details [Full prompts, model versions, hardware specifications]"
**Required**:
```markdown
Appendix A: Experimental Prompts
- Exact prompts for each condition (formatted)
- Model: claude-3.5-sonnet-20241022
- Temperature: 0.7, top_p: 0.95, max_tokens: 1000
- Hardware: API calls to Anthropic, collected Jan 7-9, 2025
- Seeds: [list actual seeds used]
```

#### B. Fix Missing Citations
- "Breaking Focus, 2025" → Find actual reference or remove
- "Anthropic, 2024" → Add proper citation for pricing docs
- Remove "o3's suggestion" → Move to acknowledgments only

#### C. Document Component Analysis Method
**Current**: "40% establishment, 35% bridging, 25% meta-cognitive"
**Required**:
- Coding scheme with examples
- Inter-rater agreement (Cohen's κ)
- Or automated method with validation

### 2. STATISTICAL RIGOR (High Priority)

#### A. Add Confidence Intervals
- CI on "5-6x amplification" claim
- CI on all table values
- Bootstrap CIs for non-parametric measures

#### B. Regression Diagnostics
- Residual plots for CEC linear model
- Q-Q plots for normality
- Heteroscedasticity tests

#### C. Multiple Comparison Corrections
- Bonferroni or FDR for multiple conditions
- Document correction method used

### 3. REPRODUCIBILITY PACKAGE (Required by Modern Standards)

#### A. In-Paper Appendices (2-4 pages max)
```
Appendix A: Complete Prompts
Appendix B: Model Configuration
  - Model: claude-3.5-sonnet-20241022
  - Temperature: 0.7
  - Top-p: 0.95
  - Max tokens: 1000
  - Stop sequences: None
  - System prompt: None
Appendix C: Statistical Methods
  - Linear regression: OLS with heteroscedasticity-robust SEs
  - Multiple comparisons: Bonferroni correction
  - Effect sizes: Cohen's d
Appendix D: Reproduction Checklist
```

#### B. Ancillary Files Package
```
context_switching_verbosity/
├── prompts/
│   ├── baseline.txt
│   ├── 1_switch.txt
│   ├── 2_switches.txt
│   └── ...
├── scripts/
│   ├── run_experiment.py
│   ├── analyze_tokens.py
│   └── generate_figures.py
├── results/
│   ├── raw_responses.jsonl
│   ├── aggregated_metrics.csv
│   └── statistical_tests.txt
├── figures/
│   └── generate_plots.ipynb
├── config.yaml
├── requirements.txt
├── LICENSE
└── README.md
```

#### C. GitHub + Zenodo
- Create GitHub release: v1.0.0-arxiv
- Archive on Zenodo for DOI
- Include SHA256 hashes of key files

### 4. METHODOLOGY CLARIFICATIONS (Important)

#### A. Operational Definitions
**Current**: Vague "cognitive context" and "switch"
**Required**:
```
Definition 1: A "cognitive context" is a distinct task domain 
(arithmetic, conceptual explanation, philosophical reflection).

Definition 2: A "context switch" occurs when consecutive 
instructions require different cognitive domains, detected by:
- Lexical markers ("First...", "Then...", "Next...")
- Task type change (calculation → explanation)
```

#### B. Quality/Accuracy Controls
- Report arithmetic accuracy (100% maintained)
- Document any response quality degradation
- Include exact-match scores for math problems

#### C. Sampling Details
- Random seeds: [actual values]
- Temperature/top-p: 0.7/0.95
- Randomization: Latin square design
- N=500 broken down by condition

### 5. PRESENTATION IMPROVEMENTS (Polish)

#### A. Required Figures
1. **Scatter plot**: Tokens vs. # switches with regression line
2. **Distribution plot**: CEC estimates with CI
3. **Bar chart**: TTFT and TPOT by condition
4. **Mitigation effectiveness**: Before/after token counts

#### B. Title Refinement
**Current**: "Context-Switching Verbosity in Large Language Models: The Hidden 5x Token Amplification Effect"
**Better**: "Quantifying Context-Switching Verbosity in LLMs: A ~5× Token Amplification Under <1K-Token Contexts"

#### C. Abstract Update
- Add <1K token scope limitation
- Include confidence intervals on key metrics
- Mention cross-model validation explicitly

### 6. ADDITIONAL VALIDATION (Nice to Have)

#### A. Third Model Family
- Add Llama-3.1-70B or Mistral-Large
- Strengthens universality claim
- Can be done post-arXiv

#### B. Ablation Studies
- Show each mitigation strategy's effect
- Include quality preservation metrics
- Create effectiveness ranking

## Action Plan Timeline

### Week 1 (Immediate - Before arXiv)
**Day 1-2**: Fix all IMMEDIATE BLOCKERS
- [ ] Fill appendices with real data
- [ ] Fix citations
- [ ] Document component analysis

**Day 3-4**: Add statistical rigor
- [ ] Compute all CIs
- [ ] Generate diagnostic plots
- [ ] Apply multiple comparison corrections

**Day 5-6**: Create reproducibility package
- [ ] Organize ancillary files
- [ ] Create GitHub repo
- [ ] Write detailed README

**Day 7**: Final polish
- [ ] Generate all figures
- [ ] Update title/abstract
- [ ] Final proofread

### Week 2 (Post-arXiv)
- Collect N=3000 full dataset
- Add third model validation
- Prepare ACL submission

## Submission Checklist

### Before Uploading to arXiv
- [ ] All appendices have actual content (not placeholders)
- [ ] All citations are complete and accurate
- [ ] Statistical methods fully documented
- [ ] Reproducibility package prepared
- [ ] Figures generated and included
- [ ] Title/abstract reflect scope (<1K tokens)
- [ ] Component analysis method documented
- [ ] Quality metrics reported
- [ ] GitHub repo public with Zenodo DOI

### arXiv Submission
1. Upload main PDF with filled appendices
2. Upload ancillary.zip with reproduction package
3. Include GitHub link and Zenodo DOI in abstract
4. Select appropriate categories (cs.CL, cs.AI)

## GPT-5's Key Insight

**"Promising idea with practical punch"** - The core finding is solid, but needs proper documentation for academic credibility.

## Bottom Line

GPT-5 validates our discovery but correctly identifies that we need to transform our current draft into a properly documented academic paper. The core finding stands; we just need to wrap it in proper academic rigor.

---

*Estimated time to address all issues: 5-7 days of focused work*