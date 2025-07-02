# Output Requirements

## Final Output Specifications

### Primary Output
**File**: `{{final_output_path}}`
**Format**: {{output_format}}

### Output Structure Requirements

#### For Markdown Reports (.md)
```markdown
# {{report_title}}

## Executive Summary
- Key findings in 2-3 bullet points
- Main insights and conclusions

## Analysis Overview
- Data sources and scope
- Methods used
- Quality considerations

## Detailed Findings
[Detailed analysis results]

## Conclusions and Implications
- What do the results mean?
- What actions or insights follow?

## Methodology
- How the analysis was conducted
- Tools and techniques used
- Limitations and caveats

---
*Analysis completed: [timestamp]*
*Workspace: {{workspace_path}}*
```

#### For JSON Data (.json)
```json
{
  "metadata": {
    "analysis_type": "{{analysis_type}}",
    "timestamp": "ISO-8601 timestamp",
    "workspace": "{{workspace_path}}",
    "data_sources": ["list of input sources"]
  },
  "summary": {
    "key_findings": ["list of main insights"],
    "metrics": {"key": "value"}
  },
  "detailed_results": {
    // Structured analysis results
  },
  "methodology": {
    "approach": "description",
    "tools_used": ["list"],
    "limitations": ["list"]
  }
}
```

### Quality Standards
- **Accuracy**: Results must be correct and validated
- **Completeness**: Address all aspects of the analysis scope
- **Clarity**: Clear, understandable presentation
- **Actionability**: Insights that can inform decisions
- **Reproducibility**: Others can understand and recreate the work

### File Naming Conventions
- Use descriptive, consistent names
- Include analysis type when relevant
- Follow project naming standards

### Workspace Documentation
Create a `README.md` in your workspace explaining:
- What analysis was performed
- How to run your scripts
- What each file contains
- Any dependencies or requirements