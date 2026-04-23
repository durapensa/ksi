# Production Deployment Guide for Optimized Components

## Overview

This guide provides the complete workflow for safely deploying optimized components to production in KSI. It covers validation, testing, rollback procedures, and monitoring.

## Pre-Deployment Checklist

### Component Requirements
- [ ] Component has been optimized using approved methods (DSPy/MIPRO, LLM-as-Judge, or Hybrid)
- [ ] All 5 quality dimensions meet minimum thresholds:
  - [ ] Instruction Following Fidelity (IFF) ≥ 0.85
  - [ ] Task Lock-in Persistence (TLP) ≥ 0.80
  - [ ] Agent Orchestration Capability (AOC) ≥ 0.70
  - [ ] Behavioral Consistency (BC) ≥ 0.85
  - [ ] Token Efficiency (TE) ≥ 0.15 improvement
- [ ] Component has valid evaluation certificate
- [ ] All dependencies have passing evaluations
- [ ] Rollback version identified and tested

### System Requirements
- [ ] Production environment prepared
- [ ] Monitoring systems operational
- [ ] Rollback procedures tested
- [ ] Team notified of deployment window

## Phase 1: Pre-Production Validation (1-2 hours)

### Step 1.1: Dependency Verification
```bash
# Check all dependencies have passing status
ksi send evaluation:validate_dependencies \
  --component "personas/analysts/data_analyst_v2_optimized"

# Expected output: All dependencies passing
```

### Step 1.2: Comprehensive Testing
```bash
# Run full test suite
ksi send evaluation:run \
  --component_path "components/personas/analysts/data_analyst_v2_optimized.md" \
  --test_suite "comprehensive_quality_suite" \
  --model "claude-sonnet-4"

# Verify all dimensions pass
ksi send evaluation:get_certificate \
  --component "data_analyst_v2_optimized" \
  --latest
```

### Step 1.3: A/B Comparison
```bash
# Compare with current production version
ksi send evaluation:compare \
  --baseline "personas/analysts/data_analyst" \
  --candidate "personas/analysts/data_analyst_v2_optimized" \
  --metrics "all_dimensions"
```

### Step 1.4: Edge Case Testing
```bash
# Test known edge cases
./test_edge_cases.sh data_analyst_v2_optimized

# Test failure scenarios
ksi send evaluation:run \
  --component "data_analyst_v2_optimized" \
  --test_suite "failure_recovery" \
  --expect_graceful_degradation
```

## Phase 2: Staged Deployment (2-3 hours)

### Step 2.1: Create Deployment Package
```bash
# Generate deployment manifest
cat > deployment_manifest.yaml << EOF
deployment:
  component: personas/analysts/data_analyst_v2_optimized
  version: 2.0.0
  replaces: personas/analysts/data_analyst
  rollback_to: personas/analysts/data_analyst_v1_backup
  
  quality_scores:
    iff: 0.92
    tlp: 0.88
    aoc: 0.75
    bc: 0.95
    te: 0.81
    overall: 0.862
  
  optimization_method: hybrid
  certificate_id: eval_2025_08_06_xyz123
  
  deployment_strategy: canary
  canary_percentage: 10
  success_criteria:
    error_rate: "< 0.01"
    latency_p95: "< 2s"
    quality_score: "> 0.85"
EOF
```

### Step 2.2: Backup Current Version
```bash
# Create timestamped backup
BACKUP_NAME="data_analyst_v1_backup_$(date +%Y%m%d_%H%M%S)"

ksi send composition:create_component \
  --name "personas/analysts/$BACKUP_NAME" \
  --copy_from "personas/analysts/data_analyst" \
  --metadata '{"deployment_status": "backup", "backed_up_at": "2025-08-06T19:00:00Z"}'

# Verify backup
ksi send composition:get_component --name "personas/analysts/$BACKUP_NAME"
```

### Step 2.3: Deploy to Canary (10% traffic)
```bash
# Deploy optimized version as canary
ksi send deployment:canary \
  --component "personas/analysts/data_analyst_v2_optimized" \
  --percentage 10 \
  --monitor_duration "30m"

# Monitor canary metrics
watch -n 10 'ksi send monitor:deployment_metrics \
  --component "data_analyst_v2_optimized" \
  --metrics "errors,latency,quality"'
```

### Step 2.4: Progressive Rollout
```bash
# If canary successful, increase traffic
for PERCENT in 25 50 75 100; do
  echo "Increasing traffic to $PERCENT%"
  
  ksi send deployment:adjust_traffic \
    --component "data_analyst_v2_optimized" \
    --percentage $PERCENT
  
  # Monitor for 15 minutes at each level
  sleep 900
  
  # Check metrics
  METRICS=$(ksi send monitor:deployment_metrics \
    --component "data_analyst_v2_optimized" \
    --format json)
  
  # Validate success criteria
  if ! python3 -c "
import json
metrics = json.loads('$METRICS')
assert metrics['error_rate'] < 0.01
assert metrics['latency_p95'] < 2.0
assert metrics['quality_score'] > 0.85
print('✓ Metrics pass at $PERCENT%')
  "; then
    echo "❌ Metrics failed at $PERCENT%, initiating rollback"
    ksi send deployment:rollback --immediate
    exit 1
  fi
done
```

## Phase 3: Production Activation (30 minutes)

### Step 3.1: Final Validation
```bash
# Verify all traffic on new version
ksi send deployment:status \
  --component "data_analyst_v2_optimized"

# Run production smoke tests
ksi send evaluation:run \
  --component "data_analyst_v2_optimized" \
  --test_suite "production_smoke_tests" \
  --environment "production"
```

### Step 3.2: Update Component Registry
```bash
# Mark as production version
ksi send composition:update_component \
  --name "personas/analysts/data_analyst" \
  --content_from "personas/analysts/data_analyst_v2_optimized" \
  --version "2.0.0" \
  --metadata '{
    "deployment_status": "production",
    "deployed_at": "2025-08-06T20:00:00Z",
    "optimization_method": "hybrid",
    "quality_improvement": "86.2%"
  }'

# Update Git
cd var/lib/compositions
git add .
git commit -m "Deploy optimized data_analyst v2.0.0 to production

- 35% token reduction
- 86.2% overall quality score
- All dimensions passing
- Hybrid optimization (DSPy + Judge)"
git push origin main
```

### Step 3.3: Configure Monitoring
```bash
# Set up production monitoring
ksi send monitor:configure \
  --component "personas/analysts/data_analyst" \
  --alerts '[
    {
      "metric": "quality_score",
      "threshold": "< 0.80",
      "action": "alert_team"
    },
    {
      "metric": "error_rate",
      "threshold": "> 0.02",
      "action": "auto_rollback"
    },
    {
      "metric": "token_usage",
      "threshold": "> baseline * 1.5",
      "action": "investigate"
    }
  ]'
```

## Phase 4: Post-Deployment (Ongoing)

### Step 4.1: Initial Monitoring (First 24 hours)
```bash
# High-frequency monitoring
while true; do
  clear
  echo "=== Production Metrics - $(date) ==="
  
  ksi send monitor:component_health \
    --component "personas/analysts/data_analyst" \
    --detailed
  
  echo
  echo "=== Recent Errors ==="
  ksi send monitor:get_events \
    --event_patterns "error:*" \
    --component "data_analyst" \
    --limit 5
  
  sleep 60
done
```

### Step 4.2: Performance Tracking
```bash
# Generate daily performance report
ksi send reporting:daily_component \
  --component "personas/analysts/data_analyst" \
  --metrics '[
    "average_quality_score",
    "token_usage_trend",
    "error_rate",
    "user_satisfaction"
  ]' \
  --email "team@example.com"
```

### Step 4.3: Continuous Optimization
```bash
# Schedule weekly re-evaluation
ksi send scheduler:create \
  --name "weekly_data_analyst_eval" \
  --schedule "0 2 * * 1" \
  --command "evaluation:run" \
  --params '{
    "component": "personas/analysts/data_analyst",
    "test_suite": "comprehensive_quality_suite",
    "alert_on_degradation": true
  }'
```

## Rollback Procedures

### Immediate Rollback (Emergency)
```bash
# Instant rollback to previous version
ksi send deployment:rollback \
  --component "personas/analysts/data_analyst" \
  --immediate \
  --reason "Critical quality degradation detected"

# Verify rollback
ksi send composition:get_component \
  --name "personas/analysts/data_analyst" \
  --show_version
```

### Planned Rollback
```bash
# Gradual rollback with monitoring
ksi send deployment:rollback \
  --component "personas/analysts/data_analyst" \
  --strategy "gradual" \
  --duration "30m" \
  --monitor
```

## Troubleshooting

### Common Issues

#### Quality Score Degradation
```bash
# Diagnose quality issues
ksi send evaluation:diagnose \
  --component "personas/analysts/data_analyst" \
  --dimension "instruction_fidelity" \
  --compare_with_baseline

# Get detailed breakdown
ksi send evaluation:detailed_scores \
  --component "data_analyst" \
  --last_24h
```

#### Token Usage Spike
```bash
# Analyze token usage
ksi send optimization:analyze_tokens \
  --component "data_analyst" \
  --time_range "1h" \
  --breakdown_by "prompt_type"

# Compare with baseline
ksi send optimization:token_comparison \
  --current "data_analyst_v2" \
  --baseline "data_analyst_v1"
```

#### Behavioral Inconsistency
```bash
# Run consistency tests
ksi send evaluation:consistency_check \
  --component "data_analyst" \
  --scenarios "production_scenarios.yaml" \
  --iterations 10
```

## Best Practices

### 1. Always Test Dependencies
Never deploy a component without verifying all dependencies have passing evaluations.

### 2. Use Canary Deployments
Start with 10% traffic and gradually increase. This minimizes impact of issues.

### 3. Monitor All Dimensions
Don't just track token usage - monitor all 5 quality dimensions continuously.

### 4. Maintain Rollback Capability
Always have a tested rollback path and keep previous versions available.

### 5. Document Changes
Include optimization method, improvements, and trade-offs in commit messages.

### 6. Automate Validation
Use scheduled evaluations to detect quality degradation early.

### 7. Team Communication
Notify team before deployments and maintain deployment calendar.

## Deployment Calendar Template

```yaml
deployment_schedule:
  - date: 2025-08-07
    component: personas/analysts/data_analyst
    version: 2.0.0
    window: "14:00-16:00 UTC"
    owner: optimization_team
    rollback_owner: oncall_engineer
    
  - date: 2025-08-08
    component: behaviors/core/mandatory_json
    version: 1.1.0
    window: "10:00-12:00 UTC"
    owner: platform_team
    rollback_owner: platform_oncall
```

## Success Metrics

### Deployment Success Criteria
- ✅ All quality dimensions meet or exceed thresholds
- ✅ Error rate < 1%
- ✅ Latency P95 < 2 seconds
- ✅ Token usage within 150% of baseline
- ✅ No critical alerts in first 24 hours
- ✅ User satisfaction maintained or improved

### Long-term Success Indicators
- 📈 Sustained quality scores over 30 days
- 📉 Reduced operational costs (tokens)
- 🎯 Improved task completion rates
- 🔄 Successful handling of edge cases
- 👥 Positive user feedback

## Compliance and Audit

### Deployment Records
All deployments must maintain:
- Optimization method used
- Quality scores before/after
- Deployment timestamp
- Rollback procedures tested
- Team members involved
- Business justification

### Audit Trail
```bash
# Generate deployment audit report
ksi send audit:deployment_history \
  --component "personas/analysts/data_analyst" \
  --include_metrics \
  --format "compliance_report"
```

## Conclusion

Following this guide ensures safe, reliable deployment of optimized components to production. The multi-phase approach with comprehensive testing, gradual rollout, and continuous monitoring minimizes risk while maximizing the benefits of optimization.

Remember: **Quality over speed**. It's better to take time validating than to rush a deployment that degrades user experience.

For emergencies, contact the on-call engineer and refer to the rollback procedures section.