#!/bin/bash
# Clean pandoc conversion using XeLaTeX for Unicode support (simple version)
# Context-Switching Verbosity paper

# Allow specifying input file, default to V4 complete
INPUT_FILE="${1:-paper_v4_complete.md}"
OUTPUT_BASE="${2:-paper_xelatex}"

echo "Converting $INPUT_FILE to LaTeX with XeLaTeX (simple Unicode support)..."

# Convert markdown to LaTeX with XeLaTeX settings, use default fonts
pandoc "$INPUT_FILE" \
    -f markdown \
    -t latex \
    -o "${OUTPUT_BASE}.tex" \
    --standalone \
    --pdf-engine=xelatex \
    --variable documentclass=article \
    --variable classoption=11pt \
    --variable geometry:margin=1in \
    --metadata title="Quantifying Context-Switching Verbosity in Large Language Models: A ~5× Token Amplification Under <1K-Token Contexts" \
    --metadata author="D. Hart and C. Opus" \
    --metadata date="January 2025" \
    --bibliography=references.bib \
    --citeproc

echo "Conversion complete!"
echo ""
echo "Generating PDF with XeLaTeX (default fonts)..."
xelatex "${OUTPUT_BASE}.tex"
xelatex "${OUTPUT_BASE}.tex"  # Run twice for references

echo "PDF generated: ${OUTPUT_BASE}.pdf"