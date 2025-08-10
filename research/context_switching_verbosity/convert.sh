#!/bin/bash
# Clean pandoc conversion for arXiv submission
# Context-Switching Verbosity paper

echo "Converting Context-Switching Verbosity paper to LaTeX..."

# Convert markdown to LaTeX with proper settings
pandoc /Users/dp/projects/ksi/docs/PAPER_DRAFT_CONTEXT_SWITCHING_VERBOSITY_V3.md \
    -f markdown \
    -t latex \
    -o paper.tex \
    --standalone \
    --pdf-engine=pdflatex \
    --variable documentclass=article \
    --variable classoption=11pt \
    --variable geometry:margin=1in \
    --metadata title="Context-Switching Verbosity in Large Language Models: The Hidden 5× Token Amplification Effect" \
    --metadata author="D. Hart" \
    --metadata date="January 2025" \
    --bibliography=references.bib \
    --citeproc

echo "Conversion complete!"
echo ""
echo "To generate PDF:"
echo "1. pdflatex paper.tex"
echo "2. bibtex paper"
echo "3. pdflatex paper.tex"
echo "4. pdflatex paper.tex"