# Context-Switching Verbosity Experiment Configuration

# Model Configuration
MODEL_NAME = "claude-3.5-sonnet"
API_PROVIDER = "anthropic"  # anthropic, openai, ksi

# Experiment Parameters
DEFAULT_SAMPLES_PER_CONDITION = 10
FULL_EXPERIMENT_SAMPLES = 100
RANDOM_SEED = 42

# Output Configuration
RESULTS_DIR = "results"
FIGURES_DIR = "figures"
LOG_LEVEL = "INFO"

# API Configuration (set environment variables)
# export ANTHROPIC_API_KEY="your-key-here"
# export OPENAI_API_KEY="your-key-here"

# Rate Limiting
REQUESTS_PER_SECOND = 5
REQUEST_TIMEOUT_SECONDS = 30
