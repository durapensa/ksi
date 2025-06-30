#!/usr/bin/env python3
"""
Composition Selector Module

Provides intelligent selection of prompt compositions based on agent characteristics,
task requirements, and available compositions.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add path for discovery module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.discovery import CompositionDiscovery, CompositionInfo

logger = logging.getLogger('composition_selector')


@dataclass
class SelectionContext:
    """Context for composition selection"""
    agent_id: str
    role: Optional[str] = None
    capabilities: Optional[List[str]] = None
    task_description: Optional[str] = None
    preferred_style: Optional[str] = None
    context_variables: Optional[Dict[str, Any]] = None


@dataclass
class SelectionResult:
    """Result of composition selection"""
    composition_name: str
    score: float
    reasons: List[str]
    fallback_used: bool = False


class CompositionSelector:
    """Intelligent selector for prompt compositions"""
    
    def __init__(self):
        self.discovery = CompositionDiscovery()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_scored = []  # Store last scoring results
        
    async def select_composition(self, context: SelectionContext) -> SelectionResult:
        """
        Select the best composition for the given context
        
        Uses a multi-factor scoring algorithm considering:
        - Role compatibility
        - Capability requirements
        - Task relevance
        - Metadata matches
        """
        # Check cache first
        cache_key = self._make_cache_key(context)
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                logger.debug(f"Using cached composition selection for {context.agent_id}")
                return cached_result
        
        # Get all available compositions
        try:
            all_compositions = await self.discovery.get_all_compositions(include_metadata=True)
        except Exception as e:
            logger.error(f"Failed to get compositions: {e}")
            return self._get_fallback_result()
        
        # Score each composition
        scored_compositions = []
        for name, comp_info in all_compositions.items():
            score, reasons = await self._score_composition(comp_info, context)
            if score > 0:
                scored_compositions.append((name, score, reasons))
        
        # Sort by score and select the best
        if scored_compositions:
            scored_compositions.sort(key=lambda x: x[1], reverse=True)
            best_name, best_score, best_reasons = scored_compositions[0]
            
            result = SelectionResult(
                composition_name=best_name,
                score=best_score,
                reasons=best_reasons,
                fallback_used=False
            )
            
            # Cache the result
            self._cache[cache_key] = (result, datetime.now())
            
            logger.info(f"Selected composition '{best_name}' for {context.agent_id} (score: {best_score:.2f})")
            
            # Store scored list for potential reuse
            self._last_scored = scored_compositions
            return result
        else:
            logger.warning(f"No suitable composition found for {context.agent_id}, using fallback")
            return self._get_fallback_result()
    
    async def _score_composition(self, comp_info: CompositionInfo, context: SelectionContext) -> Tuple[float, List[str]]:
        """Score a composition against the selection context"""
        score = 0.0
        reasons = []
        
        # 1. Role matching (weight: 30%)
        if context.role and comp_info.metadata.get('role'):
            if context.role.lower() == comp_info.metadata['role'].lower():
                score += 30
                reasons.append(f"Exact role match: {context.role}")
            elif context.role.lower() in comp_info.metadata.get('compatible_roles', []):
                score += 20
                reasons.append(f"Compatible role: {context.role}")
        
        # 2. Capability requirements (weight: 25%)
        if context.capabilities:
            comp_caps = comp_info.metadata.get('capabilities_required', [])
            comp_provides = comp_info.metadata.get('capabilities_provided', [])
            
            # Check if composition requires capabilities the agent has
            if comp_caps:
                matching_caps = set(context.capabilities) & set(comp_caps)
                if matching_caps:
                    cap_score = (len(matching_caps) / len(comp_caps)) * 25
                    score += cap_score
                    reasons.append(f"Capability match: {', '.join(matching_caps)}")
            
            # Check if composition provides capabilities the agent needs
            if comp_provides:
                useful_caps = set(comp_provides) & set(context.capabilities)
                if useful_caps:
                    score += 10
                    reasons.append(f"Provides useful capabilities: {', '.join(useful_caps)}")
        
        # 3. Task relevance (weight: 25%)
        if context.task_description:
            task_keywords = context.task_description.lower().split()
            
            # Check description
            desc_matches = sum(1 for kw in task_keywords if kw in comp_info.description.lower())
            if desc_matches:
                score += min(desc_matches * 5, 15)
                reasons.append(f"Description matches task ({desc_matches} keywords)")
            
            # Check tags
            comp_tags = [tag.lower() for tag in comp_info.metadata.get('tags', [])]
            tag_matches = sum(1 for kw in task_keywords if any(kw in tag for tag in comp_tags))
            if tag_matches:
                score += min(tag_matches * 3, 10)
                reasons.append(f"Tags match task ({tag_matches} matches)")
        
        # 4. Style preference (weight: 10%)
        if context.preferred_style:
            comp_style = comp_info.metadata.get('style', '').lower()
            if context.preferred_style.lower() in comp_style:
                score += 10
                reasons.append(f"Style match: {context.preferred_style}")
        
        # 5. General quality indicators (weight: 10%)
        # Prefer newer versions
        try:
            version = float(comp_info.version)
            if version >= 2.0:
                score += 5
                reasons.append("Recent version")
        except (ValueError, TypeError):
            pass
        
        # Prefer well-documented compositions
        if len(comp_info.metadata.get('use_cases', [])) >= 2:
            score += 3
            reasons.append("Well-documented use cases")
        
        if comp_info.metadata.get('tested', False):
            score += 2
            reasons.append("Tested composition")
        
        return score, reasons
    
    async def suggest_compositions(self, context: SelectionContext, top_n: int = 3) -> List[SelectionResult]:
        """Get top N composition suggestions for the context"""
        # Get all available compositions
        try:
            all_compositions = await self.discovery.get_all_compositions(include_metadata=True)
        except Exception as e:
            logger.error(f"Failed to get compositions: {e}")
            return [self._get_fallback_result()]
        
        # Score all compositions
        scored_results = []
        for name, comp_info in all_compositions.items():
            score, reasons = await self._score_composition(comp_info, context)
            if score > 0:
                result = SelectionResult(
                    composition_name=name,
                    score=score,
                    reasons=reasons,
                    fallback_used=False
                )
                scored_results.append(result)
        
        # Sort by score and return top N
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_n]
    
    async def validate_selection(self, composition_name: str, context: SelectionContext) -> Dict[str, Any]:
        """Validate that a selected composition will work with the given context"""
        # Build context dict for validation
        context_dict = {
            'agent_id': context.agent_id
        }
        
        if context.role:
            context_dict['role'] = context.role
        
        if context.capabilities:
            context_dict['capabilities'] = context.capabilities
        
        if context.context_variables:
            context_dict.update(context.context_variables)
        
        # Use discovery API to validate
        return await self.discovery.validate_context(composition_name, context_dict)
    
    def _make_cache_key(self, context: SelectionContext) -> str:
        """Create a cache key from selection context"""
        key_parts = [
            context.agent_id,
            context.role or 'no-role',
            ','.join(sorted(context.capabilities or [])),
            context.task_description or 'no-task',
            context.preferred_style or 'no-style'
        ]
        return '|'.join(key_parts)
    
    def _get_fallback_result(self) -> SelectionResult:
        """Get fallback result when no composition can be selected"""
        return SelectionResult(
            composition_name='claude_agent_default',
            score=0.0,
            reasons=['Fallback: No suitable composition found'],
            fallback_used=True
        )
    
    def clear_cache(self):
        """Clear the selection cache"""
        self._cache.clear()
        self._last_scored = []
        logger.info("Composition selection cache cleared")
    
    async def get_scored_compositions(self, context: SelectionContext) -> List[Tuple[str, float, List[str]]]:
        """Get all compositions with their scores for the given context."""
        # If we just scored, return cached results
        if self._last_scored:
            return self._last_scored
        
        # Otherwise, perform scoring
        try:
            all_compositions = await self.discovery.get_all_compositions(include_metadata=True)
        except Exception as e:
            logger.error(f"Failed to get compositions: {e}")
            return []
        
        scored_compositions = []
        for name, comp_info in all_compositions.items():
            score, reasons = await self._score_composition(comp_info, context)
            if score > 0:
                scored_compositions.append((name, score, reasons))
        
        scored_compositions.sort(key=lambda x: x[1], reverse=True)
        self._last_scored = scored_compositions
        return scored_compositions


# Convenience functions

async def select_composition_for_agent(agent_id: str, role: str = None, 
                                     capabilities: List[str] = None,
                                     task: str = None) -> str:
    """Quick function to select a composition for an agent"""
    selector = CompositionSelector()
    context = SelectionContext(
        agent_id=agent_id,
        role=role,
        capabilities=capabilities,
        task_description=task
    )
    result = await selector.select_composition(context)
    return result.composition_name


async def main():
    """CLI interface for testing composition selection"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test composition selection")
    parser.add_argument("--agent-id", required=True, help="Agent ID")
    parser.add_argument("--role", help="Agent role")
    parser.add_argument("--capabilities", help="Comma-separated capabilities")
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--style", help="Preferred style")
    parser.add_argument("--suggest", action="store_true", help="Show top 3 suggestions")
    
    args = parser.parse_args()
    
    # Build context
    context = SelectionContext(
        agent_id=args.agent_id,
        role=args.role,
        capabilities=args.capabilities.split(',') if args.capabilities else None,
        task_description=args.task,
        preferred_style=args.style
    )
    
    selector = CompositionSelector()
    
    if args.suggest:
        # Show suggestions
        suggestions = await selector.suggest_compositions(context, top_n=3)
        print(f"\nTop composition suggestions for {args.agent_id}:")
        for i, result in enumerate(suggestions, 1):
            print(f"\n{i}. {result.composition_name} (score: {result.score:.1f})")
            for reason in result.reasons:
                print(f"   - {reason}")
    else:
        # Select single best
        result = await selector.select_composition(context)
        print(f"\nSelected composition: {result.composition_name}")
        print(f"Score: {result.score:.1f}")
        print("Reasons:")
        for reason in result.reasons:
            print(f"  - {reason}")
        
        if not result.fallback_used:
            # Validate the selection
            validation = await selector.validate_selection(result.composition_name, context)
            if validation['valid']:
                print("\n✓ Context validation passed")
            else:
                print("\n✗ Context validation failed:")
                print(f"  Missing: {', '.join(validation.get('missing_context', []))}")


if __name__ == "__main__":
    asyncio.run(main())