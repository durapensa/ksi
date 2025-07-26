# Distributed Component Evaluation Metadata System

## Overview

This document describes KSI's distributed metadata tracking system for component evaluation and testing. The system scales from single-instance usage to community sharing via git, and eventually to peer-to-peer mesh networks.

## Problem Statement

Currently, component evaluation metadata is either:
- Embedded in components (too bulky, hard to query)
- Lost when components are updated
- Not discoverable across development sessions
- Not shareable between KSI instances

This leads to:
- Rediscovering/retesting already-validated components
- Uncertainty about component compatibility with different models
- Difficulty sharing trusted components with the community
- No standardized way to track testing coverage

## Design Principles

### 1. Content-Addressable Components
Every component version gets a unique SHA-256 hash based on its content. This enables:
- Immutable evaluation tracking
- Version-specific test results
- Deduplication across instances

### 2. Cryptographically Signed Evaluations
Test results are packaged as signed certificates containing:
- Component hash
- Test environment details
- Performance metrics
- Evaluator identity and reputation

### 3. Progressive Enhancement
The system works in three phases:
- **Phase 1**: Local registry + Git sharing (immediate implementation)
- **Phase 2**: Event-based federation between instances
- **Phase 3**: Full P2P mesh network with DHT discovery

## Phase 1: Local + Git Implementation

### Directory Structure
```
var/lib/evaluations/
├── registry.yaml           # Local component evaluation index
├── certificates/          # Individual evaluation certificates
│   ├── 2025-07-26/
│   │   ├── dsl_optimization_executor_3b4c5d6e.yaml
│   │   └── claude_code_override_7f8a9b0c.yaml
│   └── latest/           # Symlinks to most recent evaluations
└── reports/              # Detailed test reports
    └── 2025-07-26/
        └── test_session_abc123/
```

### Registry Format
```yaml
# var/lib/evaluations/registry.yaml
registry_version: "1.0.0"
last_updated: "2025-07-26T14:42:00Z"
instance:
  id: "ksi_instance_dp_projects_abc123"
  name: "dp's development instance"

components:
  "sha256:3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c":
    path: "components/agents/dsl_optimization_executor"
    version: "1.1.0"
    evaluations:
      - certificate_id: "eval_2025_07_26_3b4c5d6e"
        date: "2025-07-26"
        model: "claude-sonnet-4-20250514"
        status: "passing"
        tests_passed: 3
        tests_total: 3
        performance_class: "standard"  # fast|standard|slow
```

### Evaluation Certificate Format
```yaml
# var/lib/evaluations/certificates/2025-07-26/dsl_optimization_executor_3b4c5d6e.yaml
certificate:
  id: "eval_2025_07_26_3b4c5d6e"
  version: "1.0"
  
component:
  hash: "sha256:3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c"
  path: "components/agents/dsl_optimization_executor"
  version: "1.1.0"
  type: "agent"

evaluator:
  instance_id: "ksi_instance_dp_projects_abc123"
  tester: "claude_code"
  
environment:
  model: "claude-sonnet-4-20250514"
  model_version_date: "2025-05-14"
  ksi_version: "2.0.0"
  ksi_commit: "abc123def456"
  test_framework: "ksi_component_test_v1"
  python_version: "3.11.5"
  
results:
  status: "passing"  # passing|failing|partial|error
  tests:
    basic_emission:
      status: "pass"
      duration_ms: 4500
      events_captured: ["agent:progress"]
    optimization_events:
      status: "pass"
      duration_ms: 11000
      events_captured: ["optimization:async"]
    sequential_dsl:
      status: "pass"
      duration_ms: 13000
      events_captured: ["agent:status", "agent:progress"]
      
  performance_profile:
    response_time_p50: 8000  # milliseconds
    response_time_p95: 13000
    memory_usage_mb: 45
    
  dependencies_verified:
    - "behaviors/dsl/dsl_execution_override"
    - "behaviors/communication/mandatory_json"
    
  capabilities_required:
    - "self_improver"  # Security profile needed
    
  notes:
    - "Requires 12+ second wait times for complex requests"
    - "Successfully prevents tool-asking behavior"
    
metadata:
  created_at: "2025-07-26T14:42:00Z"
  expires_at: "2026-07-26T14:42:00Z"
  test_session_id: "test_session_abc123"
  detailed_report: "reports/2025-07-26/test_session_abc123/"
```

### Git Integration

#### In `.gitignore`
```
# Don't commit local instance data
var/lib/evaluations/registry.yaml
var/lib/evaluations/reports/

# DO commit certificates for sharing
!var/lib/evaluations/certificates/
```

#### Workflow
```bash
# 1. Test component locally
ksi test component --name "dsl_optimization_executor"

# 2. Certificate auto-generated in var/lib/evaluations/certificates/

# 3. Commit certificate to compositions repo
cd var/lib/compositions
git add .evaluations/certificates/
git commit -m "Add evaluation certificate for dsl_optimization_executor v1.1.0

Tested with claude-sonnet-4-20250514
- All 3 tests passing
- Performance: 8-12s for optimization events
- Requires self_improver security profile"

# 4. Push to share with community
git push origin main
```

## SQLite Integration with Composition Discovery

### Architecture Overview

The evaluation system integrates with KSI's composition discovery through SQLite indexing, following the same pattern as the composition index:

- **YAML certificates**: Single source of truth (git-shareable)
- **SQLite database**: Fast query index/cache
- **Automatic sync**: Index rebuilds from certificates during `composition:rebuild_index`

### Database Schema

```sql
-- New table for evaluation data index
CREATE TABLE IF NOT EXISTS evaluation_index (
    component_hash TEXT PRIMARY KEY,
    component_path TEXT NOT NULL,
    component_type TEXT,
    component_version TEXT,
    latest_evaluation_date TEXT,
    latest_status TEXT,
    performance_class TEXT,
    models_tested TEXT,  -- JSON array of models
    evaluation_summary TEXT,  -- JSON object with counts/stats
    certificates TEXT,  -- JSON array of certificate metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_eval_component_path ON evaluation_index(component_path);
CREATE INDEX idx_eval_status ON evaluation_index(latest_status);
CREATE INDEX idx_eval_models ON evaluation_index(models_tested);

-- Update composition_index to include evaluation reference
ALTER TABLE composition_index ADD COLUMN has_evaluations BOOLEAN DEFAULT FALSE;
ALTER TABLE composition_index ADD COLUMN evaluation_summary TEXT;  -- JSON summary
```

### Integration with composition:discover

```python
# Enhanced discovery with evaluation data
class CompositionDiscoverData(TypedDict):
    # Existing fields...
    type: NotRequired[str]
    name_pattern: NotRequired[str]
    
    # New evaluation filters
    min_evaluation_score: NotRequired[float]
    tested_on_model: NotRequired[str]
    evaluation_status: NotRequired[str]  # passing|failing|partial
    min_performance_class: NotRequired[str]  # fast|standard|slow
    
    # Control evaluation data inclusion
    include_evaluation: NotRequired[bool]  # Default: True (basic data)
    evaluation_detail: NotRequired[str]  # minimal|summary|detailed
```

### Default Behavior

When using `composition:discover`, basic evaluation data is included by default:

```python
# Default response includes basic evaluation info
{
  "name": "components/agents/dsl_optimization_executor",
  "type": "agent",
  "version": "1.1.0",
  "evaluation": {
    "tested": true,
    "latest_status": "passing",
    "models": ["claude-sonnet-4-20250514"],
    "performance_class": "standard"
  }
}

# Request detailed evaluation data
ksi send composition:discover --type agent \
  --evaluation_detail detailed \
  --tested_on_model "claude-sonnet-4"
```

### Index Rebuild Process

During `composition:rebuild_index`, the system:

1. **Scans certificate directories**: `var/lib/evaluations/certificates/`
2. **Parses YAML certificates**: Extracts metadata
3. **Hashes components**: Matches certificates to components
4. **Updates SQLite index**: Populates evaluation_index table
5. **Links to compositions**: Updates composition_index evaluation fields

### Query Examples

```sql
-- Find all components tested on claude-sonnet-4
SELECT c.name, c.version, e.latest_status, e.performance_class
FROM composition_index c
JOIN evaluation_index e ON c.file_hash = e.component_hash
WHERE json_extract(e.models_tested, '$') LIKE '%claude-sonnet-4%'
AND e.latest_status = 'passing';

-- Find high-performance behavioral components
SELECT c.name, e.evaluation_summary
FROM composition_index c
JOIN evaluation_index e ON c.file_hash = e.component_hash
WHERE c.type = 'behavior'
AND e.performance_class = 'fast'
ORDER BY json_extract(e.evaluation_summary, '$.avg_score') DESC;
```

### Benefits of This Architecture

1. **Single Source of Truth**: YAML certificates remain authoritative
2. **Fast Queries**: SQL performance for discovery operations
3. **Git-Friendly**: Certificates shareable through version control
4. **Backward Compatible**: Existing discovery API unchanged
5. **Incremental Updates**: Can update index without full rebuild

## Phase 2: Event-Based Federation (Future)

### Discovery Events
```python
# Share evaluation with peers
{
  "event": "evaluation:publish",
  "data": {
    "certificate_path": "certificates/2025-07-26/dsl_optimization_executor.yaml",
    "targets": ["peer_instance_1", "peer_instance_2"]
  }
}

# Query for evaluations
{
  "event": "evaluation:search", 
  "data": {
    "component_path": "components/agents/dsl_optimization_executor",
    "models": ["claude-sonnet-4"],
    "min_date": "2025-01-01"
  }
}
```

### Trust Network
```yaml
# var/lib/evaluations/trust_network.yaml
peers:
  "ksi_instance_community_1":
    public_key: "ed25519:..."
    reputation: 0.85
    last_seen: "2025-07-26T10:00:00Z"
    specialties: ["optimization", "dsl"]
```

## Phase 3: P2P Mesh Network (Future)

### Distributed Hash Table (DHT)
- Component hashes as keys
- Evaluation certificates as values
- Automatic replication based on popularity

### Consensus Mechanisms
- Multiple evaluations increase confidence
- Weighted voting based on reputation
- Dispute resolution through re-testing

## Implementation Utilities

### Component Hashing
```python
def hash_component(component_path):
    """Generate stable hash for component content."""
    with open(component_path, 'rb') as f:
        content = f.read()
    # Normalize line endings
    content = content.replace(b'\r\n', b'\n')
    return hashlib.sha256(content).hexdigest()
```

### Certificate Generation
```python
async def generate_evaluation_certificate(
    component_path, 
    test_results,
    environment_info
):
    """Create evaluation certificate from test results."""
    certificate = {
        "certificate": {
            "id": f"eval_{datetime.now():%Y_%m_%d}_{hash[:8]}",
            "version": "1.0"
        },
        "component": {
            "hash": hash_component(component_path),
            "path": component_path,
            "version": extract_version(component_path)
        },
        "environment": environment_info,
        "results": test_results,
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat()
        }
    }
    return certificate
```

### Discovery Queries
```bash
# Find all passing components for a model
ksi send evaluation:list --model "claude-sonnet-4" --status "passing"

# Get evaluation history for a component
ksi send evaluation:history --component "dsl_optimization_executor"

# Verify certificate authenticity (Phase 2+)
ksi send evaluation:verify --certificate "eval_2025_07_26_3b4c5d6e"
```

## Current Implementation Status (Phase 1 Complete)

### What's Working Now
- **Certificate Generation**: `python ksi_evaluation/generate_certificate.py`
- **Registry Management**: `python ksi_evaluation/registry_manager.py scan`
- **Discovery Integration**: `ksi send composition:discover --tested_on_model "claude-sonnet-4"`
- **SQLite Indexing**: Automatic during `composition:rebuild_index`
- **Agent Events**: `evaluation:run`, `evaluation:query`, `evaluation:get_certificate`

### Quick Start
```bash
# Test a component and generate certificate
python test_dsl_executor_incremental.py
python ksi_evaluation/generate_certificate.py

# Update registry and discover validated components
python ksi_evaluation/registry_manager.py scan
python ksi_evaluation/discover_validated.py dsl

# Use in KSI discovery
ksi send composition:discover --type agent --evaluation_status passing
```

## Future Phases

### Phase 2: Cryptographic Trust (3-6 months)
- Ed25519 signatures on certificates
- Instance identity and reputation
- Event-based certificate sharing
- Trust network establishment

### Phase 3: P2P Mesh (6-12 months)
- DHT for certificate discovery
- Gossip protocol propagation
- Consensus for disputed evaluations
- Economic incentives for testing

## Conclusion

This distributed evaluation system solves immediate discovery problems while laying groundwork for a decentralized component ecosystem. Starting with simple file-based tracking and git sharing, it can evolve into a sophisticated P2P network as the KSI community grows.

The key insight is treating evaluation metadata as **portable proof of quality** that travels with components, building a web of trust without central authorities.