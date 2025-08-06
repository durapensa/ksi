# KSI Evaluation System Migration Plan

## Overview
Migrate evaluation functionality from `ksi_evaluation/` to `ksi_daemon/evaluation/` while removing redundant code that was mistakenly moved to `ksi_common/`.

## Current State Analysis

### ksi_evaluation/ (To Be Migrated/Removed)
- `generate_certificate.py` - Certificate generation logic
- `hash_component.py` - Component hashing utility
- `registry_manager.py` - Registry YAML management
- `discover_validated.py` - Query validated components
- `create_behavioral_certificates.py` - Behavioral test certificates

### ksi_daemon/evaluation/ (Existing)
- `evaluation_events.py` - Event handlers for evaluation:run
- `certificate_index.py` - SQLite index for certificates
- `__init__.py` - Module initialization

### ksi_common/ (Mistakenly Added)
- `evaluation_utils.py` - Evaluation orchestration utilities (REMOVE after review)

## Migration Steps

### Step 1: Migrate Core Utilities
- [x] `hash_component.py` → `component_hasher.py` (DONE)
- [ ] `generate_certificate.py` → Integrate into `evaluation_events.py`
- [ ] `registry_manager.py` → Integrate with `certificate_index.py`

### Step 2: Update Event Handlers
- [ ] Add certificate generation to `handle_evaluation_run()`
- [ ] Add registry update logic to certificate creation flow
- [ ] Ensure backward compatibility with existing certificates

### Step 3: Remove Redundant Code
- [ ] Delete `ksi_common/evaluation_utils.py` (after verifying no dependencies)
- [ ] Remove `ksi_evaluation/` directory after migration complete
- [ ] Update any imports in other modules

### Step 4: Integration Points
- [ ] Update `evaluation:run` to generate certificates
- [ ] Ensure certificate index auto-updates on new certificates
- [ ] Maintain registry.yaml for backward compatibility

## Testing Requirements
1. Verify certificate generation works through event system
2. Test registry updates when certificates are created
3. Ensure composition:discover can query certified components
4. Validate behavioral override evaluation flow

## Behavioral Override Evaluation Integration
The migration should support the new behavioral override optimization workflow:
- Generate certificates for behavioral component tests
- Track JSON emission effectiveness metrics
- Support incremental composition testing
- Enable discovery of certified behavioral patterns