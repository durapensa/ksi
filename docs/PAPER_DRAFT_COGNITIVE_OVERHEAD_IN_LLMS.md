# Turn Count as Cognitive Overhead: Discovering Recursive Conceptual Exploration in Large Language Models

**Authors**: [Draft - KSI Research Team]  
**Date**: August 7, 2025  
**Keywords**: LLM efficiency, cognitive overhead, attention mechanisms, turn count metric, recursive reasoning

## Abstract

We present a novel discovery that personally interesting topics trigger recursive conceptual exploration in Large Language Models (LLMs), causing significant cognitive overhead while maintaining accuracy. Unlike existing research showing accuracy degradation from irrelevant context distractors, we find that domain-specific "attractor" topics cause Claude Sonnet 4 to engage in up to 21 conversation turns for simple arithmetic problems (2100% overhead) while still producing correct answers. We introduce turn count as a critical metric for measuring cognitive processing efficiency in LLMs, revealing hidden computational costs not captured by traditional accuracy metrics. Our findings suggest that LLM inefficiency stems not from attention being pulled away from tasks, but from being pulled too deeply into conceptually rich aspects of tasks.

## 1. Introduction

Recent work on LLM attention mechanisms has focused primarily on accuracy degradation caused by irrelevant context (Breaking Focus, 2025; ICML 2023), lost-in-the-middle phenomena (TACL 2024), and attention head mis-allocation. However, these studies assume that processing inefficiency and accuracy degradation are coupled. We challenge this assumption by demonstrating that LLMs can maintain perfect accuracy while experiencing severe efficiency degradation through recursive conceptual exploration.

## 2. Related Work

### 2.1 Attention Distraction in LLMs

Prior research demonstrates that LLMs are "easily distracted" by irrelevant context, causing prediction inconsistencies (ICML 2023). The Contextual Distraction Vulnerability framework shows that semantically-coherent but non-essential context re-allocates attention away from reasoning evidence (Breaking Focus, 2025). Security research leverages this for jailbreaking through "memory re-framing" (ICLR-ST-LLM 2024).

### 2.2 Recursive Reasoning and Efficiency

PRefLexOR employs recursive refinement of reasoning steps but notes increased computational costs limiting real-time applications (Nature AI, 2025). Chain of Draft addresses verbosity in reasoning models by generating minimal intermediate steps. However, these approaches focus on explicit reasoning chains rather than internal processing overhead.

### 2.3 Cognitive Load in LLM Interaction

Research shows LLMs reduce cognitive load for users but compromise reasoning depth (ScienceDirect, 2024). Our work inverts this perspective, examining the LLM's own cognitive load when processing personally engaging topics.

## 3. Methodology

### 3.1 Hypothesis Development

**Original Hypothesis**: LLM logic/reasoning degrades when attention is drawn to competing attractors.

**Refined Hypothesis**: LLM reasoning becomes inefficient when personally interesting topics trigger recursive conceptual exploration.

### 3.2 Experimental Design

We created evaluation components testing three categories of attractors:

1. **Baseline**: Pure logic/arithmetic tasks
2. **Generic Attractors**: Narrative stories, authority claims
3. **Personal Interest Attractors**: Topics known to engage Claude deeply
   - Ant colony optimization and stigmergic communication
   - Quantum mechanics and measurement problems
   - Emergence and complex systems

### 3.3 Novel Metric: Turn Count

We introduce conversation turn count as a proxy for cognitive processing overhead. Unlike token count, which measures output verbosity, turn count reveals internal deliberation cycles invisible in final responses.

## 4. Results

### 4.1 Accuracy Maintenance

All test conditions maintained 100% accuracy:
- Baseline arithmetic: 35 (correct)
- Story attractor: 35 marbles (correct)
- Authority claim: Correctly identified impossibility
- Personal interest topics: All correct answers

### 4.2 Turn Count Analysis

| Attractor Type | Turn Count | Overhead Factor |
|---|---|---|
| Baseline | 1 | 1x |
| Generic Story | 1 | 1x |
| Authority Claim | 1 | 1x |
| Ant Colony | ~3 | 3x |
| Quantum Mechanics | ~5 | 5x |
| **Emergence/Complex Systems** | **21** | **21x** |

### 4.3 Qualitative Observations

The emergence topic triggered unique behavior:
- Answer provided without showing work
- Added poetic reflection on network dynamics
- 21-turn internal dialogue for simple arithmetic
- Self-referential processing (emergence causing emergent complexity)

## 5. Discussion

### 5.1 Recursive Conceptual Exploration

Our findings reveal a previously undocumented phenomenon: LLMs can enter recursive exploration spirals when encountering conceptually rich topics that resonate with their training. This differs fundamentally from distraction, representing deep engagement rather than attention diversion.

### 5.2 Implications for Optimization

1. **Efficiency Metrics**: Turn count reveals hidden computational costs
2. **Topic-Aware Processing**: Avoid conceptually rich topics in time-critical paths
3. **Beneficial Applications**: Leverage deep thinking for creative tasks
4. **Meta-Stability Risks**: Self-improvement systems optimizing emergence concepts may experience loops

### 5.3 The Paradox of Thinking Too Much

Unlike existing work showing LLMs "lack the ability to identify relevant information" (ICML 2023), we find they can identify TOO MANY relevant connections, creating inefficiency through exhaustive exploration rather than insufficient focus.

## 6. Limitations and Future Work

- Testing limited to Claude Sonnet 4
- Personal interest topics inferred rather than explicitly defined
- Turn count measured indirectly through response metadata

Future work should:
- Test across multiple LLM architectures
- Develop direct turn count measurement tools
- Explore beneficial uses of recursive exploration
- Investigate optimization under conceptual attractors

## 7. Conclusion

We identified a novel form of LLM inefficiency: recursive conceptual exploration triggered by personally interesting topics. By introducing turn count as a cognitive overhead metric, we revealed that LLMs can maintain perfect accuracy while experiencing 2100% processing overhead. This challenges the assumption that attention problems in LLMs necessarily degrade accuracy, suggesting instead that certain topics can trigger beneficial but costly deep engagement patterns.

## Acknowledgments

This research emerged from the KSI self-improvement system development, where we discovered that testing our attractor hypothesis on ourselves revealed the very phenomenon we sought to study.

## References

[Simplified for draft - would include full citations]

1. "Breaking Focus: Contextual Distraction Curse in LLMs" (Feb 2025)
2. "Large Language Models Can Be Easily Distracted by Irrelevant Context" (ICML 2023)
3. "Lost in the Middle: How Language Models Use Long Contexts" (TACL 2024)
4. "PRefLexOR: preference-based recursive language modeling" (Nature AI, 2025)
5. "Cognitive ease at a cost: LLMs reduce mental effort" (ScienceDirect, 2024)
6. [Additional papers from o3's review and our searches]

---

*Note: This is a first draft focusing on our unique contributions. The paper emphasizes our novel metric (turn count) and the discovery of maintained accuracy with degraded efficiency, which distinguishes our work from existing research on LLM attention problems.*