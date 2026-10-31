from __future__ import annotations

"""Rule definitions and priority-ordered execution engine for inventory replenishment."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class DecisionContext:
    """Context container passed to rule evaluation."""
    inventory_position: int
    current_stock: int
    on_order: int
    reorder_point: int
    lead_time_demand: float
    safety_stock: int
    lead_time_days: int
    days_of_cover: float
    mean_daily_forecast: float
    abc_class: str


@dataclass
class Rule:
    """Rule dataclass representing an inventory business rule."""
    rule_id: str
    priority_order: int
    condition: Callable[[DecisionContext], bool]
    action: str
    explanation_template: str


def r1_condition(ctx: DecisionContext) -> bool:
    """R1_EXPEDITE: inventory_position <= ROP AND on_order > 0 AND days_of_cover < L."""
    return (
        ctx.inventory_position <= ctx.reorder_point
        and ctx.on_order > 0
        and ctx.days_of_cover < ctx.lead_time_days
    )


def r2_condition(ctx: DecisionContext) -> bool:
    """R2_REORDER: inventory_position <= ROP."""
    return ctx.inventory_position <= ctx.reorder_point


def r3_condition(ctx: DecisionContext) -> bool:
    """R3_HOLD: otherwise."""
    return True


# Prescribed priority ordered rules
RULES: list[Rule] = [
    Rule(
        rule_id="R1_EXPEDITE",
        priority_order=1,
        condition=r1_condition,
        action="EXPEDITE_SHIPMENT",
        explanation_template=(
            "Inventory position {inv_pos} is at or below the reorder point {rop} "
            "(lead-time demand {ltd:.1f} + safety stock {ss}); {cover:.1f} days of cover "
            "is below the {lt}-day lead time with {on_order} units already on order, so expedite shipment."
        ),
    ),
    Rule(
        rule_id="R2_REORDER",
        priority_order=2,
        condition=r2_condition,
        action="REORDER_NOW",
        explanation_template=(
            "Inventory position {inv_pos} is at or below the reorder point {rop} "
            "(lead-time demand {ltd:.1f} + safety stock {ss}); {cover:.1f} days of cover "
            "{comparison} the {lt}-day lead time, so reorder now."
        ),
    ),
    Rule(
        rule_id="R3_HOLD",
        priority_order=3,
        condition=r3_condition,
        action="HOLD_STOCK",
        explanation_template=(
            "Inventory position {inv_pos} exceeds the reorder point {rop} "
            "(lead-time demand {ltd:.1f} + safety stock {ss}) with {cover:.1f} days of cover, so hold stock."
        ),
    ),
]


def evaluate_rules(ctx: DecisionContext) -> Rule:
    """Evaluate rules in ascending priority order and return first match.
    
    Args:
        ctx: Evaluated DecisionContext.
        
    Returns:
        The matched Rule.
    """
    sorted_rules = sorted(RULES, key=lambda r: r.priority_order)
    for rule in sorted_rules:
        if rule.condition(ctx):
            return rule
    return sorted_rules[-1]
