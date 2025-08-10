# Context-Switching Verbosity in Large Language Models

## arXiv Submission Package

This directory contains the submission-ready materials for the paper:
**"Context-Switching Verbosity in Large Language Models: The Hidden 5× Token Amplification Effect"**

## Contents

- `paper.tex` - LaTeX source (generated from markdown via pandoc)
- `paper.pdf` - Compiled PDF for submission
- `references.bib` - Bibliography
- `convert.sh` - Conversion script from markdown to LaTeX
- `README.md` - This file

## Data and Scripts

Full experimental data and analysis scripts available at:
https://github.com/durapensa/ksi/tree/main/research/context_switching_verbosity

## Building the Paper

```bash
# Convert markdown to LaTeX
./convert.sh

# Generate PDF
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex
```

## Abstract

We present the discovery that Large Language Models exhibit predictable verbosity amplification when switching between cognitive contexts, generating 5-6× more tokens without additional computational overhead beyond what is explained by token length. Our findings distinguish unintentional context-switching verbosity from deliberate reasoning techniques like Chain-of-Thought.

## Contact

D. Hart  
Independent Researcher  
New York, NY USA

## License

This work is licensed under CC BY 4.0.