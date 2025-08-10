# **Novelty (what’s new)**

* **Framing a specific, measurable “context-switching verbosity” effect** distinct from RLHF length bias, CoT prompting, and long-context retrieval issues. The paper claims **5–6× token amplification** when prompts switch domains and argues the latency increase is fully explained by longer outputs, not harder computation.   

* **Quantification of per-switch cost** via a linear model (\~**125 ± 12 tokens** per switch). If robust, that’s a concrete, usable metric. 

* **Compute framing with serving metrics (TTFT/TPOT)** that shows decode speed stays flat (\~22–23 ms/token) across conditions under \<1K tokens. This focuses the discussion on output length instead of “semantic difficulty.”   

* **Cross-model replication** (Claude 3.5, Qwen3:30B) suggesting generality. 

Overall, the “context-switching verbosity” construct and the CEC estimate are novel enough for an arXiv note, provided methods are tightened and claims are scoped.

# **Methodology (what’s solid vs. thin)**

**Strengths**

* Clear conditions & controls (single-domain vs. multi-domain; constant prompt length; fixed difficulty; no explicit CoT). 

* Sensible primary metrics (tokens, TTFT, TPOT, total time) plus derived measures (CEC, VAF, TTO). 

**What needs shoring up before upload**

1. **Experimental details are placeholders.** Appendices for prompts, model versions, hardware, power analyses are currently “to-be-filled.” These must be real before arXiv. 

2. **Sampling & randomness.** You cite N=500 (5×100) for the regression; specify random seeds, temperature/top-p, stop tokens, and whether prompts were randomized or counterbalanced. 

3. **Latency measurement hygiene.** Clarify whether TTFT/TPOT were measured server-side or via client wall-clock; how you controlled for network jitter; whether batch size / concurrency varied; and whether you normalized for sequence length effects in decode. (You already note \<1K-token scope; good.) 

4. **Attribution of verbosity components.** The 40%/35%/25% split needs a method: coding scheme, annotator instructions, inter-rater agreement (e.g., Cohen’s κ), or automated labeling with error analysis. 

5. **Model/config parity.** For cross-model validation, state exact versions, decoding params, and hardware for each model (Claude API vs. local Qwen) to avoid confounds. 

6. **Stats & uncertainty.** Report confidence intervals on “5–6×,” include regression diagnostics, residual plots, and—since multiple conditions are compared—your multiple-comparison plan (your Appendix B heading promises this). 

# **Findings & presentation (clarity and evidence)**

**What lands well**

* Tables make the core effect obvious (baseline vs. multi-domain; constant TPOT).   

* The simple linear relation “Output\_Tokens \= 87.3 \+ 124.6 × N\_switches” is crisp. Consider promoting this to a figure. 

* Practical mitigations table is useful for practitioners. 

**Upgrades that would help**

* Add **plots**: (a) scatter \+ fit for tokens vs. \#switches with per-condition CIs; (b) distribution of estimated CEC; (c) TTFT and TPOT vs. output length. This will visually back your “no additional compute beyond length” claim. 

* Show **ablation**: apply “Structured Output,” “Explicit Brevity,” etc., to the multi-domain condition and plot token savings \+ quality proxy (exact-match on math answers, for example). 

* Clarify **scope**: you already state the \<1K-token limit in Limitations; echo this in the Abstract/Title to avoid over-generalization. 

# **Gaps to close before arXiv (actionable checklist)**

* **Fill the appendices with full replication detail** (prompts; seeds; decoding params; model/version; hardware; API endpoints; scripts). Include a one-command repro script and a dataset card. 

* **Tighten citations.**

  * “Breaking Focus, 2025” is cited in the intro but missing from References—either add a full entry or remove. 

  * “Anthropic, 2024” (pricing/“thinking tokens”) appears in text but is not in References—add the exact source. 

  * Consider replacing informal “o3’s suggestion” with a citable artifact or move it to Acknowledgments only. 

* **Define terms operationally.** What constitutes a “cognitive context/domain,” and how is a **switch** detected? Provide programmatic rules (e.g., task tags) and examples. 

* **Quality/accuracy controls.** Report whether extra verbosity harmed task accuracy (e.g., arithmetic correctness). If unaffected, say so with numbers; if harmed, quantify. (Your mitigations table implies minimal impact for structured outputs—document the metric.) 

* **Threats to validity.** Expand on network effects, provider throttling, temperature-driven variance, and whether safety/guardrail preambles inflated tokens in some domains. You already note hardware/batch sensitivity; make this a dedicated subsection. 

* **Scope the headline.** “Hidden 5×” reads a bit splashy. Consider: *“Quantifying Context-Switching Verbosity in LLMs: A \~5× Token Amplification Under \<1K-Token Contexts.”* This aligns the title with your stated constraints. 

* **Cross-model breadth.** If feasible, add one more family (e.g., Llama-3.x or Mistral-Medium) to bolster the “universality” claim—or soften the wording. 

* **Component analysis method.** Document how you computed the 40/35/25% breakdown (annotation protocol \+ agreement). 

# **Bottom line**

Promising idea with practical punch. If you (i) replace placeholders with full repro assets, (ii) formalize the statistics and component-labeling method, (iii) clean up citations/scope, and (iv) add 1–2 clarity figures, this will be a strong arXiv preprint that others can replicate and build on. The core claim (constant TPOT; \~125 tokens per switch; \~5× amplification) is crisp and actionable once the methodology is fully documented.  

User: re (i) replace placeholders with full repro assets, do you mean pointers to filenames or actually including the content of these assets, formatted, into the paper?

For arXiv, put the *critical, human-readable bits directly in the paper* (appendix), and ship the *full, machine-readable kit as ancillary files and a versioned repo/DOI*. Here’s a practical split that works well:

### **What to include** 

### **in the PDF**

###  **(appendices)**

* **Exact base prompts** for each condition (single-domain, multi-domain with N switches).

* **All decoding/config params**: model name/version string, temperature, top-p, max tokens, stop sequences, seed, system prompts, safety toggles.

* **Hardware/serving details**: provider/API, date(s) of runs, batch/concurrency, latency measurement method.

* **Minimal repro recipe**: one “how to run” command and the expected artifacts (e.g., results/run\_2025-08-05.csv).

* **Stats details**: regression formula, CIs, multiple-comparison plan.

* **Pointers \+ hashes** for larger assets (see below), so readers can verify integrity without leaving the PDF (e.g., SHA256 of the prompt pack and results CSV).

Rule of thumb: if a section is ≤2–4 pages and textual (prompts, configs), inline it. It helps auditability and protects against link rot.

### **What to ship as** 

### **ancillary files**

###  **on arXiv (+ mirrored repo/DOI)**

* prompts/ all prompt templates as plain .txt (one per condition).

* scripts/ exact runner used (run\_experiment.py, analyze\_tokens.py).

* environment/ (requirements.txt or environment.yml, and ideally a Dockerfile).

* results/ raw JSONL per trial (tokens, TTFT, TPOT, timing breakdowns) \+ aggregated CSVs.

* figures/ notebook(s) used to generate plots.

* LICENSE and a short README.md with a one-command repro (make reproduce).

Upload these as arXiv **ancillary files** (arXiv shows them under “Ancillary files”) *and* tag a GitHub release archived on **Zenodo** to get a DOI. In the PDF, cite both the arXiv ancillary package and the DOI; include commit hashes.

### **How to reference them in the paper**

* In Methods: “All prompts are listed in Appendix C; the complete prompt pack is in prompts/ (SHA256: …). The runner (scripts/run\_experiment.py, commit abcd123) and raw outputs (results/\*.jsonl) are available as arXiv ancillary files and Zenodo DOI: …”

* In figure captions/tables: add a small “Asset map” row (e.g., “Fig. 3 uses results/run\_2025-08-05.csv”).

### **What** 

### **not**

###  **to inline**

* Large logs, JSONL dumps, notebooks, binaries. Keep those as ancillary/repo to avoid a bloated PDF.

### **Extra polish that reviewers love**

* A **config file** (config.yaml) checked into the pack that reproduces the exact runs.

* **Determinism notes** for API models (date/time of calls, known non-determinism, retry policy).

* Content **hashes** for key files and the **Git commit** you ran.

* A tiny **repro checklist** at the top of the appendix.

Bottom line: put enough **content** in the paper so someone can reproduce without clicking (prompts \+ params \+ analysis spec), and attach the full **assets** as ancillary \+ DOI so nothing disappears later.

