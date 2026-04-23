

| Aspect being explained | Paper & venue | How the paper phrases the mechanism |
| ----- | ----- | ----- |
| **General QA / reasoning failure** | **“Breaking Focus: Contextual Distraction Curse in LLMs”** (Feb 2025\) — introduces *Contextual Distraction Vulnerability* and states that “semantically-coherent but non-essential context *re-allocates* attention away from the evidence needed for reasoning, leading to wrong answers”  |  |
| **“Large Language Models Can Be Easily Distracted by Irrelevant Context”** (ICML 2023\) — concludes that models are “easily distracted” and “lack the ability to identify relevant information,” causing “inconsistent predictions” when a single irrelevant sentence is inserted  |  |  |
| **Long-context degradation (“lost-in-the-middle”)** | **“Lost in the Middle: How Language Models Use Long Contexts”** (TACL 2024\) — attributes the U-shaped accuracy curve to *primacy/recency attention biases*; when relevant info leaves the focus region, reasoning fails  |  |
| **Mechanistic analyses of attention heads** | **“Focus Directions Make Your LMs Pay More Attention to Relevant Contexts”** (Mar 2025\) — identifies “contextual heads” that *mis-allocate attention* to irrelevant chunks; steering those heads back to the target span restores accuracy  |  |
| **Memory‐vs-reasoning errors** | **“Disentangling Memory and Reasoning Ability in LLMs”** (ACL 2025\) — argues that “knowledge forgetting … where relevant information is *lost across reasoning steps* … disrupts the logical flow,” and introduces ⟨memory⟩/⟨reason⟩ tokens to prevent newer tokens from crowding out earlier facts  |  |
| **Security / jailbreaks** | **“Distract Large Language Models for Automatic Jailbreak Attack”** (ICLR-ST-LLM Wkshp 2024\) — shows that injecting an innocuous “cover story” shifts attention away from the system prompt, allowing hidden malicious instructions to pass the filter (paper uses the term “memory re-framing”)  |  |

