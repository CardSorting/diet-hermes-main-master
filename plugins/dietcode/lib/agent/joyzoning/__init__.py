"""JoyZoning cognitive architecture — native Hermes runtime concepts.

JoyZoning (habitat) observes and supervises.
Hermes (this package) owns operational execution state.
JSDP (mutation plugin) owns transformation proposals.

Do not collapse these layers.
"""
from agent.joyzoning.boundaries import RuntimeLayer, layer_for_event
from agent.joyzoning.convergence import (
    ConvergenceState,
    get_convergence_state,
    require_review_before_complete,
    transition_convergence,
)
from agent.joyzoning.journal import ExecutionJournal, get_journal
from agent.joyzoning.config import JoyZoningConfig, get_joyzoning_config
from agent.joyzoning.scope_registry import register_from_scope_env

__all__ = [
    "RuntimeLayer",
    "layer_for_event",
    "ConvergenceState",
    "get_convergence_state",
    "require_review_before_complete",
    "transition_convergence",
    "ExecutionJournal",
    "get_journal",
    "JoyZoningConfig",
    "get_joyzoning_config",
    "register_from_scope_env",
]
