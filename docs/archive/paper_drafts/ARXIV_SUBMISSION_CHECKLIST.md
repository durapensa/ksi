# arXiv Submission Checklist for Context-Switching Verbosity Paper

## Document Status
**Date**: January 10, 2025  
**Target**: arXiv submission within 24 hours  
**Paper**: Context-Switching Verbosity in Large Language Models

## Technical Requirements ✓

### LaTeX Requirements
- [ ] **Convert to LaTeX** from Markdown (CRITICAL)
  - Use standard article class or arXiv template
  - Ensure TeX Live 2023 compatibility
  - No custom packages that might break compilation

### File Organization
- [ ] Main .tex file at root level (not in subdirectory)
- [ ] Bibliography as .bbl file (not .bib) - must match main filename
- [ ] All figures in standard formats (PDF, PNG, JPG)
- [ ] Use \includegraphics from graphicx package
- [ ] Case-sensitive file references

### Abstract Requirements ✓
- [x] Under 1,920 characters (currently ~800)
- [x] No "Abstract" header
- [x] LaTeX math commands supported via MathJax
- [x] Will be wrapped to 80 characters for email

## Content Requirements

### Current Status Assessment

#### COMPLETE ✓
1. **Core Finding**: 5-6x token amplification documented
2. **Methodology**: Clear experimental design with controls
3. **Results**: Primary metrics (CEC = 125±12 tokens)
4. **Discussion**: Connected to RLHF and CoT literature

#### NEEDS IMMEDIATE FIXING (Day 1)
1. **Convert to LaTeX** (2-3 hours)
   - Use standard article template
   - Convert tables to LaTeX format
   - Ensure figures are included properly

2. **Fix Citations** (1 hour)
   - Remove or find "Breaking Focus, 2025"
   - Add proper Anthropic API reference
   - Ensure all citations are complete

3. **Fill Real Appendices** (1 hour) - PARTIALLY DONE
   - [x] Appendix A: Complete prompts
   - [x] Appendix B: Model configuration
   - [x] Appendix C: Statistical methods
   - [ ] Appendix D: Code availability statement
   - [ ] Appendix E: Limitations

4. **Add Data & Code** (1 hour)
   - [ ] GitHub repository link
   - [ ] Data files with checksums
   - [ ] Reproduction instructions

#### NICE TO HAVE (Can submit without)
1. Cross-model validation with Qwen3:30b
2. N=100 samples (current N=50 acceptable for preliminary)
3. Manual validation of component analysis

## Submission Process

### Pre-submission
1. [ ] Create arXiv account if needed
2. [ ] Choose primary category: cs.CL (Computation and Language)
3. [ ] Consider cross-list: cs.AI (Artificial Intelligence)

### File Preparation
```bash
# Create submission package
mkdir arxiv_submission
cp paper.tex arxiv_submission/
cp paper.bbl arxiv_submission/  # Must run BibTeX locally first
cp figures/*.pdf arxiv_submission/
tar -czf arxiv_submission.tar.gz arxiv_submission/
```

### Submission Steps
1. [ ] Upload .tar.gz file
2. [ ] Verify PDF compilation (CRITICAL - must check)
3. [ ] Add metadata:
   - Title (exact match to paper)
   - Abstract (will be reformatted)
   - Authors and affiliations
   - Categories and keywords
4. [ ] Review and submit

## LaTeX Conversion Template

```latex
\documentclass[11pt]{article}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{url}
\usepackage{hyperref}

\title{Context-Switching Verbosity in Large Language Models: \\
       The Hidden 5× Token Amplification Effect}
\author{D. Hart\\
        Independent Researcher\\
        New York, NY USA\\
        \texttt{[email]}}
\date{January 2025}

\begin{document}
\maketitle

\begin{abstract}
We present the discovery that Large Language Models exhibit...
\end{abstract}

\section{Introduction}
...

\bibliographystyle{plain}
\bibliography{references}  % Will need references.bbl

\appendix
\section{Experimental Prompts}
...

\end{document}
```

## Critical Path (Next 24 Hours)

### Hour 1-3: LaTeX Conversion
- Convert paper to LaTeX
- Test compilation locally
- Fix any compilation errors

### Hour 4-5: Fix Citations & References
- Create proper .bib file
- Run BibTeX to generate .bbl
- Verify all citations resolve

### Hour 6-7: Final Content
- Add GitHub link
- Complete appendices
- Add limitations section

### Hour 8: Package & Test
- Create .tar.gz archive
- Test extraction and compilation
- Verify all files included

### Hour 9-10: Submit
- Upload to arXiv
- Complete metadata
- Submit for processing

## Fallback Options

If LaTeX conversion proves problematic:
1. Use Pandoc for initial conversion: `pandoc -s paper.md -o paper.tex`
2. Use Overleaf with TeX Live 2023 setting
3. Submit as "preliminary findings" to reduce expectations

## Notes

- arXiv doesn't have strict page limits - quality matters more than length
- "Preliminary findings" framing is acceptable for N=50
- Can update with v2 after full data collection
- Focus on reproducibility - include all code and data

## Success Criteria

Minimum viable submission:
- [ ] Compiles on TeX Live 2023
- [ ] Contains core finding (5-6x amplification)
- [ ] Includes methodology and some data
- [ ] Has working citations
- [ ] Provides reproduction materials

Remember: arXiv is for rapid dissemination. Perfect is the enemy of good.