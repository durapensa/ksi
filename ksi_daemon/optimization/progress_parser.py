"""DSPy progress parser for extracting optimization progress from stderr output."""

import re
from typing import Dict, Any, Optional, Tuple
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("dspy_progress_parser")


class DSPyProgressParser:
    """Parser for DSPy optimization progress from stderr output."""
    
    def __init__(self):
        self.trial_progress = {}
        self.score_history = []
        self.current_step = 0
        self.total_steps = 0
    
    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line of stderr output."""
        return parse_dspy_progress(line)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of parsed progress."""
        return {
            "trial_progress": self.trial_progress,
            "score_history": self.score_history,
            "current_step": self.current_step,
            "total_steps": self.total_steps
        }


def parse_dspy_progress(stderr_line: str) -> Optional[Dict[str, Any]]:
    """Parse DSPy stderr output for progress information.
    
    Returns dict with progress info or None if not a progress line.
    """
    progress_info = {}
    
    # Pattern for trial progress: "Trial 3/10"
    trial_match = re.search(r'Trial\s+(\d+)/(\d+)', stderr_line)
    if trial_match:
        current_trial = int(trial_match.group(1))
        total_trials = int(trial_match.group(2))
        progress_info['trial_current'] = current_trial
        progress_info['trial_total'] = total_trials
        progress_info['trial_progress'] = current_trial / total_trials
    
    # Pattern for scores: "Score: 0.875" or "score=0.875"
    score_match = re.search(r'(?:Score|score)[:\s=]+(\d+\.?\d*)', stderr_line)
    if score_match:
        progress_info['current_score'] = float(score_match.group(1))
    
    # Pattern for best score: "Best Score: 0.925"
    best_score_match = re.search(r'Best\s+Score[:\s]+(\d+\.?\d*)', stderr_line, re.IGNORECASE)
    if best_score_match:
        progress_info['best_score'] = float(best_score_match.group(1))
    
    # Pattern for step info: "STEP 1:" or "==> STEP 2:"
    step_match = re.search(r'(?:==>)?\s*STEP\s+(\d+):', stderr_line)
    if step_match:
        progress_info['current_step'] = int(step_match.group(1))
        progress_info['step_description'] = stderr_line.strip()
    
    # Pattern for bootstrapping progress
    bootstrap_match = re.search(r'Bootstrapping.*?(\d+)%', stderr_line)
    if bootstrap_match:
        progress_info['bootstrap_progress'] = int(bootstrap_match.group(1))
    
    # Pattern for evaluation progress: "100%|██████████| 1/1"
    eval_match = re.search(r'(\d+)%\|[█▓▒░\s]*\|\s*(\d+)/(\d+)', stderr_line)
    if eval_match:
        progress_info['eval_percent'] = int(eval_match.group(1))
        progress_info['eval_current'] = int(eval_match.group(2))
        progress_info['eval_total'] = int(eval_match.group(3))
    
    # Pattern for time estimates: "[00:12<00:00, 12.07s/it]"
    time_match = re.search(r'\[(\d+:\d+)<(\d+:\d+),\s*([\d.]+)s/it\]', stderr_line)
    if time_match:
        progress_info['time_elapsed'] = time_match.group(1)
        progress_info['time_remaining'] = time_match.group(2)
        progress_info['seconds_per_item'] = float(time_match.group(3))
    
    # Pattern for auto mode settings
    if "AUTO RUN SETTINGS" in stderr_line:
        progress_info['phase'] = 'initialization'
        progress_info['message'] = 'Configuring optimization settings'
    
    # Pattern for compilation complete
    if "compile() complete" in stderr_line or "Optimization complete" in stderr_line:
        progress_info['phase'] = 'completed'
        progress_info['message'] = 'Optimization finished'
    
    return progress_info if progress_info else None


def extract_optimization_summary(full_stderr: str) -> Dict[str, Any]:
    """Extract summary information from complete DSPy stderr output."""
    summary = {
        'total_trials': 0,
        'completed_trials': 0,
        'best_score': 0.0,
        'final_score': 0.0,
        'steps_completed': [],
        'total_time': None,
        'settings': {}
    }
    
    lines = full_stderr.split('\n')
    
    for line in lines:
        # Extract auto mode settings
        if "num_trials:" in line:
            match = re.search(r'num_trials:\s*(\d+)', line)
            if match:
                summary['total_trials'] = int(match.group(1))
        
        # Extract final results
        if "Best program found" in line:
            score_match = re.search(r'score[:\s=]+(\d+\.?\d*)', line)
            if score_match:
                summary['final_score'] = float(score_match.group(1))
        
        # Track completed trials
        trial_match = re.search(r'Trial\s+(\d+)/(\d+)', line)
        if trial_match:
            summary['completed_trials'] = max(
                summary['completed_trials'], 
                int(trial_match.group(1))
            )
        
        # Track best score seen
        score_match = re.search(r'(?:Score|score)[:\s=]+(\d+\.?\d*)', line)
        if score_match:
            score = float(score_match.group(1))
            summary['best_score'] = max(summary['best_score'], score)
    
    return summary