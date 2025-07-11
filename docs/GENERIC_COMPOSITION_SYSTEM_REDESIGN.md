# Generic Composition System Redesign

**Status**: Planning  
**Priority**: High  
**Affects**: Composition System, Transformer Service, Orchestration Service, Future Pattern Types

---

## Overview

Transform the composition system from a type-aware filter to a generic pattern storage service that preserves all sections while maintaining basic structural validation.

## Problem Statement

### Current Issues
- Composition system strips custom sections (`transformers`, `agents`, `routing`, etc.)
- Only returns standard composition metadata fields (`name`, `type`, `version`, etc.)
- Consuming services cannot access their required sections
- Not extensible for new pattern types without modifying composition system
- Creates tight coupling between pattern storage and pattern processing

### Impact
- Transformer service cannot load transformers from patterns
- Orchestration service missing agents/routing configuration
- Future services (evaluation, workflows) will face same limitations
- Architecture violates separation of concerns principle

## Proposed Solution

**Generic preservation with layered validation:**
1. **Composition System**: Basic structural validation + preserve ALL sections
2. **Consuming Services**: Business logic validation for their specific sections

### Core Philosophy
- **Composition System** = Generic YAML storage and retrieval
- **Consuming Services** = Business logic validation and processing
- **Clear separation** between storage and processing concerns

## Validation Boundaries

### ✅ What Composition System SHOULD Validate

#### Core Structure (Universal)
- **YAML Syntax**: Valid YAML parsing (already implemented)
- **Top-level Structure**: Must be a dictionary/object
- **Required Fields**: Presence and basic type checking
  - `name`: string, required, alphanumeric + underscores/hyphens only
  - `type`: string, required (orchestration, prompt, profile, evaluation, etc.)
  - `version`: string, optional, semver format validation if present
  - `description`: string, optional
  - `author`: string, optional

#### Basic Safety
- **Security**: No dangerous YAML constructs (no arbitrary code execution)
- **Resource Limits**: Reasonable file size limits (prevent abuse)
- **Name Validation**: Pattern names follow naming conventions
- **Type Registry**: Valid pattern types from known registry

### ❌ What Composition System SHOULD NOT Validate

#### Business Logic (Service-Specific)
- **Transformer Content**: Structure/validity of `transformers` section → Transformer Service
- **Orchestration Content**: Structure/validity of `agents`/`routing` sections → Orchestration Service
- **Evaluation Content**: Structure/validity of evaluation-specific sections → Evaluation Service
- **Cross-References**: Links between sections → Consuming Services
- **Semantic Validation**: Pattern-specific business rules → Pattern-aware services

#### Future Extensibility
- **Unknown Sections**: Preserve any sections not in core schema
- **New Pattern Types**: Support new types without code changes
- **Custom Validation**: Service-specific validation rules
- **Experimental Features**: Allow innovation without central approval

## Implementation Plan

### Phase 1: Update Composition System Core
**Files**: `ksi_daemon/composition/composition_service.py`

#### 1.1 Modify Response Format
```python
# Current (filtered response):
{
  "name": "pattern_name",
  "type": "orchestration", 
  "version": "1.0.0",
  "metadata": {...}
}

# New (raw + validated response):
{
  "name": "pattern_name",
  "type": "orchestration",
  "version": "1.0.0", 
  "description": "...",
  "author": "...",
  "transformers": [...],        # Preserved!
  "agents": {...},             # Preserved!
  "routing": {...},            # Preserved!
  "coordination": {...},       # Preserved!
  "custom_evaluation": {...},  # Preserved!
  "future_workflow": {...}     # Preserved!
}
```

#### 1.2 Update `handle_get()` Function
- Load raw YAML content
- Validate core fields only
- Return complete YAML structure
- Preserve all unknown sections

#### 1.3 Update Validation Logic
```python
def validate_core_composition(data: Dict[str, Any]) -> List[str]:
    """Validate only core composition fields."""
    errors = []
    
    # Required fields
    if not isinstance(data.get('name'), str):
        errors.append("'name' must be a string")
    if not isinstance(data.get('type'), str):  
        errors.append("'type' must be a string")
    
    # Optional fields with type checking
    if 'version' in data and not isinstance(data['version'], str):
        errors.append("'version' must be a string")
    
    # Name format validation
    name = data.get('name', '')
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        errors.append("'name' must contain only alphanumeric, underscore, and hyphen characters")
    
    return errors
```

### Phase 2: Update Consuming Services

#### 2.1 Transformer Service
**File**: `ksi_daemon/transformer/transformer_service.py`

- Update `_load_pattern_file()` to expect `transformers` section in response
- Add validation for transformer-specific structure
- Handle missing `transformers` section gracefully

```python
async def _load_pattern_file(self, pattern_name: str) -> Dict[str, Any]:
    """Load pattern file via composition system."""
    router = self._get_router()
    result = await router.emit("composition:get", {
        "name": pattern_name, 
        "type": "orchestration"
    })
    
    if result and isinstance(result, list) and result:
        pattern_data = result[0]
        if isinstance(pattern_data, dict) and 'error' not in pattern_data:
            # Now pattern_data includes transformers section!
            return pattern_data
    
    raise FileNotFoundError(f"Pattern not found: {pattern_name}")
```

#### 2.2 Orchestration Service  
**File**: `ksi_daemon/orchestration/orchestration_service.py`

- Update `load_pattern()` to expect `agents`/`routing` sections
- Remove direct file access fallback
- Add orchestration-specific validation

### Phase 3: Service-Specific Validation Framework

#### 3.1 Validation Utilities
**New File**: `ksi_common/validation_utils.py`

```python
class PatternValidator:
    """Base class for pattern section validation."""
    
    def validate_section(self, section_name: str, data: Any) -> List[str]:
        """Override in subclasses for specific validation."""
        return []

class TransformerValidator(PatternValidator):
    """Validates transformer sections."""
    
    def validate_section(self, section_name: str, transformers: List[Dict]) -> List[str]:
        errors = []
        for i, transformer in enumerate(transformers):
            if 'source' not in transformer:
                errors.append(f"Transformer {i}: missing 'source' field")
            if 'target' not in transformer:
                errors.append(f"Transformer {i}: missing 'target' field")
        return errors
```

#### 3.2 Integration in Services
```python
# In transformer service
from ksi_common.validation_utils import TransformerValidator

validator = TransformerValidator()
errors = validator.validate_section('transformers', transformers_data)
if errors:
    logger.error(f"Invalid transformers in pattern {pattern_name}: {errors}")
```

### Phase 4: Testing & Rollout

#### 4.1 End-to-End Testing
- Test transformer loading with new flow
- Test orchestration pattern loading
- Test backward compatibility with existing patterns
- Test error handling for malformed patterns

#### 4.2 Performance Testing
- Measure impact of returning full pattern data
- Ensure no degradation in pattern loading times
- Test with large patterns containing many sections

#### 4.3 Documentation Updates
- Update composition system documentation
- Update service integration guides  
- Create migration guide for new pattern types

## Benefits

### 🎯 Clean Architecture
- **Single Responsibility**: Composition system focused on storage/retrieval
- **Separation of Concerns**: Services validate what they process
- **Loose Coupling**: No service-specific logic in composition system

### 🚀 Extensibility
- **New Pattern Types**: Zero changes required to composition system
- **Custom Sections**: Services can define any sections they need
- **Future-Proof**: Unknown sections automatically preserved
- **Innovation**: Teams can experiment without central coordination

### 🔧 Maintainability  
- **Validation Co-location**: Logic lives where it's used
- **Simpler Composition Logic**: No complex type-aware filtering
- **Service Ownership**: Each service owns its validation rules
- **Easier Testing**: Smaller, focused validation functions

### 🎨 Flexibility
- **Multi-Service Patterns**: Services can share pattern sections
- **Gradual Migration**: Services can add validation over time
- **Custom Use Cases**: Patterns can include experimental sections
- **Development Workflow**: Easier to iterate on pattern formats

## Risk Mitigation

### Security Considerations
- **YAML Safety**: Basic YAML safety checks remain in place
- **Resource Limits**: File size and complexity limits prevent abuse
- **Validation Depth**: Services still validate their critical sections
- **Schema Evolution**: Can add stricter validation later if needed

### Backward Compatibility
- **Response Format**: All existing fields remain in response
- **API Stability**: No breaking changes to composition events
- **Migration Path**: Existing patterns continue to work unchanged
- **Gradual Rollout**: Can implement service-by-service

### Performance Impact
- **Parsing Overhead**: Minimal - just returning more data
- **Memory Usage**: Slight increase from larger response objects
- **Network**: Local unix socket communication, negligible impact
- **Caching**: Response caching can mitigate any repeated access costs

### Error Handling
- **Validation Errors**: Clear attribution to specific services
- **Partial Failures**: Services can function with missing optional sections
- **Debugging**: Better error messages with section context
- **Monitoring**: Can track validation failures per service

## Success Metrics

### Functional Goals
- ✅ Transformer service can load transformers from patterns
- ✅ Orchestration service can load full pattern configuration
- ✅ New pattern types can be added without composition system changes
- ✅ All existing functionality continues to work

### Quality Goals
- ✅ No performance degradation in pattern loading
- ✅ Clear error messages for validation failures
- ✅ Services can validate independently
- ✅ Zero breaking changes to existing APIs

### Future Goals
- ✅ Evaluation patterns with custom sections work seamlessly
- ✅ Agent workflow patterns can be added easily
- ✅ Custom pattern types by third parties possible
- ✅ Pattern innovation happens at service level

## Implementation Order

1. **Phase 1**: Update composition system (1-2 days)
2. **Phase 2**: Update transformer service (1 day)  
3. **Phase 2**: Update orchestration service (1 day)
4. **Phase 3**: Add validation framework (1-2 days)
5. **Phase 4**: Testing and documentation (1-2 days)

**Total Estimated Time**: 5-8 days

**Dependencies**: None - this is backward compatible

**Risks**: Low - additive changes only, extensive testing planned

---

## Related Documentation

- [Intelligent Orchestration Patterns](INTELLIGENT_ORCHESTRATION_PATTERNS.md)
- [Transformer Service Architecture](../ksi_daemon/transformer/README.md) *(to be created)*
- [Composition System](../ksi_daemon/composition/README.md)
- [Pattern Development Guide](PATTERN_DEVELOPMENT_GUIDE.md) *(to be created)*

---

*This document will be updated as implementation progresses and learnings emerge.*