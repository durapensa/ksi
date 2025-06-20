# Prompt Composition System

A standardized, git-friendly system for composing AI prompts from modular components.

## 🎯 Why This Exists

**Problem**: AI prompt sharing is chaotic
- Scattered across forums, gists, repos with no organization
- Copy-paste culture with no modularity or reusability
- No standards for composition or collaboration
- Difficult to build on others' work systematically

**Solution**: A composition system that enables
- **Modular prompts** built from reusable components
- **Version control** friendly format that shows clean diffs
- **Community collaboration** with clear standards
- **Systematic organization** and discoverability

## 🏗️ Architecture

### Directory Structure
```
prompts/
├── components/          # Reusable markdown components
│   ├── system_identity.md
│   ├── workspace_isolation.md
│   └── analysis_framework.md
├── compositions/        # YAML composition recipes  
│   ├── autonomous_researcher.yaml
│   └── data_analyst.yaml
├── examples/           # Example outputs and usage
├── composer.py         # Composition engine
├── README.md          # This documentation
└── spec.md            # Technical specification
```

### How It Works

1. **Components** (`.md`) = Reusable prompt fragments with variables
2. **Compositions** (`.yaml`) = Recipes that combine components  
3. **Composer** (`.py`) = Engine that builds final prompts
4. **Context** (`.json`) = Variables injected at composition time

## 🚀 Quick Start

### Install
```bash
# Clone this repository or copy the prompts/ directory
git clone https://github.com/user/ksi
cd ksi/prompts

# Install dependencies
pip install pyyaml
```

### Compose a Prompt
```bash
# Basic usage
python composer.py autonomous_researcher --context '{
  "experiment_name": "entropy_analysis",
  "output_filename": "entropy_report.md", 
  "output_format": "markdown",
  "report_title": "Cognitive Entropy Analysis",
  "analysis_type": "entropy"
}'

# Save to file
python composer.py autonomous_researcher --context context.json -o final_prompt.txt

# List available compositions
python composer.py --list

# Validate a composition
python composer.py --validate autonomous_researcher
```

### Create Components
```markdown
<!-- components/my_component.md -->
# My Custom Component

You are {{role}} working on {{task_type}}.

## Instructions
{{custom_instructions}}
```

### Create Compositions
```yaml
# compositions/my_composition.yaml
name: "my_composition"
version: "1.0"
description: "Custom composition for specific use case"
author: "your-name"

components:
  - name: "identity"
    source: "components/my_component.md"
    vars:
      role: "data analyst"
      task_type: "statistical analysis"
      custom_instructions: "Focus on accuracy and validation"

required_context:
  dataset_path: "string - path to input dataset"
  
metadata:
  tags: ["analysis", "statistics"]
  use_cases: ["data_analysis"]
```

## 📖 Core Concepts

### Components
- **Reusable** prompt fragments in Markdown
- **Parameterized** with `{{variable}}` syntax
- **Focused** on single concerns (identity, tools, output format)
- **Git-friendly** with clear diffs

### Compositions  
- **Recipes** that combine components
- **Declarative** YAML format
- **Conditional** component inclusion
- **Validated** against required context

### Context
- **Runtime variables** injected during composition
- **Type-validated** against composition requirements
- **Flexible** JSON format for complex data

## 🌟 Community Features

### Sharing Standards
- **MIT License** by default for maximum reusability
- **Clear attribution** with author and repository fields
- **Version tracking** with semantic versioning
- **Documentation** requirements for community submissions

### Organization
- **Tags** for categorization and discovery
- **Use cases** for practical examples
- **Testing metadata** for compatibility tracking
- **Community categories** for specialized domains

### Contribution Guidelines
1. **Components** should be focused and reusable
2. **Compositions** should be well-documented with examples
3. **Variable names** should be descriptive and consistent
4. **Test your compositions** before sharing
5. **Follow semantic versioning** for updates

## 📊 Examples

### Research Agent
Perfect for autonomous analysis tasks:
- Workspace isolation
- Systematic analysis framework  
- Structured output requirements
- Tool permission guidelines

### Data Analyst
Focused on data analysis workflows:
- Data validation and cleaning
- Statistical analysis patterns
- Visualization guidelines
- Result interpretation

### Code Reviewer
Specialized for code review tasks:
- Review criteria and standards
- Language-specific guidelines
- Security considerations
- Constructive feedback patterns

## 🛠️ Advanced Usage

### Conditional Components
```yaml
components:
  - name: "advanced_analysis"
    source: "components/advanced_analysis.md"
    condition: "{{complexity_level}} == 'advanced'"
```

### Nested Variables
```yaml
components:
  - name: "output_format"
    source: "components/output_format.md"
    vars:
      format_type: "{{output_format}}"
      filename: "{{experiment_name}}_results.{{file_extension}}"
```

### Component Libraries
Organize components by domain:
```
components/
├── research/           # Research-specific components
├── analysis/          # Data analysis components  
├── coding/            # Programming-related components
└── general/           # General-purpose components
```

## 🔧 Integration

### With Python
```python
from composer import PromptComposer

composer = PromptComposer()
prompt = composer.compose("autonomous_researcher", {
    "experiment_name": "test",
    "output_filename": "results.md",
    # ... other context
})
```

### With CI/CD
```yaml
# .github/workflows/validate-prompts.yml
- name: Validate Prompt Compositions
  run: |
    for comp in prompts/compositions/*.yaml; do
      python prompts/composer.py --validate $(basename $comp .yaml)
    done
```

### With APIs
```python
def generate_analysis_prompt(experiment_config):
    return composer.compose("autonomous_researcher", experiment_config)
```

## 🎓 Learning Resources

- **spec.md** - Complete technical specification
- **examples/** - Working examples with outputs
- **community/** - Community-contributed compositions
- **tutorials/** - Step-by-step guides

## 🤝 Contributing

We welcome contributions! Please:

1. **Fork** the repository
2. **Create** new components or compositions
3. **Test** thoroughly with validation tools
4. **Document** your work clearly
5. **Submit** a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built by the ksi project** - Advancing systematic AI prompt engineering

*"Turning prompt chaos into collaborative standards"*