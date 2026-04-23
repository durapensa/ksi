# Component Deprecation Process

## Version 1.0.0
Date: 2025-01-28  
Status: ACTIVE

## Overview

This document defines the standardized process for deprecating KSI components that are obsolete, uncertifiable, or replaced by better alternatives.

## Deprecation Triggers

### Automatic Deprecation
Components are automatically marked for deprecation when:
- **Certification Failure**: Score below 0.70 after 3 attempts
- **Security Issues**: Identified vulnerabilities that cannot be patched
- **Obsolete Patterns**: Using deprecated architectural patterns
- **No Maintainer**: Abandoned for > 180 days with issues

### Manual Deprecation
Components may be manually deprecated for:
- **Better Alternative Available**: Superior component exists
- **Architectural Changes**: No longer fits system design
- **Performance Issues**: Consistently poor performance
- **Maintenance Burden**: Too complex or fragile

## Deprecation Phases

### Phase 1: Warning (30 days)
```yaml
# Component frontmatter update
certification:
  status: deprecated_pending
  deprecated_date: "2025-01-28"
  warning_until: "2025-02-27"
  removal_date: "2025-04-28"
  replacement: "components/modern/alternative"
  reason: "Obsolete pattern - use modern alternative"
```

**Actions**:
- Add deprecation notice to component
- Log warnings when component is used
- Notify dependent components
- Create migration guide

### Phase 2: Deprecated (60 days)
```yaml
certification:
  status: deprecated
  deprecated_date: "2025-02-27"
  removal_date: "2025-04-28"
  replacement: "components/modern/alternative"
  migration_guide: "/docs/migrations/old_to_new.md"
```

**Actions**:
- Errors in production environment
- Warnings become errors in staging
- Block new dependencies
- Automated migration assistance

### Phase 3: Archived (90 days)
```yaml
certification:
  status: archived
  archived_date: "2025-04-28"
  archive_location: "components/_archive/2025Q2/"
  replacement: "components/modern/alternative"
```

**Actions**:
- Move to archive folder
- Remove from component index
- Error on any usage attempt
- Preserve for historical reference

### Phase 4: Removal (120+ days)
- Complete deletion from repository
- Update all documentation
- Final cleanup of references
- Close related issues

## Deprecation Categories

### 1. Obsolete Concepts
**Components**: DSL interpreters, code generators
**Reason**: Fundamental misunderstanding - LLMs ARE interpreters
**Action**: Immediate deprecation, no grace period
```bash
# Mark as obsolete
ksi send deprecation:mark \
  --component "components/agents/dsl_interpreter_v2" \
  --reason "obsolete_concept" \
  --immediate true
```

### 2. Replaced Components
**Components**: Old optimization agents, legacy personas
**Reason**: Better alternatives exist
**Action**: Standard 90-day deprecation
```bash
# Mark as replaced
ksi send deprecation:mark \
  --component "components/agents/old_optimizer" \
  --reason "replaced" \
  --replacement "components/workflows/optimization_flow"
```

### 3. Failed Certification
**Components**: Consistently failing certification
**Reason**: Quality below standards
**Action**: 60-day grace period for fixes
```bash
# Mark as uncertifiable
ksi send deprecation:mark \
  --component "components/broken/bad_component" \
  --reason "certification_failed" \
  --attempts 3
```

### 4. Experimental/Test
**Components**: Test code, experiments
**Reason**: Never intended for production
**Action**: Immediate archive
```bash
# Archive experimental
ksi send deprecation:archive \
  --pattern "components/experimental/*" \
  --reason "experimental_code"
```

## Migration Support

### Automated Migration
```yaml
# Migration configuration
migration:
  from: "components/old/deprecated_component"
  to: "components/new/modern_component"
  automated: true
  transformations:
    - rename_field: {old: "prompt", new: "instruction"}
    - update_dependency: {old: "old_dep", new: "new_dep"}
    - adjust_capability: {remove: ["old_cap"], add: ["new_cap"]}
```

### Migration Tools
```bash
# Check migration feasibility
ksi send migration:analyze \
  --from "old_component" \
  --to "new_component"

# Perform automated migration
ksi send migration:execute \
  --from "old_component" \
  --to "new_component" \
  --dry_run false

# Validate migration
ksi send migration:validate \
  --component "new_component"
```

## Communication Strategy

### Deprecation Notices

#### In-Component Notice
```markdown
> ⚠️ **DEPRECATION WARNING**
> 
> This component is deprecated as of 2025-01-28.
> It will be removed on 2025-04-28.
> 
> **Replacement**: `components/modern/alternative`
> **Migration Guide**: [Link to guide]
> **Reason**: Obsolete pattern - modern alternative available
```

#### Log Messages
```
WARNING: Component 'old_component' is deprecated and will be removed on 2025-04-28.
Please migrate to 'new_component'. See migration guide: /docs/migrations/guide.md
```

#### Email Notifications
- Week 1: Initial deprecation notice
- Week 4: Reminder with migration guide
- Week 8: Final warning
- Week 12: Removal notice

## Immediate Deprecation List

### Category: Obsolete Concepts
1. `components/agents/dsl_interpreter_basic.md`
2. `components/agents/dsl_interpreter_v2.md`
3. `components/behaviors/dsl/*`
4. Any component with "dsl_execution" in name

### Category: Failed Architecture
1. `components/agents/event_emitting_optimizer.md`
2. `components/agents/dspy_optimization_agent.md`
3. Components attempting direct JSON emission without tool_use

### Category: Experimental
1. Everything in `components/experimental/`
2. Everything in `components/_archive/`
3. Everything in `components/test/` (except validated tests)

### Category: Duplicates
1. Multiple "data_analyst" variants (keep best one)
2. Multiple "coordinator" components (consolidate)
3. Redundant "hello_agent" examples

## Deprecation Workflow Automation

### Transformer Configuration
```yaml
# deprecation_workflow.yaml
name: deprecation_workflow
triggers:
  - event: certification:failed
    condition: attempts >= 3
  - event: deprecation:request
  - event: component:obsolete

actions:
  mark_deprecated:
    - update_frontmatter: add_deprecation_metadata
    - create_issue: deprecation_tracking
    - notify_users: email_and_logs
    - create_migration_guide: if_replacement_exists

  enforce_deprecation:
    - phase_1: log_warnings
    - phase_2: block_production
    - phase_3: move_to_archive
    - phase_4: delete_component
```

## Success Metrics

### Deprecation KPIs
- **Response Time**: < 24 hours from trigger to marking
- **Migration Success**: > 90% automated migration
- **User Disruption**: < 5% failed deployments
- **Cleanup Rate**: 100% removal by deadline

### Monthly Targets
- **Month 1**: 50+ components deprecated
- **Month 2**: 100+ components migrated
- **Month 3**: 150+ components removed
- **Month 4**: 0 deprecated components in production

## Appeals Process

### Requesting Extension
```bash
ksi send deprecation:appeal \
  --component "important_component" \
  --reason "Critical production dependency" \
  --extension_days 30
```

### Criteria for Extension
- Critical production dependency
- Migration complexity > 1 week
- No suitable replacement exists
- Active development to fix issues

## Archive Strategy

### Archive Structure
```
components/_archive/
├── 2025Q1/
│   ├── deprecated_concepts/
│   ├── failed_certification/
│   └── replaced_components/
├── 2025Q2/
└── README.md  # Index and history
```

### Archive Metadata
```yaml
# Archive entry
archived:
  component: "old_component"
  date: "2025-04-28"
  reason: "obsolete_concept"
  final_score: 0.45
  usage_count: 12
  dependent_components: ["comp1", "comp2"]
  migration_success_rate: 0.92
```

## Quick Reference

### Commands
```bash
# Mark for deprecation
ksi send deprecation:mark --component "path/to/component"

# Check deprecation status
ksi send deprecation:status --component "path/to/component"

# List all deprecated
ksi send deprecation:list --status "deprecated"

# Migrate component
ksi send migration:execute --from "old" --to "new"

# Appeal deprecation
ksi send deprecation:appeal --component "path" --reason "..."
```

### Timeline
- **Day 0**: Component marked for deprecation
- **Day 30**: Warning phase ends, deprecated phase begins
- **Day 60**: Grace period ends, enforcement begins
- **Day 90**: Component archived
- **Day 120**: Component deleted

---

*Component Deprecation Process v1.0.0 - Maintaining Quality Through Lifecycle Management*