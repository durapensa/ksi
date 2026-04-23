# **Is the “computational overhead” discussion necessary / supported?**

**Short answer:** keep it, but reframe. What you’re observing looks like *token-length* (verbosity) effects, not extra algorithmic compute from “harder cognition.” That distinction is real and has prior art you can cite.

* **Why keep it:** Reviewers will otherwise conflate longer answers with heavier compute. Modern serving literature cleanly separates **prefill** (time-to-first-token) from **decode** (time per output token). Latency is largely a function of input length and *how many tokens you generate*, not the semantic “difficulty” of the task. 

* **How to support it:** Cite inference/serving work showing that, with KV-cache, per-token complexity during decode scales *roughly linearly with sequence length* (so longer contexts or more generated tokens slow you down; switching “domains” does not add a new compute mode). Also cite system optimizations (FlashAttention / PagedAttention) that speed attention but don’t make “philosophy vs math” intrinsically slower. 

* **Tighten the claim:** Replace “processing speed remains constant (\~40–45 tok/s)” with “no *additional* slow-down beyond what is explained by prompt and output length under our settings (\<X tokens context).” Then report **TTFT** and **TPOT** across conditions; that mirrors standard metrics. 

**One more nuance to add:** as contexts get long, decoding *does* slow because each token attends to more KV entries (even with caching). So don’t overstate “no degradation”; just say “we controlled context length, so differences track verbosity, not compute.” 

**On using cost as a proxy:** Reasonable, but caveat it. Pricing is per token and—in some models—explicitly includes “thinking”/reasoning tokens. Anthropic states Sonnet 3.5 is $3/$15 per M input/output tokens; the newer Sonnet 3.7 says pricing “includes thinking tokens.” OpenAI’s o-series pages also note special billing for some reasoning models. Cite these and still report raw token counts. 

# **What else to compare / cite**

If you add the following comparisons \+ citations, your argument gets much stronger:

1. **Verbosity/length bias from RLHF**

    Show that longer outputs are a known bias and “reward hack,” independent of problem difficulty. This directly backs your “verbosity, not compute” thesis. 

2. **Chain-of-Thought (CoT) and deliberate methods inflate tokens**

    Position your *context-switching verbosity* alongside CoT/ToT: those techniques *intentionally* expand tokens; you’re finding an *unintentional* expansion at domain boundaries. Add a small ablation: same task, with/without “Let’s think step by step,” and show your amplification is above the CoT baseline. Also consider citing “concise CoT” work to motivate your mitigation section. 

3. **Long-context behavior is different (but related)**

    Acknowledge that accuracy degrades in long contexts (“lost in the middle”) but that’s about *retrieval/attention*, not verbosity. This helps separate your contribution from long-context literature. 

4. **Serving systems & KV-cache implications**

    Briefly connect your 5–6× token blow-up to real serving costs (batching, KV-cache pressure). PagedAttention/vLLM are canonical here. This grounds your systems implications. 

# **Concrete edits I’d make**

* **Section title:** change “No Performance Degradation” → “No Additional Compute Beyond Length Effects (Controlled Context).” Add TTFT/TPOT tables. 

* **Methods:** report **usage-level token counts** (prompt, output) alongside **cost**, since pricing varies by provider and may include special “thinking” tokens. 

* **Related work:** add short paras on (a) length bias in RLHF, (b) CoT/ToT token expansion, (c) long-context retrieval issues, (d) serving/KV-cache. 

* **Limitations:** note that your “constant tokens/s” holds for your (report them) context lengths and hardware; longer contexts or heavy batching change throughput.

