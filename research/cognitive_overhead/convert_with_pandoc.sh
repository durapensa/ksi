#!/bin/bash
# Pandoc-based conversion for arXiv submission
# Requires: brew install pandoc pandoc-citeproc

# Get default LaTeX template if needed
if [ ! -f arxiv-template.tex ]; then
    echo "Creating default template..."
    pandoc -D latex > arxiv-template.tex
    echo "Edit arxiv-template.tex to customize for arXiv"
fi

# Convert markdown to LaTeX
echo "Converting markdown to LaTeX..."
pandoc /Users/dp/projects/ksi/docs/PAPER_DRAFT_CONTEXT_SWITCHING_VERBOSITY_V2.md \
    -f markdown \
    -t latex \
    -o paper.tex \
    --standalone \
    --bibliography=paper.bib \
    --citeproc \
    --pdf-engine=pdflatex \
    --variable documentclass=article \
    --variable classoption=11pt \
    --variable geometry:margin=1in \
    --metadata title="Context-Switching Verbosity in Large Language Models: The Hidden 5× Token Amplification Effect" \
    --metadata author="D. Hart" \
    --metadata date="January 2025"

echo "Conversion complete!"
echo ""
echo "Next steps:"
echo "1. Review paper.tex for any issues"
echo "2. pdflatex paper.tex"
echo "3. bibtex paper"  
echo "4. pdflatex paper.tex"
echo "5. pdflatex paper.tex"