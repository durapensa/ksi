#!/usr/bin/env python3
"""
Real-time Meta-Cognitive Capture System
Analyzes conversation patterns and cognitive processes in real-time
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib

class MetaCognitiveCapture:
    """Real-time analysis and capture of meta-cognitive patterns"""
    
    def __init__(self, output_dir: str = "cognitive_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Analysis state
        self.session_context = {}
        self.conversation_depth = 0
        self.topic_threads = []
        self.cognitive_patterns = {}
        
        # Output files
        self.meta_log = self.output_dir / "meta_cognitive.jsonl"
        self.pattern_log = self.output_dir / "cognitive_patterns.jsonl"
        self.session_analytics = self.output_dir / "session_analytics.jsonl"
    
    def analyze_human_input(self, content: str, session_id: str) -> Dict[str, Any]:
        """Analyze human input for cognitive patterns"""
        analysis = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "type": "human_input_analysis",
            "content_hash": hashlib.md5(content.encode()).hexdigest()[:8],
            "analysis": {}
        }
        
        # Question patterns
        questions = len(re.findall(r'[?]', content))
        analysis["analysis"]["question_count"] = questions
        analysis["analysis"]["is_interrogative"] = questions > 0
        
        # Command patterns
        commands = self._detect_commands(content)
        analysis["analysis"]["commands"] = commands
        analysis["analysis"]["is_directive"] = len(commands) > 0
        
        # Cognitive indicators
        cognitive_markers = self._detect_cognitive_markers(content)
        analysis["analysis"]["cognitive_markers"] = cognitive_markers
        
        # Complexity metrics
        analysis["analysis"]["complexity"] = self._assess_complexity(content)
        
        # Emotional/intent indicators
        analysis["analysis"]["intent"] = self._detect_intent(content)
        
        # Context tracking
        analysis["analysis"]["conversation_depth"] = self.conversation_depth
        analysis["analysis"]["builds_on_previous"] = self._detect_context_building(content)
        
        self._log_analysis(analysis)
        return analysis
    
    def analyze_claude_response(self, output: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analyze Claude response for meta-cognitive patterns"""
        result = output.get('result', '')
        
        analysis = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "type": "claude_response_analysis",
            "response_hash": hashlib.md5(result.encode()).hexdigest()[:8],
            "analysis": {}
        }
        
        # Response structure analysis
        analysis["analysis"]["structure"] = self._analyze_response_structure(result)
        
        # Reasoning patterns
        analysis["analysis"]["reasoning_patterns"] = self._detect_reasoning_patterns(result)
        
        # Problem-solving approach
        analysis["analysis"]["problem_solving"] = self._analyze_problem_solving(result)
        
        # Information density
        analysis["analysis"]["information_density"] = self._calculate_information_density(result)
        
        # Cognitive load indicators
        analysis["analysis"]["cognitive_load"] = self._assess_cognitive_load(output)
        
        # Meta-cognitive awareness
        analysis["analysis"]["meta_awareness"] = self._detect_meta_awareness(result)
        
        # Conversational dynamics
        analysis["analysis"]["conversational_dynamics"] = self._analyze_conversational_dynamics(result)
        
        self._log_analysis(analysis)
        self._update_session_patterns(session_id, analysis)
        return analysis
    
    def capture_interaction_pattern(self, human_input: str, claude_output: Dict[str, Any], session_id: str):
        """Capture the complete interaction pattern for deeper analysis"""
        
        interaction = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "type": "interaction_pattern",
            "interaction_id": hashlib.md5(f"{human_input}{claude_output.get('result', '')}".encode()).hexdigest()[:12],
            "pattern_analysis": {}
        }
        
        # Input-Output relationship
        interaction["pattern_analysis"]["response_alignment"] = self._analyze_response_alignment(
            human_input, claude_output.get('result', '')
        )
        
        # Cognitive flow
        interaction["pattern_analysis"]["cognitive_flow"] = self._trace_cognitive_flow(
            human_input, claude_output.get('result', '')
        )
        
        # Problem evolution
        interaction["pattern_analysis"]["problem_evolution"] = self._track_problem_evolution(
            human_input, claude_output.get('result', '')
        )
        
        # Learning indicators
        interaction["pattern_analysis"]["learning_indicators"] = self._detect_learning_patterns(
            human_input, claude_output.get('result', '')
        )
        
        # Collaboration quality
        interaction["pattern_analysis"]["collaboration_quality"] = self._assess_collaboration_quality(
            human_input, claude_output.get('result', '')
        )
        
        self._log_pattern(interaction)
        self._update_conversation_context(interaction)
    
    def generate_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive session summary with meta-cognitive insights"""
        
        summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "type": "session_summary",
            "meta_cognitive_summary": {}
        }
        
        # Session-level patterns
        if session_id in self.session_context:
            ctx = self.session_context[session_id]
            
            summary["meta_cognitive_summary"]["interaction_count"] = ctx.get("interaction_count", 0)
            summary["meta_cognitive_summary"]["dominant_patterns"] = self._identify_dominant_patterns(ctx)
            summary["meta_cognitive_summary"]["cognitive_evolution"] = self._trace_cognitive_evolution(ctx)
            summary["meta_cognitive_summary"]["collaboration_quality"] = self._assess_session_collaboration(ctx)
            summary["meta_cognitive_summary"]["learning_trajectory"] = self._analyze_learning_trajectory(ctx)
            summary["meta_cognitive_summary"]["meta_insights"] = self._extract_meta_insights(ctx)
        
        self._log_session_analytics(summary)
        return summary
    
    # Private analysis methods
    
    def _detect_commands(self, content: str) -> List[str]:
        """Detect command-like patterns in input"""
        commands = []
        
        # Imperative verbs
        imperative_patterns = [
            r'\b(create|make|build|implement|add|fix|update|modify|change|remove|delete)\b',
            r'\b(show|display|list|print|output|generate|produce)\b',
            r'\b(analyze|examine|check|test|verify|validate)\b',
            r'\b(explain|describe|tell|clarify|elaborate)\b'
        ]
        
        for pattern in imperative_patterns:
            matches = re.findall(pattern, content.lower())
            commands.extend(matches)
        
        return list(set(commands))
    
    def _detect_cognitive_markers(self, content: str) -> Dict[str, int]:
        """Detect cognitive processing markers"""
        markers = {
            "uncertainty": len(re.findall(r'\b(maybe|perhaps|possibly|might|could|uncertain|unsure)\b', content.lower())),
            "certainty": len(re.findall(r'\b(definitely|certainly|absolutely|clearly|obviously)\b', content.lower())),
            "reasoning": len(re.findall(r'\b(because|since|therefore|thus|hence|consequently)\b', content.lower())),
            "comparison": len(re.findall(r'\b(compare|contrast|versus|vs|better|worse|similar|different)\b', content.lower())),
            "prioritization": len(re.findall(r'\b(first|second|priority|important|critical|essential)\b', content.lower())),
            "temporal": len(re.findall(r'\b(before|after|then|next|later|previously|now|currently)\b', content.lower())),
        }
        return markers
    
    def _assess_complexity(self, content: str) -> Dict[str, Any]:
        """Assess cognitive complexity of input"""
        return {
            "word_count": len(content.split()),
            "sentence_count": len(re.split(r'[.!?]+', content)),
            "avg_sentence_length": len(content.split()) / max(1, len(re.split(r'[.!?]+', content))),
            "technical_terms": len(re.findall(r'\b[A-Z][a-z]*[A-Z][a-zA-Z]*\b', content)),  # CamelCase
            "nested_concepts": content.count('(') + content.count('['),
        }
    
    def _detect_intent(self, content: str) -> Dict[str, bool]:
        """Detect user intent patterns"""
        return {
            "seeking_help": bool(re.search(r'\b(help|assist|support|guide)\b', content.lower())),
            "providing_feedback": bool(re.search(r'\b(good|bad|wrong|correct|feedback|review)\b', content.lower())),
            "exploring": bool(re.search(r'\b(explore|investigate|discover|learn|understand)\b', content.lower())),
            "planning": bool(re.search(r'\b(plan|strategy|approach|design|architecture)\b', content.lower())),
            "problem_solving": bool(re.search(r'\b(problem|issue|bug|error|fix|solve)\b', content.lower())),
        }
    
    def _detect_context_building(self, content: str) -> bool:
        """Detect if input builds on previous conversation"""
        context_indicators = [
            r'\b(this|that|it|they|them)\b',
            r'\b(also|additionally|furthermore|moreover)\b',
            r'\b(but|however|although|though)\b',
            r'\b(continue|continuing|further|next)\b'
        ]
        
        for pattern in context_indicators:
            if re.search(pattern, content.lower()):
                return True
        return False
    
    def _analyze_response_structure(self, result: str) -> Dict[str, Any]:
        """Analyze structural patterns in Claude's response"""
        return {
            "has_headers": bool(re.search(r'^#{1,6}\s', result, re.MULTILINE)),
            "has_lists": bool(re.search(r'^\s*[-*+]\s', result, re.MULTILINE)),
            "has_code": bool(re.search(r'```', result)),
            "has_emphasis": bool(re.search(r'\*\*.*?\*\*', result)),
            "paragraph_count": len(re.split(r'\n\s*\n', result.strip())),
            "organization_score": self._calculate_organization_score(result)
        }
    
    def _detect_reasoning_patterns(self, result: str) -> Dict[str, int]:
        """Detect reasoning patterns in response"""
        return {
            "causal_reasoning": len(re.findall(r'\b(because|since|due to|caused by|results in)\b', result.lower())),
            "conditional_reasoning": len(re.findall(r'\b(if|unless|provided that|assuming)\b', result.lower())),
            "comparative_reasoning": len(re.findall(r'\b(whereas|while|compared to|in contrast)\b', result.lower())),
            "sequential_reasoning": len(re.findall(r'\b(first|then|next|finally|subsequently)\b', result.lower())),
            "analytical_reasoning": len(re.findall(r'\b(analyze|examine|consider|evaluate)\b', result.lower())),
        }
    
    def _analyze_problem_solving(self, result: str) -> Dict[str, Any]:
        """Analyze problem-solving approach in response"""
        return {
            "breaks_down_problem": bool(re.search(r'\b(step|stage|phase|part|component)\b', result.lower())),
            "provides_alternatives": len(re.findall(r'\b(alternative|option|choice|approach)\b', result.lower())),
            "systematic_approach": bool(re.search(r'\b(systematic|methodical|structured)\b', result.lower())),
            "considers_tradeoffs": bool(re.search(r'\b(tradeoff|trade-off|pros|cons|advantage|disadvantage)\b', result.lower())),
            "future_oriented": bool(re.search(r'\b(future|next|upcoming|plan|roadmap)\b', result.lower())),
        }
    
    def _calculate_information_density(self, result: str) -> Dict[str, float]:
        """Calculate information density metrics"""
        words = result.split()
        unique_words = set(word.lower().strip('.,!?;:') for word in words)
        
        return {
            "unique_word_ratio": len(unique_words) / max(1, len(words)),
            "avg_word_length": sum(len(word) for word in words) / max(1, len(words)),
            "technical_density": len(re.findall(r'\b[a-z]+[A-Z][a-zA-Z]*\b', result)) / max(1, len(words)),
            "concept_density": (result.count('(') + result.count('[')) / max(1, len(words)),
        }
    
    def _assess_cognitive_load(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Assess cognitive load indicators from Claude output"""
        return {
            "response_time_ms": output.get('duration_ms', 0),
            "api_time_ms": output.get('duration_api_ms', 0),
            "token_usage": output.get('usage', {}),
            "complexity_indicator": output.get('duration_ms', 0) / max(1, len(output.get('result', '').split())),
        }
    
    def _detect_meta_awareness(self, result: str) -> Dict[str, bool]:
        """Detect meta-cognitive awareness in response"""
        return {
            "acknowledges_uncertainty": bool(re.search(r'\b(uncertain|unsure|unclear|ambiguous)\b', result.lower())),
            "reflects_on_process": bool(re.search(r'\b(thinking|reasoning|approach|method)\b', result.lower())),
            "shows_self_awareness": bool(re.search(r'\b(I think|I believe|in my view|it seems)\b', result.lower())),
            "requests_clarification": bool(re.search(r'\b(clarify|specify|elaborate|explain)\b', result.lower())),
        }
    
    def _analyze_conversational_dynamics(self, result: str) -> Dict[str, Any]:
        """Analyze conversational dynamics in response"""
        return {
            "acknowledgment": bool(re.search(r'\b(yes|I see|understood|got it|right)\b', result.lower())),
            "building_on_input": bool(re.search(r'\b(building on|expanding|extending)\b', result.lower())),
            "collaborative_tone": len(re.findall(r'\b(we|us|together|collaborate)\b', result.lower())),
            "teaching_mode": bool(re.search(r'\b(explain|show|demonstrate|illustrate)\b', result.lower())),
        }
    
    def _calculate_organization_score(self, result: str) -> float:
        """Calculate organizational clarity score"""
        score = 0.0
        
        # Headers and structure
        if re.search(r'^#{1,6}\s', result, re.MULTILINE):
            score += 0.3
        
        # Lists and enumeration
        if re.search(r'^\s*[-*+]\s', result, re.MULTILINE):
            score += 0.2
        
        # Paragraph breaks
        paragraphs = len(re.split(r'\n\s*\n', result.strip()))
        if paragraphs > 1:
            score += min(0.3, paragraphs * 0.1)
        
        # Code blocks
        if re.search(r'```', result):
            score += 0.2
        
        return min(1.0, score)
    
    def _analyze_response_alignment(self, human_input: str, claude_result: str) -> Dict[str, Any]:
        """Analyze how well Claude's response aligns with human input"""
        # Simple keyword overlap analysis
        human_words = set(re.findall(r'\b\w+\b', human_input.lower()))
        claude_words = set(re.findall(r'\b\w+\b', claude_result.lower()))
        
        overlap = len(human_words & claude_words)
        total_unique = len(human_words | claude_words)
        
        return {
            "keyword_overlap_ratio": overlap / max(1, total_unique),
            "addresses_question": bool(re.search(r'[?]', human_input)) and len(claude_result) > 20,
            "response_length_ratio": len(claude_result.split()) / max(1, len(human_input.split())),
            "maintains_context": overlap > 0,
        }
    
    def _trace_cognitive_flow(self, human_input: str, claude_result: str) -> Dict[str, Any]:
        """Trace the cognitive flow from input to output"""
        return {
            "flow_continuity": self._assess_flow_continuity(human_input, claude_result),
            "cognitive_jumps": self._detect_cognitive_jumps(human_input, claude_result),
            "elaboration_depth": len(claude_result.split()) / max(1, len(human_input.split())),
            "maintains_thread": self._check_thread_maintenance(human_input, claude_result),
        }
    
    def _track_problem_evolution(self, human_input: str, claude_result: str) -> Dict[str, Any]:
        """Track how problems evolve through the interaction"""
        return {
            "problem_refined": bool(re.search(r'\b(clarify|refine|narrow|focus)\b', claude_result.lower())),
            "solution_proposed": bool(re.search(r'\b(solution|approach|method|way)\b', claude_result.lower())),
            "alternatives_offered": len(re.findall(r'\b(alternative|option|instead|alternatively)\b', claude_result.lower())),
            "complexity_addressed": self._assess_complexity_handling(human_input, claude_result),
        }
    
    def _detect_learning_patterns(self, human_input: str, claude_result: str) -> Dict[str, bool]:
        """Detect learning patterns in the interaction"""
        return {
            "knowledge_building": bool(re.search(r'\b(learn|understand|build|develop)\b', claude_result.lower())),
            "concept_introduction": bool(re.search(r'\b(concept|idea|principle|theory)\b', claude_result.lower())),
            "skill_transfer": bool(re.search(r'\b(apply|use|implement|practice)\b', claude_result.lower())),
            "metacognitive_guidance": bool(re.search(r'\b(think|reason|approach|strategy)\b', claude_result.lower())),
        }
    
    def _assess_collaboration_quality(self, human_input: str, claude_result: str) -> Dict[str, float]:
        """Assess the quality of collaboration in the interaction"""
        collaboration_score = 0.0
        
        # Acknowledgment and building
        if re.search(r'\b(yes|I see|building on|expanding)\b', claude_result.lower()):
            collaboration_score += 0.3
        
        # Collaborative language
        collaborative_terms = len(re.findall(r'\b(we|us|together|collaborate|work together)\b', claude_result.lower()))
        collaboration_score += min(0.3, collaborative_terms * 0.1)
        
        # Constructive response
        if len(claude_result) > len(human_input):
            collaboration_score += 0.2
        
        # Question engagement
        if '?' in human_input and len(claude_result) > 50:
            collaboration_score += 0.2
        
        return {
            "collaboration_score": min(1.0, collaboration_score),
            "engagement_level": "high" if collaboration_score > 0.7 else "medium" if collaboration_score > 0.4 else "low",
        }
    
    # Utility methods for complex analysis
    
    def _assess_flow_continuity(self, human_input: str, claude_result: str) -> float:
        """Assess logical flow continuity"""
        # Simplified continuity assessment
        transition_words = len(re.findall(r'\b(therefore|thus|consequently|however|moreover)\b', claude_result.lower()))
        return min(1.0, transition_words * 0.2)
    
    def _detect_cognitive_jumps(self, human_input: str, claude_result: str) -> int:
        """Detect sudden topic or cognitive jumps"""
        # Simplified jump detection
        human_topics = set(re.findall(r'\b[A-Z][a-z]+\b', human_input))
        claude_topics = set(re.findall(r'\b[A-Z][a-z]+\b', claude_result))
        
        new_topics = claude_topics - human_topics
        return len(new_topics)
    
    def _check_thread_maintenance(self, human_input: str, claude_result: str) -> bool:
        """Check if conversational thread is maintained"""
        # Simple thread maintenance check
        key_words = re.findall(r'\b\w{4,}\b', human_input.lower())
        return any(word in claude_result.lower() for word in key_words[:3])
    
    def _assess_complexity_handling(self, human_input: str, claude_result: str) -> Dict[str, Any]:
        """Assess how complexity is handled"""
        return {
            "breaks_down_complexity": bool(re.search(r'\b(step|part|component|aspect)\b', claude_result.lower())),
            "addresses_multiple_aspects": len(re.findall(r'\b(first|second|also|additionally)\b', claude_result.lower())),
            "provides_structure": bool(re.search(r'^[-*#]', claude_result, re.MULTILINE)),
        }
    
    # Context and pattern management
    
    def _update_conversation_context(self, interaction: Dict[str, Any]):
        """Update conversation context with new interaction"""
        session_id = interaction["session_id"]
        
        if session_id not in self.session_context:
            self.session_context[session_id] = {
                "interactions": [],
                "patterns": {},
                "evolution": [],
                "start_time": datetime.utcnow().isoformat() + "Z"
            }
        
        self.session_context[session_id]["interactions"].append(interaction)
        self.session_context[session_id]["last_update"] = datetime.utcnow().isoformat() + "Z"
        
        # Update conversation depth
        self.conversation_depth += 1
    
    def _update_session_patterns(self, session_id: str, analysis: Dict[str, Any]):
        """Update session-level patterns"""
        if session_id not in self.cognitive_patterns:
            self.cognitive_patterns[session_id] = {
                "response_patterns": [],
                "reasoning_evolution": [],
                "complexity_trend": [],
            }
        
        self.cognitive_patterns[session_id]["response_patterns"].append(analysis["analysis"])
        
        # Track reasoning evolution
        reasoning = analysis["analysis"].get("reasoning_patterns", {})
        self.cognitive_patterns[session_id]["reasoning_evolution"].append(reasoning)
        
        # Track complexity trend
        complexity = analysis["analysis"].get("cognitive_load", {})
        self.cognitive_patterns[session_id]["complexity_trend"].append(complexity)
    
    # Session-level analysis methods
    
    def _identify_dominant_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify dominant patterns in session"""
        interactions = context.get("interactions", [])
        if not interactions:
            return {}
        
        # Aggregate pattern analysis
        pattern_counts = {}
        for interaction in interactions:
            patterns = interaction.get("pattern_analysis", {})
            for key, value in patterns.items():
                if key not in pattern_counts:
                    pattern_counts[key] = []
                pattern_counts[key].append(value)
        
        return {
            "most_common_patterns": list(pattern_counts.keys())[:5],
            "interaction_count": len(interactions),
            "avg_complexity": sum(len(str(i)) for i in interactions) / len(interactions)
        }
    
    def _trace_cognitive_evolution(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Trace cognitive evolution through session"""
        interactions = context.get("interactions", [])
        evolution = []
        
        for i, interaction in enumerate(interactions):
            evolution.append({
                "step": i + 1,
                "timestamp": interaction.get("timestamp"),
                "cognitive_shift": self._detect_cognitive_shift(interaction, interactions[:i]),
                "complexity_change": self._assess_complexity_change(interaction, interactions[:i])
            })
        
        return evolution
    
    def _assess_session_collaboration(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall session collaboration quality"""
        interactions = context.get("interactions", [])
        if not interactions:
            return {"score": 0.0, "quality": "unknown"}
        
        collaboration_scores = []
        for interaction in interactions:
            collab = interaction.get("pattern_analysis", {}).get("collaboration_quality", {})
            if "collaboration_score" in collab:
                collaboration_scores.append(collab["collaboration_score"])
        
        if not collaboration_scores:
            return {"score": 0.0, "quality": "unknown"}
        
        avg_score = sum(collaboration_scores) / len(collaboration_scores)
        
        return {
            "score": avg_score,
            "quality": "excellent" if avg_score > 0.8 else "good" if avg_score > 0.6 else "fair" if avg_score > 0.4 else "poor",
            "trend": "improving" if collaboration_scores[-1] > collaboration_scores[0] else "stable",
        }
    
    def _analyze_learning_trajectory(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze learning trajectory through session"""
        interactions = context.get("interactions", [])
        
        learning_indicators = []
        for interaction in interactions:
            learning = interaction.get("pattern_analysis", {}).get("learning_indicators", {})
            learning_indicators.append(learning)
        
        return {
            "learning_progression": len([l for l in learning_indicators if l.get("knowledge_building", False)]),
            "concept_density": len([l for l in learning_indicators if l.get("concept_introduction", False)]),
            "skill_application": len([l for l in learning_indicators if l.get("skill_transfer", False)]),
            "meta_guidance": len([l for l in learning_indicators if l.get("metacognitive_guidance", False)]),
        }
    
    def _extract_meta_insights(self, context: Dict[str, Any]) -> List[str]:
        """Extract high-level meta-insights from session"""
        insights = []
        interactions = context.get("interactions", [])
        
        if len(interactions) > 5:
            insights.append("Extended deep-dive conversation")
        
        # Check for problem-solving patterns
        problem_solving_count = sum(1 for i in interactions 
                                   if i.get("pattern_analysis", {}).get("problem_evolution", {}).get("solution_proposed", False))
        
        if problem_solving_count > len(interactions) * 0.6:
            insights.append("Problem-solving focused session")
        
        # Check for learning patterns
        learning_count = sum(1 for i in interactions 
                           if i.get("pattern_analysis", {}).get("learning_indicators", {}).get("knowledge_building", False))
        
        if learning_count > len(interactions) * 0.5:
            insights.append("Learning-oriented session")
        
        return insights
    
    def _detect_cognitive_shift(self, current: Dict[str, Any], previous: List[Dict[str, Any]]) -> bool:
        """Detect significant cognitive shifts"""
        if not previous:
            return False
        
        # Simple shift detection based on pattern changes
        current_patterns = set(current.get("pattern_analysis", {}).keys())
        if previous:
            prev_patterns = set(previous[-1].get("pattern_analysis", {}).keys())
            return len(current_patterns - prev_patterns) > 2
        
        return False
    
    def _assess_complexity_change(self, current: Dict[str, Any], previous: List[Dict[str, Any]]) -> str:
        """Assess complexity change from previous interactions"""
        if not previous:
            return "baseline"
        
        # Simplified complexity assessment
        current_complexity = len(str(current))
        prev_complexity = len(str(previous[-1])) if previous else 0
        
        if current_complexity > prev_complexity * 1.2:
            return "increased"
        elif current_complexity < prev_complexity * 0.8:
            return "decreased"
        else:
            return "stable"
    
    # Logging methods
    
    def _log_analysis(self, analysis: Dict[str, Any]):
        """Log analysis to meta-cognitive log"""
        with open(self.meta_log, 'a') as f:
            f.write(json.dumps(analysis) + '\n')
    
    def _log_pattern(self, pattern: Dict[str, Any]):
        """Log pattern analysis"""
        with open(self.pattern_log, 'a') as f:
            f.write(json.dumps(pattern) + '\n')
    
    def _log_session_analytics(self, analytics: Dict[str, Any]):
        """Log session analytics"""
        with open(self.session_analytics, 'a') as f:
            f.write(json.dumps(analytics) + '\n')


# Convenience functions for integration

def create_meta_capture_hooks(capture_system: MetaCognitiveCapture):
    """Create hooks for integration with chat.py"""
    
    def on_human_input(content: str, session_id: str) -> Dict[str, Any]:
        """Hook for human input analysis"""
        return capture_system.analyze_human_input(content, session_id)
    
    def on_claude_response(output: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Hook for Claude response analysis"""
        return capture_system.analyze_claude_response(output, session_id)
    
    def on_interaction_complete(human_input: str, claude_output: Dict[str, Any], session_id: str):
        """Hook for complete interaction analysis"""
        capture_system.capture_interaction_pattern(human_input, claude_output, session_id)
    
    def on_session_end(session_id: str) -> Dict[str, Any]:
        """Hook for session summary generation"""
        return capture_system.generate_session_summary(session_id)
    
    return {
        "on_human_input": on_human_input,
        "on_claude_response": on_claude_response,
        "on_interaction_complete": on_interaction_complete,
        "on_session_end": on_session_end,
    }


if __name__ == "__main__":
    # Test the meta-cognitive capture system
    capture = MetaCognitiveCapture()
    hooks = create_meta_capture_hooks(capture)
    
    # Simulate some interactions
    test_session = "test-session-123"
    
    # Test human input analysis
    human_analysis = hooks["on_human_input"]("Can you help me understand how recursion works in programming?", test_session)
    print("Human input analysis:", json.dumps(human_analysis, indent=2))
    
    # Test Claude response analysis
    claude_output = {
        "result": "Recursion is a programming technique where a function calls itself to solve smaller instances of the same problem. Here are the key concepts:\n\n1. **Base Case**: The condition that stops the recursion\n2. **Recursive Case**: The function calling itself with modified parameters\n\nFor example, calculating factorial:\n```python\ndef factorial(n):\n    if n <= 1:  # Base case\n        return 1\n    return n * factorial(n-1)  # Recursive case\n```",
        "session_id": test_session,
        "duration_ms": 2500,
        "usage": {"input_tokens": 15, "output_tokens": 120}
    }
    
    claude_analysis = hooks["on_claude_response"](claude_output, test_session)
    print("\nClaude response analysis:", json.dumps(claude_analysis, indent=2))
    
    # Test interaction pattern capture
    hooks["on_interaction_complete"](
        "Can you help me understand how recursion works in programming?",
        claude_output,
        test_session
    )
    
    # Test session summary
    session_summary = hooks["on_session_end"](test_session)
    print("\nSession summary:", json.dumps(session_summary, indent=2))