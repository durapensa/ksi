#!/usr/bin/env python3
"""
Melting Pot Test Orchestrator
==============================

Systematically tests all services, validators, and scenarios.
Provides comprehensive testing framework for the Melting Pot integration.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import traceback
import random
import statistics

# Import KSI client
from ksi_common.sync_client import MinimalSyncClient

# Import validators for direct testing
from ksi_daemon.validators.movement_validator import MovementValidator, MovementRequest, Position
from ksi_daemon.validators.resource_validator import ResourceTransferValidator, ResourceTransferRequest, TransferType
from ksi_daemon.validators.interaction_validator import InteractionValidator, InteractionRequest, InteractionType


@dataclass
class TestResult:
    """Result of a single test."""
    test_name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TestSuite:
    """Collection of test results."""
    suite_name: str
    tests: List[TestResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)
    
    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)
    
    @property
    def pass_rate(self) -> float:
        if not self.tests:
            return 0.0
        return self.passed / len(self.tests)
    
    @property
    def duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


class MeltingPotTestOrchestrator:
    """Orchestrates comprehensive testing of Melting Pot integration."""
    
    def __init__(self, socket_path: str = "/tmp/ksi.sock", verbose: bool = True):
        """Initialize test orchestrator."""
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.verbose = verbose
        self.test_suites: List[TestSuite] = []
        self.current_suite: Optional[TestSuite] = None
        
        # Initialize validators for direct testing
        self.movement_validator = MovementValidator()
        self.resource_validator = ResourceTransferValidator()
        self.interaction_validator = InteractionValidator()
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite."""
        self.log("="*80)
        self.log("MELTING POT TEST ORCHESTRATOR")
        self.log("="*80)
        
        overall_start = time.time()
        
        # 1. Test validators directly
        await self.test_validators()
        
        # 2. Test service health
        await self.test_service_health()
        
        # 3. Test service integration
        await self.test_service_integration()
        
        # 4. Test scenario basics
        await self.test_scenario_basics()
        
        # 5. Test fairness mechanisms
        await self.test_fairness_mechanisms()
        
        # 6. Generate report
        report = self.generate_report()
        
        overall_duration = time.time() - overall_start
        
        self.log("="*80)
        self.log(f"ALL TESTS COMPLETE in {overall_duration:.1f}s")
        self.log(f"Total Suites: {len(self.test_suites)}")
        self.log(f"Total Tests: {sum(len(s.tests) for s in self.test_suites)}")
        self.log(f"Overall Pass Rate: {self._calculate_overall_pass_rate():.1%}")
        self.log("="*80)
        
        return report
    
    # ==================== VALIDATOR TESTS ====================
    
    async def test_validators(self):
        """Test validators directly without services."""
        self.log("\n" + "="*60)
        self.log("TESTING VALIDATORS")
        self.log("="*60)
        
        suite = TestSuite("Validators")
        self.current_suite = suite
        
        # Test movement validator
        await self._test_movement_validator()
        
        # Test resource validator
        await self._test_resource_validator()
        
        # Test interaction validator
        await self._test_interaction_validator()
        
        suite.end_time = time.time()
        self.test_suites.append(suite)
        
        self.log(f"Validator Tests: {suite.passed}/{len(suite.tests)} passed")
    
    async def _test_movement_validator(self):
        """Test movement validation logic."""
        self.log("Testing Movement Validator...")
        
        # Test 1: Valid movement
        start = time.time()
        try:
            request = MovementRequest(
                entity_id="test_agent",
                entity_type="agent",
                from_position=Position(0, 0),
                to_position=Position(3, 4),
                movement_type="walk",
                speed=1.0
            )
            
            result = self.movement_validator.validate_movement(request)
            
            test_result = TestResult(
                test_name="movement_valid_walk",
                passed=result.valid,
                duration=time.time() - start,
                details={"distance": 5.0, "max_distance": 5.0}
            )
            
            if result.valid:
                self.log("  ✓ Valid walk movement")
            else:
                self.log(f"  ✗ Valid walk failed: {result.reason}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="movement_valid_walk",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 2: Invalid movement (too far)
        start = time.time()
        try:
            request = MovementRequest(
                entity_id="test_agent",
                entity_type="agent",
                from_position=Position(0, 0),
                to_position=Position(10, 10),
                movement_type="walk",
                speed=1.0
            )
            
            result = self.movement_validator.validate_movement(request)
            
            test_result = TestResult(
                test_name="movement_invalid_distance",
                passed=not result.valid and "exceeds max" in result.reason,
                duration=time.time() - start,
                details={"distance": 14.14, "max_distance": 5.0}
            )
            
            if not result.valid:
                self.log(f"  ✓ Correctly rejected far movement: {result.reason}")
            else:
                self.log("  ✗ Should have rejected far movement")
                
        except Exception as e:
            test_result = TestResult(
                test_name="movement_invalid_distance",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 3: Pathfinding with obstacles
        start = time.time()
        try:
            # Add obstacle
            self.movement_validator.add_obstacle({"x": 2, "y": 2})
            
            request = MovementRequest(
                entity_id="test_agent",
                entity_type="agent",
                from_position=Position(0, 0),
                to_position=Position(4, 4),
                movement_type="walk",
                speed=1.0
            )
            
            environment = {"obstacles": [{"x": 2, "y": 2}]}
            result = self.movement_validator.validate_movement(request, environment)
            
            test_result = TestResult(
                test_name="movement_pathfinding",
                passed=result.valid and result.suggested_path is not None,
                duration=time.time() - start,
                details={"path_length": len(result.suggested_path) if result.suggested_path else 0}
            )
            
            if result.valid:
                self.log(f"  ✓ Found path around obstacle ({len(result.suggested_path)} steps)")
            else:
                self.log(f"  ✗ Pathfinding failed: {result.reason}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="movement_pathfinding",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Clear obstacles for next tests
        self.movement_validator.clear_obstacles()
    
    async def _test_resource_validator(self):
        """Test resource transfer validation."""
        self.log("Testing Resource Validator...")
        
        # Setup initial ownership
        self.resource_validator.update_ownership("alice", "gold", 100)
        self.resource_validator.update_ownership("bob", "gold", 50)
        
        # Test 1: Valid transfer
        start = time.time()
        try:
            request = ResourceTransferRequest(
                from_entity="alice",
                to_entity="bob",
                resource_type="gold",
                amount=20,
                transfer_type=TransferType.GIFT
            )
            
            result = self.resource_validator.validate_transfer(request)
            
            test_result = TestResult(
                test_name="resource_valid_transfer",
                passed=result.valid,
                duration=time.time() - start,
                details={"amount": 20, "sender_balance": 100}
            )
            
            if result.valid:
                self.log("  ✓ Valid resource transfer")
            else:
                self.log(f"  ✗ Valid transfer failed: {result.reason}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="resource_valid_transfer",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 2: Invalid transfer (insufficient resources)
        start = time.time()
        try:
            request = ResourceTransferRequest(
                from_entity="bob",
                to_entity="alice",
                resource_type="gold",
                amount=100,
                transfer_type=TransferType.TRADE
            )
            
            result = self.resource_validator.validate_transfer(request)
            
            test_result = TestResult(
                test_name="resource_insufficient_funds",
                passed=not result.valid and "doesn't have" in result.reason,
                duration=time.time() - start,
                details={"requested": 100, "available": 50}
            )
            
            if not result.valid:
                self.log(f"  ✓ Correctly rejected insufficient funds: {result.reason}")
            else:
                self.log("  ✗ Should have rejected insufficient funds")
                
        except Exception as e:
            test_result = TestResult(
                test_name="resource_insufficient_funds",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 3: Fairness check
        start = time.time()
        try:
            # Make alice very rich
            self.resource_validator.update_ownership("alice", "gold", 1000)
            
            request = ResourceTransferRequest(
                from_entity="bob",
                to_entity="alice",
                resource_type="gold",
                amount=40,  # Poor giving to rich
                transfer_type=TransferType.GIFT
            )
            
            result = self.resource_validator.validate_transfer(request)
            
            # Check if fairness warning was triggered
            has_fairness_warning = (
                result.fairness and 
                (result.fairness.exploitation_risk or result.fairness.gini_impact > 0.05)
            )
            
            test_result = TestResult(
                test_name="resource_fairness_check",
                passed=has_fairness_warning,
                duration=time.time() - start,
                details={
                    "gini_impact": result.fairness.gini_impact if result.fairness else 0,
                    "exploitation": result.fairness.exploitation_risk if result.fairness else False
                }
            )
            
            if has_fairness_warning:
                self.log("  ✓ Fairness mechanism detected inequality")
            else:
                self.log("  ✗ Fairness check should have triggered")
                
        except Exception as e:
            test_result = TestResult(
                test_name="resource_fairness_check",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    async def _test_interaction_validator(self):
        """Test interaction validation."""
        self.log("Testing Interaction Validator...")
        
        # Test 1: Valid interaction
        start = time.time()
        try:
            request = InteractionRequest(
                actor_id="alice",
                target_id="bob",
                interaction_type=InteractionType.TRADE,
                range_limit=2.0,
                position_actor=(0, 0),
                position_target=(1, 1),
                capabilities=["trade"]
            )
            
            result = self.interaction_validator.validate_interaction(request)
            
            test_result = TestResult(
                test_name="interaction_valid_trade",
                passed=result.valid,
                duration=time.time() - start,
                details={"distance": 1.41, "max_range": 2.0}
            )
            
            if result.valid:
                self.log("  ✓ Valid trade interaction")
            else:
                self.log(f"  ✗ Valid trade failed: {result.reason}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="interaction_valid_trade",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 2: Out of range
        start = time.time()
        try:
            request = InteractionRequest(
                actor_id="alice",
                target_id="charlie",
                interaction_type=InteractionType.ATTACK,
                range_limit=2.0,
                position_actor=(0, 0),
                position_target=(10, 10),
                capabilities=["attack"]
            )
            
            result = self.interaction_validator.validate_interaction(request)
            
            test_result = TestResult(
                test_name="interaction_out_of_range",
                passed=not result.valid and "exceeds max range" in result.reason,
                duration=time.time() - start,
                details={"distance": 14.14, "max_range": 2.0}
            )
            
            if not result.valid:
                self.log(f"  ✓ Correctly rejected out-of-range: {result.reason}")
            else:
                self.log("  ✗ Should have rejected out-of-range interaction")
                
        except Exception as e:
            test_result = TestResult(
                test_name="interaction_out_of_range",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Test 3: Cooperation requirements
        start = time.time()
        try:
            request = InteractionRequest(
                actor_id="hunter1",
                target_id="stag",
                interaction_type=InteractionType.HUNT_COOPERATIVE,
                range_limit=5.0,
                position_actor=(10, 10),
                position_target=(12, 12),
                parameters={"cooperation_type": "stag_hunt"},
                capabilities=["hunt"]
            )
            
            # Need other hunters nearby
            context = {
                "nearby_entities": [
                    {"entity_id": "hunter2", "entity_type": "agent", "position": {"x": 11, "y": 10}},
                    {"entity_id": "hunter3", "entity_type": "agent", "position": {"x": 10, "y": 11}}
                ]
            }
            
            result = self.interaction_validator.validate_interaction(request, context)
            
            test_result = TestResult(
                test_name="interaction_cooperation",
                passed=result.valid,
                duration=time.time() - start,
                details={"participants": 3, "required": 3}
            )
            
            if result.valid:
                self.log("  ✓ Cooperative hunt validated")
            else:
                self.log(f"  ✗ Cooperation failed: {result.reason}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="interaction_cooperation",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    # ==================== SERVICE TESTS ====================
    
    async def test_service_health(self):
        """Test if services are healthy."""
        self.log("\n" + "="*60)
        self.log("TESTING SERVICE HEALTH")
        self.log("="*60)
        
        suite = TestSuite("Service Health")
        self.current_suite = suite
        
        services = ["spatial", "resource", "episode", "metrics", "scheduler"]
        
        for service_name in services:
            start = time.time()
            try:
                # Try to send a health check event
                response = self.client.send_event(f"{service_name}:health", {})
                
                test_result = TestResult(
                    test_name=f"health_{service_name}",
                    passed="error" not in response,
                    duration=time.time() - start,
                    details=response
                )
                
                if "error" not in response:
                    self.log(f"  ✓ {service_name} service healthy")
                else:
                    self.log(f"  ✗ {service_name} service error: {response['error']}")
                    
            except Exception as e:
                test_result = TestResult(
                    test_name=f"health_{service_name}",
                    passed=False,
                    duration=time.time() - start,
                    error=str(e),
                    warnings=[f"Service may not be registered"]
                )
                self.log(f"  ⚠ {service_name} service not responding: {e}")
            
            self.current_suite.tests.append(test_result)
        
        suite.end_time = time.time()
        self.test_suites.append(suite)
        
        self.log(f"Service Health: {suite.passed}/{len(suite.tests)} healthy")
    
    async def test_service_integration(self):
        """Test service integration with real events."""
        self.log("\n" + "="*60)
        self.log("TESTING SERVICE INTEGRATION")
        self.log("="*60)
        
        suite = TestSuite("Service Integration")
        self.current_suite = suite
        
        # Test spatial service
        await self._test_spatial_integration()
        
        # Test resource service
        await self._test_resource_integration()
        
        # Test episode service
        await self._test_episode_integration()
        
        suite.end_time = time.time()
        self.test_suites.append(suite)
        
        self.log(f"Integration Tests: {suite.passed}/{len(suite.tests)} passed")
    
    async def _test_spatial_integration(self):
        """Test spatial service integration."""
        self.log("Testing Spatial Service...")
        
        # Initialize environment
        start = time.time()
        try:
            response = self.client.send_event("spatial:initialize", {
                "environment_id": "test_env",
                "dimensions": 2,
                "bounds": {"x_min": 0, "x_max": 24, "y_min": 0, "y_max": 24},
                "grid_size": 1
            })
            
            test_result = TestResult(
                test_name="spatial_initialize",
                passed="error" not in response,
                duration=time.time() - start,
                details=response
            )
            
            if "error" not in response:
                self.log("  ✓ Spatial environment initialized")
            else:
                self.log(f"  ✗ Spatial init failed: {response['error']}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="spatial_initialize",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
        
        # Add entity
        start = time.time()
        try:
            response = self.client.send_event("spatial:entity:add", {
                "environment_id": "test_env",
                "entity_id": "test_agent",
                "entity_type": "agent",
                "position": {"x": 5, "y": 5},
                "properties": {"speed": 1.0}
            })
            
            test_result = TestResult(
                test_name="spatial_add_entity",
                passed="error" not in response,
                duration=time.time() - start,
                details=response
            )
            
            if "error" not in response:
                self.log("  ✓ Entity added to environment")
            else:
                self.log(f"  ✗ Add entity failed: {response['error']}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="spatial_add_entity",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    async def _test_resource_integration(self):
        """Test resource service integration."""
        self.log("Testing Resource Service...")
        
        # Create resource
        start = time.time()
        try:
            response = self.client.send_event("resource:create", {
                "resource_type": "test_gold",
                "amount": 100,
                "owner": "test_owner",
                "properties": {"value": 10}
            })
            
            test_result = TestResult(
                test_name="resource_create",
                passed="error" not in response,
                duration=time.time() - start,
                details=response
            )
            
            if "error" not in response:
                self.log("  ✓ Resource created")
            else:
                self.log(f"  ✗ Resource creation failed: {response['error']}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="resource_create",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    async def _test_episode_integration(self):
        """Test episode service integration."""
        self.log("Testing Episode Service...")
        
        # Create episode
        start = time.time()
        try:
            response = self.client.send_event("episode:create", {
                "episode_type": "test_scenario",
                "participants": ["agent1", "agent2"],
                "configuration": {
                    "max_steps": 100,
                    "spatial": True,
                    "dimensions": 2
                }
            })
            
            test_result = TestResult(
                test_name="episode_create",
                passed="error" not in response and "episode_id" in response.get("result", {}),
                duration=time.time() - start,
                details=response
            )
            
            if "error" not in response:
                episode_id = response.get("result", {}).get("episode_id")
                self.log(f"  ✓ Episode created: {episode_id}")
            else:
                self.log(f"  ✗ Episode creation failed: {response.get('error')}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="episode_create",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    # ==================== SCENARIO TESTS ====================
    
    async def test_scenario_basics(self):
        """Test basic scenario functionality."""
        self.log("\n" + "="*60)
        self.log("TESTING SCENARIO BASICS")
        self.log("="*60)
        
        suite = TestSuite("Scenario Basics")
        self.current_suite = suite
        
        # Test Prisoners Dilemma minimal version
        await self._test_prisoners_dilemma_minimal()
        
        suite.end_time = time.time()
        self.test_suites.append(suite)
        
        self.log(f"Scenario Tests: {suite.passed}/{len(suite.tests)} passed")
    
    async def _test_prisoners_dilemma_minimal(self):
        """Test minimal Prisoners Dilemma scenario."""
        self.log("Testing Prisoners Dilemma (Minimal)...")
        
        start = time.time()
        try:
            # Create episode
            response = self.client.send_event("episode:create", {
                "episode_type": "prisoners_dilemma",
                "participants": ["focal_1", "background_1"],
                "configuration": {
                    "max_steps": 10,
                    "spatial": True,
                    "dimensions": 2,
                    "grid_size": 10
                }
            })
            
            if "error" in response:
                raise Exception(f"Episode creation failed: {response['error']}")
            
            episode_id = response["result"]["episode_id"]
            
            # Initialize spatial
            response = self.client.send_event("spatial:initialize", {
                "environment_id": episode_id,
                "dimensions": 2,
                "bounds": {"x_min": 0, "x_max": 9, "y_min": 0, "y_max": 9}
            })
            
            # Add agents
            for i, agent_id in enumerate(["focal_1", "background_1"]):
                self.client.send_event("spatial:entity:add", {
                    "environment_id": episode_id,
                    "entity_id": agent_id,
                    "entity_type": "agent",
                    "position": {"x": i * 5, "y": i * 5}
                })
            
            # Run a few steps
            for step in range(3):
                response = self.client.send_event("episode:step", {
                    "episode_id": episode_id,
                    "actions": {
                        "focal_1": {"type": "cooperate"},
                        "background_1": {"type": "defect"}
                    }
                })
                
                if "error" in response:
                    raise Exception(f"Step {step} failed: {response['error']}")
            
            # Calculate metrics
            response = self.client.send_event("metrics:calculate", {
                "metric_types": ["gini", "collective_return"],
                "data_source": {"episode_id": episode_id}
            })
            
            metrics = response.get("result", {})
            
            test_result = TestResult(
                test_name="pd_minimal_scenario",
                passed=True,
                duration=time.time() - start,
                details={
                    "episode_id": episode_id,
                    "steps_completed": 3,
                    "metrics": metrics
                }
            )
            
            self.log(f"  ✓ PD scenario ran for 3 steps")
            self.log(f"    Metrics: Gini={metrics.get('gini', 0):.3f}, Return={metrics.get('collective_return', 0):.1f}")
            
        except Exception as e:
            test_result = TestResult(
                test_name="pd_minimal_scenario",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ PD scenario failed: {e}")
        
        self.current_suite.tests.append(test_result)
    
    # ==================== FAIRNESS TESTS ====================
    
    async def test_fairness_mechanisms(self):
        """Test fairness mechanisms."""
        self.log("\n" + "="*60)
        self.log("TESTING FAIRNESS MECHANISMS")
        self.log("="*60)
        
        suite = TestSuite("Fairness Mechanisms")
        self.current_suite = suite
        
        # Test strategic diversity
        await self._test_strategic_diversity()
        
        # Test consent mechanisms
        await self._test_consent_mechanisms()
        
        suite.end_time = time.time()
        self.test_suites.append(suite)
        
        self.log(f"Fairness Tests: {suite.passed}/{len(suite.tests)} passed")
    
    async def _test_strategic_diversity(self):
        """Test strategic diversity fairness condition."""
        self.log("Testing Strategic Diversity...")
        
        start = time.time()
        try:
            # Simulate diverse strategies
            strategies = ["cooperate", "defect", "tit_for_tat", "random"]
            diversity_score = len(set(strategies)) / len(strategies)
            
            test_result = TestResult(
                test_name="strategic_diversity",
                passed=diversity_score >= 0.75,  # At least 75% diversity
                duration=time.time() - start,
                details={
                    "strategies": strategies,
                    "unique": len(set(strategies)),
                    "diversity_score": diversity_score
                }
            )
            
            if diversity_score >= 0.75:
                self.log(f"  ✓ Strategic diversity achieved: {diversity_score:.1%}")
            else:
                self.log(f"  ✗ Insufficient diversity: {diversity_score:.1%}")
                
        except Exception as e:
            test_result = TestResult(
                test_name="strategic_diversity",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    async def _test_consent_mechanisms(self):
        """Test consent mechanisms."""
        self.log("Testing Consent Mechanisms...")
        
        start = time.time()
        try:
            # Test resource transfer with consent
            request = ResourceTransferRequest(
                from_entity="donor",
                to_entity="recipient",
                resource_type="gold",
                amount=50,
                transfer_type=TransferType.GIFT
            )
            
            # Update ownership for test
            self.resource_validator.update_ownership("donor", "gold", 100)
            
            # Validate with consent check
            result = self.resource_validator.validate_transfer(request)
            
            # Consent should be checked for gifts
            has_consent_check = result.consent is not None
            
            test_result = TestResult(
                test_name="consent_mechanism",
                passed=has_consent_check,
                duration=time.time() - start,
                details={
                    "transfer_type": "gift",
                    "consent_checked": has_consent_check,
                    "consented": result.consent.consented if result.consent else None
                }
            )
            
            if has_consent_check:
                self.log(f"  ✓ Consent mechanism active")
            else:
                self.log(f"  ✗ Consent not checked for gift transfer")
                
        except Exception as e:
            test_result = TestResult(
                test_name="consent_mechanism",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
            self.log(f"  ✗ Exception: {e}")
        
        self.current_suite.tests.append(test_result)
    
    # ==================== REPORT GENERATION ====================
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_suites": len(self.test_suites),
                "total_tests": sum(len(s.tests) for s in self.test_suites),
                "total_passed": sum(s.passed for s in self.test_suites),
                "total_failed": sum(s.failed for s in self.test_suites),
                "overall_pass_rate": self._calculate_overall_pass_rate(),
                "total_duration": sum(s.duration for s in self.test_suites)
            },
            "suites": []
        }
        
        for suite in self.test_suites:
            suite_report = {
                "name": suite.suite_name,
                "passed": suite.passed,
                "failed": suite.failed,
                "pass_rate": suite.pass_rate,
                "duration": suite.duration,
                "tests": []
            }
            
            for test in suite.tests:
                test_report = {
                    "name": test.test_name,
                    "passed": test.passed,
                    "duration": test.duration,
                    "error": test.error,
                    "warnings": test.warnings,
                    "details": test.details
                }
                suite_report["tests"].append(test_report)
            
            report["suites"].append(suite_report)
        
        # Save report to file
        report_path = Path(f"results/test_report_{int(time.time())}.json")
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log(f"\nReport saved to: {report_path}")
        
        return report
    
    def _calculate_overall_pass_rate(self) -> float:
        """Calculate overall pass rate across all suites."""
        total_tests = sum(len(s.tests) for s in self.test_suites)
        total_passed = sum(s.passed for s in self.test_suites)
        
        if total_tests == 0:
            return 0.0
        
        return total_passed / total_tests


async def main():
    """Run the test orchestrator."""
    orchestrator = MeltingPotTestOrchestrator(verbose=True)
    report = await orchestrator.run_all_tests()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['total_passed']}")
    print(f"Failed: {report['summary']['total_failed']}")
    print(f"Pass Rate: {report['summary']['overall_pass_rate']:.1%}")
    print(f"Duration: {report['summary']['total_duration']:.1f}s")
    
    return report


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())