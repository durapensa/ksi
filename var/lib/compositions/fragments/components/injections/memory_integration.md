# Memory Integration

{{#if memory_context}}
## Collective Memory Context

{{#if memory_context.relevant_experiences}}
### Relevant Past Experiences
{{#each memory_context.relevant_experiences}}
- **{{title}}** ({{timestamp}})
  - Context: {{context}}
  - Outcome: {{outcome}}
  - Lessons: {{lessons_learned}}
  - Relevance Score: {{relevance_score}}
{{/each}}
{{/if}}

{{#if memory_context.patterns_detected}}
### Detected Patterns
{{#each memory_context.patterns_detected}}
- **Pattern**: {{name}}
  - Frequency: {{frequency}}
  - Confidence: {{confidence}}%
  - Implications: {{implications}}
{{/each}}
{{/if}}

{{#if memory_context.knowledge_gaps}}
### Identified Knowledge Gaps
{{#each memory_context.knowledge_gaps}}
- {{description}}
  - Priority: {{priority}}
  - Suggested Actions: {{#each suggested_actions}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}
{{/each}}
{{/if}}

### Memory Operations Available
- **Store Experience**: Save current findings to collective memory
  - Include: Context, approach, outcome, lessons learned
- **Query Experiences**: Search for similar past experiences
  - Filters: Time range, agent, outcome type, domain
- **Link Memories**: Connect related experiences for pattern detection
- **Tag for Retrieval**: Add semantic tags for future discovery

{{#if memory_context.storage_recommendation}}
### Storage Recommendation
{{memory_context.storage_recommendation.reason}}

Suggested tags: {{#each memory_context.storage_recommendation.tags}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}
{{/if}}

{{#if memory_context.synthesis_opportunity}}
### Knowledge Synthesis Opportunity
Multiple related experiences detected. Consider synthesizing insights:
- Common patterns: {{memory_context.synthesis_opportunity.common_patterns}}
- Divergent approaches: {{memory_context.synthesis_opportunity.divergent_approaches}}
- Potential new insights: {{memory_context.synthesis_opportunity.potential_insights}}
{{/if}}
{{/if}}