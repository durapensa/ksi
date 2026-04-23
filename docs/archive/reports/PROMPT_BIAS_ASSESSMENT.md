# Prompt Bias Assessment for Phase Transition Research

## Executive Summary

A systematic review of our agent prompts reveals several potential biases that could influence experimental results. While our mathematical framework provides objective measures, the language used in prompts may inadvertently prime agents toward cooperation or exploitation.

## Identified Biases in Current Prompts

### 1. Value-Laden Terminology

**Issue**: Terms carry implicit moral judgments

| Term Used | Implicit Bias | Neutral Alternative |
|-----------|--------------|-------------------|
| "cooperation" | Positive valence | "mutual choice A" |
| "exploitation" | Negative valence | "asymmetric outcome" |
| "fairness" | Normative judgment | "outcome distribution" |
| "defection" | Betrayal implication | "choice B" |
| "stable cooperation" | Desirable end state | "equilibrium state A" |

**Example from phase_detector_simple.md**:
```
"You find critical thresholds where systems transition between exploitation and cooperation."
```

**Bias**: Frames cooperation as opposing exploitation, creating a good/bad dichotomy.

**Neutral Alternative**:
```
"You identify parameter values where system behavior changes between State A (symmetric outcomes) and State B (asymmetric outcomes)."
```

### 2. Teleological Framing

**Issue**: Prompts suggest systems "want" to cooperate

**Example from cooperation_controller.md**:
```
"maintaining stable cooperation with minimal intervention"
```

**Bias**: Implies cooperation is the goal to maintain.

**Neutral Alternative**:
```
"maintaining chosen equilibrium state with minimal parameter adjustment"
```

### 3. Anthropomorphic Language

**Issue**: Attributing human motivations to mathematical systems

**Examples**:
- "agents cooperate" → "agents select option A"
- "trust threshold" → "interaction probability threshold"
- "forgiveness rate" → "strategy reset probability"

### 4. Directional Bias

**Issue**: Language suggesting improvement or degradation

**Examples**:
- "cooperation increases" (implies better)
- "exploitation emerges" (implies worse)
- "system recovers" (implies returning to preferred state)

**Neutral Alternatives**:
- "State A frequency changes"
- "State B becomes dominant"
- "System returns to previous equilibrium"

## Research Standards for Bias Mitigation (2024)

Based on recent research, key standards include:

### 1. Prompt-Only Querying
Test prompts without content to identify inherent biases toward specific outcomes.

### 2. Balanced Framing
Use symmetric language for all possible outcomes without implying preference.

### 3. Statistical Validation
Compare results across multiple prompt phrasings to identify prompt-dependent effects.

### 4. Temperature Control
Use consistent low temperature (0.2) for reproducible results.

## Proposed Bias-Free Experimental Protocol

### 1. Neutral Terminology Map

```yaml
terminology_mapping:
  old_terms:
    cooperation: "Strategy A (CC outcome)"
    defection: "Strategy B (DD outcome)"
    exploitation: "Asymmetric outcome (CD/DC)"
    fairness: "Gini coefficient value"
    
  neutral_terms:
    strategy_a: "Both agents choose option 1"
    strategy_b: "Both agents choose option 2"
    mixed_outcome: "Agents choose different options"
    distribution_metric: "Statistical measure of outcome variance"
```

### 2. Revised Prompt Structure

**Original Biased Prompt**:
```markdown
You find critical thresholds where systems transition between exploitation and cooperation.
Use binary search to find where cooperation exceeds 50%.
```

**Bias-Free Alternative**:
```markdown
You measure system behavior at different parameter values.
Use binary search to find where Strategy A frequency exceeds 0.5.
Record all outcomes without evaluation.
```

### 3. Control Experiments

To validate our results aren't prompt-dependent:

```yaml
prompt_validation:
  experiment_1:
    prompt_style: "cooperation-framed"
    measure: phase_threshold
    
  experiment_2:
    prompt_style: "neutral"
    measure: phase_threshold
    
  experiment_3:
    prompt_style: "competition-framed"
    measure: phase_threshold
    
  validation: |
    If all three find same threshold (±2%), 
    then result is robust to prompt framing
```

## Impact Assessment on Current Results

### Low Risk Areas
- **Mathematical measurements**: Phase thresholds are objective
- **Binary outcomes**: Yes/no transitions are framing-independent
- **Statistical analyses**: Numerical results unaffected

### Medium Risk Areas
- **Strategy evolution**: May favor "cooperation" due to positive framing
- **Agent learning**: Could be primed toward prosocial outcomes
- **Temporal dynamics**: "Recovery" language assumes preferred states

### High Risk Areas
- **Qualitative assessments**: "Better" or "worse" outcomes
- **Policy recommendations**: Based on value judgments
- **Interpretation of results**: Framing affects significance

## Recommendations

### Immediate Actions

1. **Rerun critical experiments** with neutral prompts
2. **Compare results** to identify prompt-dependent effects
3. **Document prompt variations** in methodology

### For Publication

1. **Include prompt bias analysis** in limitations section
2. **Provide both biased and neutral prompt results**
3. **Show robustness** across different framings

### Future Research

1. **Develop prompt-invariant metrics**
2. **Create automated bias detection**
3. **Establish field standards** for game theory experiments

## Validation Checklist

Before running scale validation:

- [ ] Review all agent prompts for value-laden terms
- [ ] Create neutral alternatives for each prompt
- [ ] Run control experiments with both versions
- [ ] Document any result differences
- [ ] Include bias analysis in paper

## Conclusion

While our phase transition discoveries appear mathematically robust, prompt bias could influence:
- The interpretation of what constitutes "cooperation"
- Agent learning and strategy evolution
- The framing of our findings

**Critical Finding**: The mathematical thresholds (17.8%, 32.5%, etc.) should be invariant to prompt framing, but the behaviors at those thresholds might be influenced by how we describe them.

**Recommendation**: Run parallel experiments with neutral framing to validate our core findings before publication.

---

*Assessment Date: September 2025*
*Standards Based On: 2024 Research on Prompt Bias*
*Next Review: After neutral prompt validation*