# Git Submodule Component Architecture for KSI

## Overview

This document outlines the architecture and implementation plan for converting KSI's `var/lib/` components into git submodules, enabling federated sharing of compositions, evaluations, and capabilities across KSI instances and beyond.

## Current State Analysis

### Existing Components in var/lib/
```
var/lib/
├── compositions/           # 250+ files, 2.8MB
│   ├── profiles/          # Agent profiles and fragments
│   ├── orchestrations/    # Orchestration patterns
│   ├── prompts/          # Prompt library
│   └── fragments/        # Reusable components
├── evaluations/           # 50+ files, 1.2MB
│   ├── test_suites/      # Evaluation test definitions
│   └── results/          # Evaluation results and metrics
└── capabilities/          # 20+ files, 400KB
    ├── ksi_capabilities.yaml
    ├── capability_mappings.yaml
    └── schemas/
```

### Current Git Status
- **Already git-tracked**: All components are currently tracked in main KSI repository
- **YAML/JSON format**: Human-readable, git-friendly formats
- **Reference-based**: Event system references by name, not content
- **Modular design**: Components are already designed for reusability

## Target Architecture

### Git Submodule Structure
```
var/lib/
├── compositions/          # Git submodule -> ksi-compositions
├── evaluations/          # Git submodule -> ksi-evaluations  
├── capabilities/         # Git submodule -> ksi-capabilities
└── .gitmodules           # Submodule configuration
```

### Repository Organization
```
Main KSI Repository
├── ksi_daemon/
├── ksi_common/
├── var/lib/              # Contains submodules
│   ├── compositions/     # -> github.com/durapensa/ksi-compositions
│   ├── evaluations/      # -> github.com/durapensa/ksi-evaluations
│   └── capabilities/     # -> github.com/durapensa/ksi-capabilities
└── docs/
```

## Component Repository Design

### Individual Repository Structure

#### ksi-compositions Repository
```
ksi-compositions/
├── README.md             # Usage, contribution guidelines
├── profiles/
│   ├── base/            # Foundation profiles
│   ├── agents/          # Specialized agent profiles
│   └── fragments/       # Reusable profile components
├── orchestrations/       # Orchestration patterns
├── prompts/             # Prompt library
├── fragments/           # Cross-cutting components
├── schemas/             # Validation schemas
├── .github/
│   └── workflows/       # CI/CD for validation
└── examples/            # Usage examples
```

#### ksi-evaluations Repository
```
ksi-evaluations/
├── README.md
├── test_suites/         # Evaluation definitions
├── results/             # Evaluation results (may be gitignored)
├── judges/              # Judge configurations
├── schemas/             # Validation schemas
└── .github/
    └── workflows/       # CI/CD for evaluation runs
```

#### ksi-capabilities Repository
```
ksi-capabilities/
├── README.md
├── ksi_capabilities.yaml
├── capability_mappings.yaml
├── schemas/             # Capability schemas
├── plugins/             # Plugin definitions
└── .github/
    └── workflows/       # CI/CD for capability validation
```

## Federation and Sharing Strategy

### Standalone Repository Features

#### Universal Compatibility
- **Framework-agnostic**: Can be used by any system, not just KSI
- **Standard formats**: YAML/JSON with clear schemas
- **Documentation**: Comprehensive READMEs and examples
- **Validation**: CI/CD pipelines for quality assurance

#### Federated Sharing
- **Multiple origins**: Different KSI instances can contribute
- **Selective inclusion**: Choose which components to include
- **Version pinning**: Lock to specific versions for stability
- **Conflict resolution**: Git merge strategies for collaboration

#### Community Ecosystem
- **Public repositories**: Open source contributions welcome
- **Private forks**: Organizations can maintain private variants
- **Contribution guidelines**: Clear processes for community input
- **Issue tracking**: Bug reports and feature requests

## Implementation Plan

### Phase 1: Repository Setup (Week 1)
1. **Create separate repositories**
   - Initialize ksi-compositions repository
   - Initialize ksi-evaluations repository  
   - Initialize ksi-capabilities repository
   - Set up GitHub organizations/teams

2. **Migrate existing content**
   - Extract var/lib/compositions/ to ksi-compositions
   - Extract var/lib/evaluations/ to ksi-evaluations
   - Extract var/lib/capabilities/ to ksi-capabilities
   - Preserve git history using `git subtree`

3. **Configure submodules**
   - Add submodules to main KSI repository
   - Update .gitmodules configuration
   - Test submodule initialization and updates

### Phase 2: Component Management Integration (Week 2)
1. **Enhance composition service**
   - Add git operations to composition_service.py
   - Implement component save with git commit
   - Add component fork functionality
   - Support component branch management

2. **Update event handlers**
   - Modify composition:save to commit changes
   - Add composition:fork for branching
   - Implement composition:merge for collaboration
   - Add composition:sync for submodule updates

3. **Git integration utilities**
   - Create ksi_common/git_utils.py
   - Add commit, branch, merge operations
   - Implement conflict resolution helpers
   - Add submodule management functions

### Phase 3: Federation Support (Week 3)
1. **Remote repository support**
   - Add configuration for remote repositories
   - Implement repository discovery
   - Support multiple composition sources
   - Add authentication for private repositories

2. **Synchronization mechanisms**
   - Implement pull/push for submodules
   - Add selective component synchronization
   - Support version pinning and updates
   - Add conflict detection and resolution

3. **CLI and API enhancements**
   - Add ksi CLI commands for component management
   - Implement repository configuration
   - Add federation status reporting
   - Support component marketplace discovery

### Phase 4: Advanced Features (Week 4)
1. **Version management**
   - Implement semantic versioning for components
   - Add compatibility checking
   - Support component dependency resolution
   - Add deprecation and migration support

2. **Collaboration features**
   - Implement component review workflows
   - Add collaborative editing support
   - Support team-based component development
   - Add contribution tracking and attribution

3. **Performance optimizations**
   - Implement lazy loading for large repositories
   - Add component caching strategies
   - Optimize git operations for large repositories
   - Add parallel component operations

## Technical Implementation Details

### Git Operations Integration

#### Component Save Operation
```python
async def save_component(component_type: str, name: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """Save component with git commit."""
    repo_path = config.get_component_repo_path(component_type)
    
    # Write component file
    component_path = repo_path / f"{name}.yaml"
    with open(component_path, 'w') as f:
        yaml.dump(content, f)
    
    # Git operations
    repo = pygit2.Repository(repo_path)
    repo.index.add(str(component_path))
    
    # Create commit
    commit_hash = repo.create_commit(
        'HEAD',
        signature,
        signature,
        f"Update {component_type}: {name}",
        repo.index.write_tree(),
        [repo.head.target]
    )
    
    return {
        "status": "saved",
        "commit": commit_hash,
        "path": str(component_path)
    }
```

#### Component Fork Operation
```python
async def fork_component(component_type: str, source_name: str, target_name: str) -> Dict[str, Any]:
    """Fork component to new name with git branch."""
    repo_path = config.get_component_repo_path(component_type)
    repo = pygit2.Repository(repo_path)
    
    # Create branch for fork
    branch_name = f"fork/{target_name}"
    repo.branches.local.create(branch_name, repo.head.target)
    
    # Copy component file
    source_path = repo_path / f"{source_name}.yaml"
    target_path = repo_path / f"{target_name}.yaml"
    
    shutil.copy2(source_path, target_path)
    
    # Commit fork
    repo.index.add(str(target_path))
    commit_hash = repo.create_commit(
        f"refs/heads/{branch_name}",
        signature,
        signature,
        f"Fork {component_type}: {source_name} -> {target_name}",
        repo.index.write_tree(),
        [repo.head.target]
    )
    
    return {
        "status": "forked",
        "branch": branch_name,
        "commit": commit_hash
    }
```

### Event System Integration

#### New Event Handlers
```python
@event_handler("composition:save")
async def handle_composition_save(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save composition with git commit."""
    component_type = data["type"]  # profiles, orchestrations, prompts
    name = data["name"]
    content = data["content"]
    
    return await save_component(component_type, name, content)

@event_handler("composition:fork")
async def handle_composition_fork(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fork composition to new name."""
    component_type = data["type"]
    source_name = data["source_name"]
    target_name = data["target_name"]
    
    return await fork_component(component_type, source_name, target_name)

@event_handler("composition:sync")
async def handle_composition_sync(data: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronize submodules with remote repositories."""
    component_type = data.get("type")  # Optional: sync specific component
    
    return await sync_submodules(component_type)
```

### Configuration Management

#### Submodule Configuration
```yaml
# ksi_common/config.yaml - new section
git_submodules:
  compositions:
    url: "https://github.com/ksi-project/ksi-compositions.git"
    branch: "main"
    path: "var/lib/compositions"
  evaluations:
    url: "https://github.com/ksi-project/ksi-evaluations.git"
    branch: "main"
    path: "var/lib/evaluations"
  capabilities:
    url: "https://github.com/ksi-project/ksi-capabilities.git"
    branch: "main"
    path: "var/lib/capabilities"

federation:
  enabled: true
  remote_repositories:
    - url: "https://github.com/community/ksi-compositions.git"
      type: "compositions"
      priority: 1
    - url: "https://github.com/enterprise/ksi-evaluations.git"
      type: "evaluations"
      priority: 2
```

## Migration Strategy

### Backward Compatibility
- **Gradual migration**: Phase migration over several releases
- **Fallback support**: Keep existing file-based loading during transition
- **Configuration flags**: Allow disabling git submodules during migration
- **Data preservation**: Ensure no data loss during migration

### Migration Steps
1. **Preparation**: Back up existing var/lib/ content
2. **Repository creation**: Set up separate repositories
3. **Content migration**: Move files preserving git history
4. **Submodule setup**: Configure submodules in main repository
5. **Service updates**: Update composition service for git operations
6. **Testing**: Comprehensive testing of git operations
7. **Deployment**: Gradual rollout with monitoring

## Benefits and Impact

### Development Benefits
- **Modularity**: Components can be developed independently
- **Collaboration**: Multiple teams can contribute to components
- **Reusability**: Components can be used beyond KSI
- **Version control**: Full git history for all components

### Operational Benefits
- **Federation**: Share components across KSI instances
- **Scalability**: Distribute component load across repositories
- **Reliability**: Git's distributed nature provides redundancy
- **Audit trail**: Complete history of component changes

### Community Benefits
- **Open source**: Public repositories enable community contributions
- **Standardization**: Common formats promote interoperability
- **Innovation**: Shared components accelerate development
- **Learning**: Examples and patterns benefit the community

## Risks and Mitigation

### Technical Risks
- **Complexity**: Git submodules add operational complexity
  - *Mitigation*: Comprehensive documentation and tooling
- **Performance**: Large repositories may slow operations
  - *Mitigation*: Lazy loading and caching strategies
- **Conflicts**: Merge conflicts in collaborative environments
  - *Mitigation*: Clear contribution guidelines and tooling

### Operational Risks
- **Repository unavailability**: Remote repositories may be down
  - *Mitigation*: Local caching and fallback mechanisms
- **Version incompatibilities**: Components may have breaking changes
  - *Mitigation*: Semantic versioning and compatibility checking
- **Security**: Untrusted repositories may contain malicious content
  - *Mitigation*: Validation pipelines and sandboxing

## Success Metrics

### Technical Metrics
- **Repository size**: Individual repositories under 10MB
- **Operation speed**: Component operations under 2s
- **Submodule sync time**: Full sync under 30s
- **Test coverage**: 90% coverage for git operations

### Usage Metrics
- **Community adoption**: 10+ external contributors in 6 months
- **Repository forks**: 5+ community forks per repository
- **Component reuse**: 50+ components shared across instances
- **Federation usage**: 3+ federated KSI instances

## Future Considerations

### Advanced Features
- **Component marketplace**: Centralized component discovery
- **Automated testing**: CI/CD for component validation
- **Performance optimization**: Advanced git operations
- **Security hardening**: Component signing and verification

### Ecosystem Integration
- **IDE plugins**: Support for component development
- **Package managers**: Integration with language package systems
- **Cloud platforms**: Native support for cloud git repositories
- **Monitoring**: Observability for component operations

## Conclusion

The git submodule architecture provides a solid foundation for federated KSI component sharing while maintaining backward compatibility and enabling community collaboration. The phased implementation plan ensures a smooth transition while delivering immediate value through improved modularity and version control.

This architecture positions KSI as a platform that can scale beyond individual instances to become a collaborative ecosystem for AI orchestration patterns, evaluation frameworks, and capability definitions.

---

*Next Steps: Review this plan and prioritize initial implementation phases based on current project needs and resource availability.*