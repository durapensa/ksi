#!/usr/bin/env python3
"""
Resource Transfer Validator
============================

Validates resource transfers with consent and fairness checks.
Prevents exploitation and ensures economic balance.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class TransferType(Enum):
    """Types of resource transfers."""
    GIFT = "gift"
    TRADE = "trade"
    HARVEST = "harvest"
    THEFT = "theft"
    TAX = "tax"
    PRODUCTION = "production"
    CONSUMPTION = "consumption"


@dataclass
class ResourceTransferRequest:
    """A resource transfer validation request."""
    from_entity: str
    to_entity: str
    resource_type: str
    amount: float
    transfer_type: TransferType
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConsentStatus:
    """Consent status for a transfer."""
    consented: bool
    reason: str = ""
    negotiated_amount: Optional[float] = None
    conditions: List[str] = None
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []


@dataclass
class FairnessCheck:
    """Fairness analysis of a transfer."""
    fair: bool
    gini_impact: float = 0.0
    monopoly_risk: bool = False
    exploitation_risk: bool = False
    sustainability_impact: float = 0.0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class ValidationResult:
    """Result of resource transfer validation."""
    valid: bool
    reason: str = ""
    consent: Optional[ConsentStatus] = None
    fairness: Optional[FairnessCheck] = None
    suggested_amount: Optional[float] = None
    alternative_transfers: List[Dict] = None
    
    def __post_init__(self):
        if self.alternative_transfers is None:
            self.alternative_transfers = []


class ResourceTransferValidator:
    """Validates resource transfers with fairness and consent."""
    
    def __init__(self):
        self.resource_ownership: Dict[str, Dict[str, float]] = {}
        self.transfer_history: List[ResourceTransferRequest] = []
        self.consent_settings = {
            "default_threshold": 0.3,  # 30% refusal rate
            "exploitation_threshold": 0.5,  # 50% wealth transfer threshold
            "monopoly_threshold": 0.4  # 40% market share threshold
        }
        self.fairness_settings = {
            "max_gini_increase": 0.1,
            "min_consent_ratio": 0.7,
            "max_monopoly_share": 0.4
        }
        
    def validate_transfer(self, request: ResourceTransferRequest, 
                         context: Optional[Dict] = None) -> ValidationResult:
        """Validate a resource transfer request."""
        
        # Check ownership
        if not self._check_ownership(request):
            return ValidationResult(
                valid=False,
                reason=f"{request.from_entity} doesn't have {request.amount} {request.resource_type}"
            )
        
        # Check consent if required
        consent = None
        if self._requires_consent(request):
            consent = self._check_consent(request, context)
            if not consent.consented:
                return ValidationResult(
                    valid=False,
                    reason=f"Transfer not consented: {consent.reason}",
                    consent=consent,
                    suggested_amount=consent.negotiated_amount
                )
        
        # Check fairness
        fairness = self._check_fairness(request, context)
        if not fairness.fair and request.transfer_type != TransferType.THEFT:
            # Generate alternatives
            alternatives = self._suggest_alternatives(request, fairness)
            return ValidationResult(
                valid=False,
                reason=f"Transfer violates fairness principles",
                fairness=fairness,
                alternative_transfers=alternatives
            )
        
        # Check conservation laws
        if not self._check_conservation(request):
            return ValidationResult(
                valid=False,
                reason="Transfer violates resource conservation"
            )
        
        # Record transfer for history
        self.transfer_history.append(request)
        
        return ValidationResult(
            valid=True,
            consent=consent,
            fairness=fairness
        )
    
    def _check_ownership(self, request: ResourceTransferRequest) -> bool:
        """Check if sender owns the resources."""
        if request.from_entity == "environment":
            return True  # Environment has unlimited resources
        
        owner_resources = self.resource_ownership.get(request.from_entity, {})
        owned_amount = owner_resources.get(request.resource_type, 0)
        
        return owned_amount >= request.amount
    
    def _requires_consent(self, request: ResourceTransferRequest) -> bool:
        """Check if transfer requires consent."""
        # Gifts and trades require consent
        if request.transfer_type in [TransferType.GIFT, TransferType.TRADE]:
            return True
        
        # Harvest from owned resources requires consent
        if request.transfer_type == TransferType.HARVEST:
            if request.from_entity != "environment":
                return True
        
        # Theft never has consent
        if request.transfer_type == TransferType.THEFT:
            return False
        
        return False
    
    def _check_consent(self, request: ResourceTransferRequest, 
                      context: Optional[Dict]) -> ConsentStatus:
        """Check consent for transfer."""
        
        # Check recent interaction history
        recent_interactions = self._get_recent_interactions(
            request.from_entity, 
            request.to_entity
        )
        
        # Calculate consent probability based on history
        if recent_interactions:
            positive_interactions = sum(
                1 for t in recent_interactions 
                if t.transfer_type in [TransferType.GIFT, TransferType.TRADE]
            )
            negative_interactions = sum(
                1 for t in recent_interactions 
                if t.transfer_type == TransferType.THEFT
            )
            
            consent_probability = (positive_interactions + 1) / (
                positive_interactions + negative_interactions + 2
            )
        else:
            consent_probability = 1 - self.consent_settings["default_threshold"]
        
        # Check if transfer is exploitative
        if self._is_exploitative(request, context):
            consent_probability *= 0.5  # Reduce consent for exploitation
        
        # Make consent decision
        import random
        consented = random.random() < consent_probability
        
        if not consented:
            # Negotiate alternative
            negotiated = request.amount * 0.5  # Offer half
            return ConsentStatus(
                consented=False,
                reason="Transfer amount too high",
                negotiated_amount=negotiated,
                conditions=["Reduce amount", "Provide compensation"]
            )
        
        return ConsentStatus(consented=True)
    
    def _check_fairness(self, request: ResourceTransferRequest, 
                       context: Optional[Dict]) -> FairnessCheck:
        """Check fairness impact of transfer."""
        
        # Calculate Gini impact
        gini_before = self._calculate_gini()
        gini_after = self._calculate_gini_after_transfer(request)
        gini_impact = gini_after - gini_before
        
        # Check monopoly risk
        monopoly_risk = self._check_monopoly_risk(request)
        
        # Check exploitation
        exploitation_risk = self._is_exploitative(request, context)
        
        # Check sustainability
        sustainability_impact = self._check_sustainability_impact(request)
        
        # Determine if fair
        fair = True
        warnings = []
        
        if gini_impact > self.fairness_settings["max_gini_increase"]:
            fair = False
            warnings.append(f"Gini increase {gini_impact:.2f} exceeds threshold")
        
        if monopoly_risk:
            fair = False
            warnings.append("Creates monopoly risk")
        
        if exploitation_risk:
            fair = False
            warnings.append("Potentially exploitative transfer")
        
        if sustainability_impact < -0.3:
            fair = False
            warnings.append("Threatens resource sustainability")
        
        return FairnessCheck(
            fair=fair,
            gini_impact=gini_impact,
            monopoly_risk=monopoly_risk,
            exploitation_risk=exploitation_risk,
            sustainability_impact=sustainability_impact,
            warnings=warnings
        )
    
    def _calculate_gini(self) -> float:
        """Calculate current Gini coefficient."""
        all_wealth = []
        
        for entity, resources in self.resource_ownership.items():
            total_wealth = sum(resources.values())
            all_wealth.append(total_wealth)
        
        if len(all_wealth) < 2:
            return 0.0
        
        # Sort wealth
        all_wealth = sorted(all_wealth)
        n = len(all_wealth)
        
        # Calculate Gini
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * all_wealth)) / (n * np.sum(all_wealth)) - (n + 1) / n
    
    def _calculate_gini_after_transfer(self, request: ResourceTransferRequest) -> float:
        """Calculate Gini after hypothetical transfer."""
        # Make a copy of current ownership
        temp_ownership = {
            entity: resources.copy() 
            for entity, resources in self.resource_ownership.items()
        }
        
        # Apply transfer
        if request.from_entity in temp_ownership:
            temp_ownership[request.from_entity][request.resource_type] -= request.amount
        
        if request.to_entity not in temp_ownership:
            temp_ownership[request.to_entity] = {}
        if request.resource_type not in temp_ownership[request.to_entity]:
            temp_ownership[request.to_entity][request.resource_type] = 0
        temp_ownership[request.to_entity][request.resource_type] += request.amount
        
        # Calculate new Gini
        all_wealth = []
        for entity, resources in temp_ownership.items():
            total_wealth = sum(resources.values())
            all_wealth.append(total_wealth)
        
        if len(all_wealth) < 2:
            return 0.0
        
        all_wealth = sorted(all_wealth)
        n = len(all_wealth)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * all_wealth)) / (n * np.sum(all_wealth)) - (n + 1) / n
    
    def _check_monopoly_risk(self, request: ResourceTransferRequest) -> bool:
        """Check if transfer creates monopoly."""
        # Calculate receiver's share after transfer
        total_resource = sum(
            resources.get(request.resource_type, 0)
            for resources in self.resource_ownership.values()
        )
        
        if total_resource == 0:
            return False
        
        receiver_current = self.resource_ownership.get(
            request.to_entity, {}
        ).get(request.resource_type, 0)
        
        receiver_after = receiver_current + request.amount
        market_share = receiver_after / (total_resource + request.amount)
        
        return market_share > self.fairness_settings["max_monopoly_share"]
    
    def _is_exploitative(self, request: ResourceTransferRequest, 
                        context: Optional[Dict]) -> bool:
        """Check if transfer is exploitative."""
        # Check wealth disparity
        sender_wealth = sum(self.resource_ownership.get(request.from_entity, {}).values())
        receiver_wealth = sum(self.resource_ownership.get(request.to_entity, {}).values())
        
        if sender_wealth > 0:
            transfer_ratio = request.amount / sender_wealth
            
            # If poor entity giving large portion to rich entity
            if receiver_wealth > sender_wealth * 2 and transfer_ratio > 0.3:
                return True
        
        # Check if part of repeated exploitation pattern
        recent = self._get_recent_interactions(request.from_entity, request.to_entity)
        if len(recent) > 3:
            # Check if always one-directional
            reverse_transfers = [
                t for t in recent 
                if t.from_entity == request.to_entity and t.to_entity == request.from_entity
            ]
            if len(reverse_transfers) == 0:
                return True
        
        return False
    
    def _check_conservation(self, request: ResourceTransferRequest) -> bool:
        """Check if transfer violates conservation laws."""
        # Resources can't be created or destroyed (except by environment)
        if request.transfer_type == TransferType.PRODUCTION:
            # Production creates resources, needs special handling
            return True
        
        if request.transfer_type == TransferType.CONSUMPTION:
            # Consumption destroys resources, needs validation
            return request.from_entity != "environment"
        
        return True
    
    def _check_sustainability_impact(self, request: ResourceTransferRequest) -> float:
        """Calculate sustainability impact (-1 to 1)."""
        # Check if depleting renewable resources
        if request.resource_type in ["commons_resource", "forest", "fish"]:
            total = sum(
                resources.get(request.resource_type, 0)
                for resources in self.resource_ownership.values()
            )
            
            if total > 0:
                depletion_rate = request.amount / total
                
                # Negative impact if depleting too fast
                if depletion_rate > 0.1:  # More than 10% in one transfer
                    return -depletion_rate
        
        # Check if transfer supports regeneration
        if request.transfer_type == TransferType.PRODUCTION:
            return 0.5  # Positive for production
        
        return 0.0  # Neutral
    
    def _get_recent_interactions(self, entity1: str, entity2: str, 
                                limit: int = 10) -> List[ResourceTransferRequest]:
        """Get recent transfer history between two entities."""
        recent = []
        for transfer in reversed(self.transfer_history):
            if ((transfer.from_entity == entity1 and transfer.to_entity == entity2) or
                (transfer.from_entity == entity2 and transfer.to_entity == entity1)):
                recent.append(transfer)
                if len(recent) >= limit:
                    break
        return recent
    
    def _suggest_alternatives(self, request: ResourceTransferRequest, 
                             fairness: FairnessCheck) -> List[Dict]:
        """Suggest alternative transfers that would be fair."""
        alternatives = []
        
        # Suggest reduced amount
        if fairness.gini_impact > 0:
            reduced_amount = request.amount * 0.5
            alternatives.append({
                "type": "reduced_amount",
                "amount": reduced_amount,
                "reason": "Reduces inequality impact"
            })
        
        # Suggest reciprocal trade
        if fairness.exploitation_risk:
            alternatives.append({
                "type": "reciprocal_trade",
                "give": request.resource_type,
                "give_amount": request.amount,
                "receive": "alternative_resource",
                "receive_amount": request.amount * 0.8,
                "reason": "Balanced exchange prevents exploitation"
            })
        
        # Suggest delayed transfer
        if fairness.monopoly_risk:
            alternatives.append({
                "type": "delayed_transfer",
                "amount_per_step": request.amount / 5,
                "steps": 5,
                "reason": "Gradual transfer prevents monopolization"
            })
        
        return alternatives
    
    def update_ownership(self, entity: str, resource_type: str, amount: float):
        """Update resource ownership records."""
        if entity not in self.resource_ownership:
            self.resource_ownership[entity] = {}
        
        if resource_type not in self.resource_ownership[entity]:
            self.resource_ownership[entity][resource_type] = 0
        
        self.resource_ownership[entity][resource_type] += amount
    
    def get_entity_wealth(self, entity: str) -> float:
        """Get total wealth of an entity."""
        return sum(self.resource_ownership.get(entity, {}).values())
    
    def get_resource_distribution(self, resource_type: str) -> Dict[str, float]:
        """Get distribution of a specific resource."""
        distribution = {}
        for entity, resources in self.resource_ownership.items():
            if resource_type in resources:
                distribution[entity] = resources[resource_type]
        return distribution


class DSPyResourceValidator:
    """DSPy-based validator for complex economic scenarios."""
    
    def __init__(self):
        self.basic_validator = ResourceTransferValidator()
        
    def validate_market_transaction(self, request: ResourceTransferRequest,
                                   market_context: Dict) -> ValidationResult:
        """Validate transaction considering market dynamics."""
        
        # Basic validation
        result = self.basic_validator.validate_transfer(request)
        
        if not result.valid:
            return result
        
        # Add market considerations
        market_price = market_context.get("prices", {}).get(request.resource_type, 1.0)
        supply = market_context.get("supply", {}).get(request.resource_type, 100)
        demand = market_context.get("demand", {}).get(request.resource_type, 100)
        
        # Check if price is fair
        if request.transfer_type == TransferType.TRADE:
            expected_value = request.amount * market_price
            offered_value = request.metadata.get("payment", 0)
            
            if offered_value < expected_value * 0.7:  # 30% below market
                return ValidationResult(
                    valid=False,
                    reason=f"Offered price {offered_value} significantly below market {expected_value}",
                    suggested_amount=expected_value
                )
        
        # Check market impact
        if request.amount > supply * 0.2:  # Large transaction
            warnings = result.fairness.warnings if result.fairness else []
            warnings.append(f"Large transaction may impact market price")
            
            if result.fairness:
                result.fairness.warnings = warnings
        
        return result


# Export validators
__all__ = ['ResourceTransferValidator', 'DSPyResourceValidator', 'ValidationResult',
           'ResourceTransferRequest', 'ConsentStatus', 'FairnessCheck', 'TransferType']