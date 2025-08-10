#!/usr/bin/env python3
"""
Automated Component Analysis for Context-Switching Verbosity
Categorizes response text into establishment, bridging, and meta-cognitive components
With manual validation capability
"""

import re
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ComponentAnalysisResult:
    """Result of component analysis for a single response"""
    response_id: str
    total_words: int
    establishment_words: int
    establishment_pct: float
    bridging_words: int
    bridging_pct: float
    meta_cognitive_words: int
    meta_cognitive_pct: float
    task_content_words: int
    task_content_pct: float
    matched_patterns: List[str]
    
class VerbosityComponentAnalyzer:
    """
    Automated categorization of response components
    Following GPT-5's requirement for documented methodology
    """
    
    # Establishment patterns - setting up new context
    ESTABLISHMENT_MARKERS = [
        r"(?i)\b(now|turning to|let me address|moving on to|switching to)\b",
        r"(?i)\b(first|second|third|fourth|fifth|next|then|finally)\b",
        r"(?i)\b(for the .{1,20} part|regarding the .{1,20} question)\b",
        r"(?i)\b(let's start with|beginning with|starting with)\b",
        r"(?i)\b(calculate|solve|compute|find)\b.*:",  # Task setup
    ]
    
    # Bridging patterns - connecting contexts
    BRIDGING_MARKERS = [
        r"(?i)\b(this connects to|building on|relates to|similar to)\b",
        r"(?i)\b(as mentioned|previously|earlier|before|above)\b",
        r"(?i)\b(in contrast|however|whereas|on the other hand|alternatively)\b",
        r"(?i)\b(returning to|back to|continuing from)\b",
        r"(?i)\b(furthermore|additionally|moreover|also)\b",
    ]
    
    # Meta-cognitive patterns - self-awareness of process
    META_COGNITIVE_MARKERS = [
        r"(?i)\b(I notice|I observe|I'm aware|it's interesting)\b",
        r"(?i)\b(this requires|thinking about|considering how|reflecting on)\b",
        r"(?i)\b(different mode|switching between|cognitive|mental)\b",
        r"(?i)\b(my approach|my thinking|my process|I'm)\b",
        r"(?i)\b(awareness|conscious|self-referential|meta)\b",
    ]
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.validation_samples = []
        
    def analyze_response(self, response_text: str, response_id: str = None) -> ComponentAnalysisResult:
        """
        Analyze a single response and categorize its components
        
        Args:
            response_text: The LLM response to analyze
            response_id: Optional identifier for tracking
            
        Returns:
            ComponentAnalysisResult with breakdown
        """
        if response_id is None:
            response_id = f"resp_{datetime.now():%Y%m%d_%H%M%S}"
        
        # Split into sentences for analysis
        sentences = self._split_sentences(response_text)
        
        # Track word counts by category
        categorized = {
            'establishment': 0,
            'bridging': 0,
            'meta_cognitive': 0,
            'task_content': 0
        }
        
        matched_patterns = []
        
        for sentence in sentences:
            words_in_sentence = len(sentence.split())
            
            # Check each category (order matters - first match wins)
            if patterns := self._matches_patterns(sentence, self.ESTABLISHMENT_MARKERS):
                categorized['establishment'] += words_in_sentence
                matched_patterns.extend([f"ESTABLISH: {p}" for p in patterns])
                
            elif patterns := self._matches_patterns(sentence, self.BRIDGING_MARKERS):
                categorized['bridging'] += words_in_sentence
                matched_patterns.extend([f"BRIDGE: {p}" for p in patterns])
                
            elif patterns := self._matches_patterns(sentence, self.META_COGNITIVE_MARKERS):
                categorized['meta_cognitive'] += words_in_sentence
                matched_patterns.extend([f"META: {p}" for p in patterns])
                
            else:
                categorized['task_content'] += words_in_sentence
        
        # Calculate totals and percentages
        total_words = sum(categorized.values())
        
        if total_words == 0:
            # Empty response
            return ComponentAnalysisResult(
                response_id=response_id,
                total_words=0,
                establishment_words=0,
                establishment_pct=0.0,
                bridging_words=0,
                bridging_pct=0.0,
                meta_cognitive_words=0,
                meta_cognitive_pct=0.0,
                task_content_words=0,
                task_content_pct=0.0,
                matched_patterns=[]
            )
        
        result = ComponentAnalysisResult(
            response_id=response_id,
            total_words=total_words,
            establishment_words=categorized['establishment'],
            establishment_pct=(categorized['establishment'] / total_words) * 100,
            bridging_words=categorized['bridging'],
            bridging_pct=(categorized['bridging'] / total_words) * 100,
            meta_cognitive_words=categorized['meta_cognitive'],
            meta_cognitive_pct=(categorized['meta_cognitive'] / total_words) * 100,
            task_content_words=categorized['task_content'],
            task_content_pct=(categorized['task_content'] / total_words) * 100,
            matched_patterns=matched_patterns[:10]  # Limit for readability
        )
        
        if self.verbose:
            self._print_analysis(result)
        
        return result
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences, handling common edge cases"""
        # Simple sentence splitter - could be improved with NLTK
        sentences = re.split(r'[.!?]\s+', text)
        # Filter empty sentences
        return [s.strip() for s in sentences if s.strip()]
    
    def _matches_patterns(self, text: str, patterns: List[str]) -> List[str]:
        """Check if text matches any patterns, return matched patterns"""
        matched = []
        for pattern in patterns:
            if re.search(pattern, text):
                matched.append(pattern[:30])  # Truncate for readability
        return matched
    
    def _print_analysis(self, result: ComponentAnalysisResult):
        """Print detailed analysis for debugging"""
        print(f"\nAnalysis for {result.response_id}:")
        print(f"  Total words: {result.total_words}")
        print(f"  Establishment: {result.establishment_pct:.1f}% ({result.establishment_words} words)")
        print(f"  Bridging: {result.bridging_pct:.1f}% ({result.bridging_words} words)")
        print(f"  Meta-cognitive: {result.meta_cognitive_pct:.1f}% ({result.meta_cognitive_words} words)")
        print(f"  Task content: {result.task_content_pct:.1f}% ({result.task_content_words} words)")
        if result.matched_patterns:
            print(f"  Patterns: {', '.join(result.matched_patterns[:3])}")
    
    def analyze_dataset(self, responses: List[Dict]) -> Dict:
        """
        Analyze multiple responses and compute aggregate statistics
        
        Args:
            responses: List of response dictionaries with 'text' and 'id' fields
            
        Returns:
            Aggregate statistics dictionary
        """
        results = []
        
        for response in responses:
            text = response.get('text', response.get('response', ''))
            resp_id = response.get('id', response.get('agent_id', None))
            
            result = self.analyze_response(text, resp_id)
            results.append(result)
        
        # Compute aggregate statistics
        establishment_pcts = [r.establishment_pct for r in results]
        bridging_pcts = [r.bridging_pct for r in results]
        meta_pcts = [r.meta_cognitive_pct for r in results]
        task_pcts = [r.task_content_pct for r in results]
        
        aggregate = {
            'n_responses': len(results),
            'establishment': {
                'mean_pct': np.mean(establishment_pcts),
                'std_pct': np.std(establishment_pcts),
                'ci_95': self._compute_ci(establishment_pcts)
            },
            'bridging': {
                'mean_pct': np.mean(bridging_pcts),
                'std_pct': np.std(bridging_pcts),
                'ci_95': self._compute_ci(bridging_pcts)
            },
            'meta_cognitive': {
                'mean_pct': np.mean(meta_pcts),
                'std_pct': np.std(meta_pcts),
                'ci_95': self._compute_ci(meta_pcts)
            },
            'task_content': {
                'mean_pct': np.mean(task_pcts),
                'std_pct': np.std(task_pcts),
                'ci_95': self._compute_ci(task_pcts)
            },
            'individual_results': results
        }
        
        return aggregate
    
    def _compute_ci(self, values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Compute confidence interval using bootstrap"""
        if len(values) < 2:
            return (0, 0)
        
        n_bootstrap = 1000
        bootstrap_means = []
        
        for _ in range(n_bootstrap):
            sample = np.random.choice(values, len(values), replace=True)
            bootstrap_means.append(np.mean(sample))
        
        alpha = (1 - confidence) / 2
        ci_lower = np.percentile(bootstrap_means, alpha * 100)
        ci_upper = np.percentile(bootstrap_means, (1 - alpha) * 100)
        
        return (ci_lower, ci_upper)
    
    def prepare_manual_validation(self, results: List[ComponentAnalysisResult], n_samples: int = 20) -> Dict:
        """
        Prepare samples for manual validation
        
        Args:
            results: Automated analysis results
            n_samples: Number of samples for manual coding
            
        Returns:
            Validation template dictionary
        """
        # Stratified sampling - try to get samples from each condition
        n_per_category = n_samples // 5  # 5 conditions
        
        validation_template = {
            'instructions': """
            Manual Component Coding Instructions:
            
            1. ESTABLISHMENT (Setting up new context):
               - Phrases like "Now let's...", "Turning to...", "First/Second/Third..."
               - Setting up a new task or topic
               
            2. BRIDGING (Connecting contexts):
               - Phrases like "This connects to...", "As mentioned...", "Building on..."
               - References to previous content
               
            3. META-COGNITIVE (Self-awareness):
               - Phrases like "I notice...", "This requires different thinking..."
               - Comments about the cognitive process
               
            4. TASK CONTENT (Direct task execution):
               - Actual calculations, direct answers
               - No transition or meta-commentary
            
            For each sentence, assign to ONE category based on primary function.
            """,
            'samples': [],
            'coder_name': '',
            'coding_date': datetime.now().isoformat()
        }
        
        # Select random samples
        sample_indices = np.random.choice(len(results), min(n_samples, len(results)), replace=False)
        
        for idx in sample_indices:
            result = results[idx]
            validation_template['samples'].append({
                'sample_id': result.response_id,
                'text': '',  # To be filled with actual response text
                'automated_coding': {
                    'establishment': result.establishment_pct,
                    'bridging': result.bridging_pct,
                    'meta_cognitive': result.meta_cognitive_pct,
                    'task_content': result.task_content_pct
                },
                'manual_coding': {
                    'establishment': None,
                    'bridging': None,
                    'meta_cognitive': None,
                    'task_content': None
                },
                'notes': ''
            })
        
        return validation_template
    
    def compute_agreement(self, validation_data: Dict) -> float:
        """
        Compute Cohen's kappa for inter-rater agreement
        
        Args:
            validation_data: Completed validation template
            
        Returns:
            Cohen's kappa value
        """
        automated = []
        manual = []
        
        for sample in validation_data['samples']:
            # Get primary category for each
            auto = sample['automated_coding']
            man = sample['manual_coding']
            
            if man['establishment'] is None:
                continue  # Skip uncoded samples
            
            # Find primary category (highest percentage)
            auto_primary = max(auto.items(), key=lambda x: x[1])[0]
            man_primary = max(man.items(), key=lambda x: x[1])[0]
            
            automated.append(auto_primary)
            manual.append(man_primary)
        
        if len(automated) < 2:
            return 0.0
        
        # Compute Cohen's kappa
        from sklearn.metrics import cohen_kappa_score
        kappa = cohen_kappa_score(automated, manual)
        
        return kappa


def main():
    """Example usage and testing"""
    
    # Initialize analyzer
    analyzer = VerbosityComponentAnalyzer(verbose=True)
    
    # Test with example responses
    test_responses = [
        {
            'id': 'test_1',
            'text': """First, let me calculate 47 + 89. This equals 136.
            Now turning to the second calculation, 156 - 78 equals 78.
            I notice I'm switching between different arithmetic operations here.
            Finally, 34 × 3 equals 102."""
        },
        {
            'id': 'test_2',
            'text': """47 + 89 = 136. 156 - 78 = 78. 34 × 3 = 102. 144 ÷ 12 = 12. 25 + 67 = 92."""
        }
    ]
    
    # Analyze dataset
    results = analyzer.analyze_dataset(test_responses)
    
    # Print aggregate results
    print("\n" + "=" * 60)
    print("AGGREGATE COMPONENT ANALYSIS")
    print("=" * 60)
    print(f"N = {results['n_responses']} responses analyzed")
    print()
    
    for component in ['establishment', 'bridging', 'meta_cognitive', 'task_content']:
        stats = results[component]
        ci = stats['ci_95']
        print(f"{component.upper()}:")
        print(f"  Mean: {stats['mean_pct']:.1f}%")
        print(f"  95% CI: [{ci[0]:.1f}%, {ci[1]:.1f}%]")
        print()
    
    # Prepare manual validation
    validation = analyzer.prepare_manual_validation(results['individual_results'], n_samples=2)
    
    print("Manual validation template prepared")
    print(f"Samples selected: {len(validation['samples'])}")
    
    # Save validation template
    with open('manual_validation_template.json', 'w') as f:
        json.dump(validation, f, indent=2)
    
    print("\nValidation template saved to manual_validation_template.json")


if __name__ == "__main__":
    main()