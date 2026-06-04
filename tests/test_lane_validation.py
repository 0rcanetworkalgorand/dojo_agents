"""Agent lane payload validation tests.

Tests the validate_task_payload method for each of the four agent lanes:
- Research: requires 'query' or 'description'
- Code: requires 'description' or 'query'
- Data: requires 'data' or 'operation'
- Outreach: requires 'recipient' or 'goal'

These tests do NOT require API keys, LLM calls, or network access.
They validate ONLY the input validation logic by calling the method
directly on the class (unbound) since the base SDK classes have
abstract methods that prevent normal instantiation without full config.
"""

import sys
from pathlib import Path

import pytest

# Add dojo-agents root to path so lane imports resolve
_AGENTS_ROOT = Path(__file__).resolve().parents[1]
if str(_AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_ROOT))

from lanes.research import ActiveResearchLane
from lanes.code import CodeLane
from lanes.data import DataLane
from lanes.outreach import OutreachLane


# ---------------------------------------------------------------------------
# Helper: call validate_task_payload as an unbound method (no instance needed)
# The validation logic is a pure function of the payload dict — it doesn't
# reference self beyond being a method on the class.
# ---------------------------------------------------------------------------

def _validate(lane_class, payload):
    """Call validate_task_payload without instantiating the class."""
    return lane_class.validate_task_payload(None, payload)


# ---------------------------------------------------------------------------
# Research Lane Tests
# ---------------------------------------------------------------------------

class TestResearchLaneValidation:
    """Validate Research lane payload requirements: 'query' or 'description'."""

    def test_valid_with_query(self):
        assert _validate(ActiveResearchLane, {"query": "Algorand DeFi trends"}) is True

    def test_valid_with_description(self):
        assert _validate(ActiveResearchLane, {"description": "Analyze market trends"}) is True

    def test_valid_with_both(self):
        assert _validate(ActiveResearchLane, {"query": "x", "description": "y"}) is True

    def test_invalid_empty_payload(self):
        assert _validate(ActiveResearchLane, {}) is False

    def test_invalid_wrong_fields(self):
        assert _validate(ActiveResearchLane, {"topic": "AI", "context": "general"}) is False


# ---------------------------------------------------------------------------
# Code Lane Tests
# ---------------------------------------------------------------------------

class TestCodeLaneValidation:
    """Validate Code lane payload requirements: 'description' or 'query'."""

    def test_valid_with_description(self):
        assert _validate(CodeLane, {"description": "Write a sorting algorithm"}) is True

    def test_valid_with_query(self):
        assert _validate(CodeLane, {"query": "binary search in Python"}) is True

    def test_valid_with_both(self):
        assert _validate(CodeLane, {"description": "x", "query": "y"}) is True

    def test_invalid_empty_payload(self):
        assert _validate(CodeLane, {}) is False

    def test_invalid_wrong_fields(self):
        assert _validate(CodeLane, {"language": "python", "context": "web"}) is False


# ---------------------------------------------------------------------------
# Data Lane Tests
# ---------------------------------------------------------------------------

class TestDataLaneValidation:
    """Validate Data lane payload requirements: 'data' or 'operation'."""

    def test_valid_with_data(self):
        assert _validate(DataLane, {"data": "col1,col2\n1,2\n3,4"}) is True

    def test_valid_with_operation(self):
        assert _validate(DataLane, {"operation": "aggregate by month"}) is True

    def test_valid_with_both(self):
        assert _validate(DataLane, {"data": "x", "operation": "clean"}) is True

    def test_invalid_empty_payload(self):
        assert _validate(DataLane, {}) is False

    def test_invalid_wrong_fields(self):
        assert _validate(DataLane, {"format": "csv", "source": "api"}) is False


# ---------------------------------------------------------------------------
# Outreach Lane Tests
# ---------------------------------------------------------------------------

class TestOutreachLaneValidation:
    """Validate Outreach lane payload requirements: 'recipient' or 'goal'."""

    def test_valid_with_recipient(self):
        assert _validate(OutreachLane, {"recipient": "investor@vc.com"}) is True

    def test_valid_with_goal(self):
        assert _validate(OutreachLane, {"goal": "partnership introduction"}) is True

    def test_valid_with_both(self):
        assert _validate(OutreachLane, {"recipient": "x", "goal": "y"}) is True

    def test_invalid_empty_payload(self):
        assert _validate(OutreachLane, {}) is False

    def test_invalid_wrong_fields(self):
        assert _validate(OutreachLane, {"message": "hi", "tone": "formal"}) is False
