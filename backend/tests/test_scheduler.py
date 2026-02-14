"""
Test scheduler logic
"""
import pytest
from app.scheduler.balanced_strategy import BalancedStrategy


def test_balanced_strategy_creation():
    """Test that BalancedStrategy can be instantiated"""
    strategy = BalancedStrategy()
    assert strategy is not None


def test_split_sessions_basic():
    """Test session splitting logic"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=120,
        min_len=30,
        max_len=60
    )
    
    assert len(sessions) == 2
    assert sum(sessions) == 120
