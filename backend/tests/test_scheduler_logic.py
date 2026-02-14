"""
Tests for scheduler algorithm logic
"""
import pytest
from datetime import datetime, date, timedelta
from app.scheduler.balanced_strategy import BalancedStrategy
from app.models.database_models import TaskDB


def test_split_sessions_respects_min_length():
    """Test that all sessions respect minimum length"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=200,
        min_len=40,
        max_len=60
    )
    
    assert all(s >= 40 for s in sessions)
    assert sum(sessions) == 200


def test_split_sessions_respects_max_length():
    """Test that no session exceeds maximum length"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=200,
        min_len=30,
        max_len=50
    )
    
    assert all(s <= 50 for s in sessions)
    assert sum(sessions) == 200


def test_split_sessions_combines_small_remainder():
    """Test that small remainders are combined with previous session"""
    strategy = BalancedStrategy()
    
    # 125 minutes with max 60 should give [60, 65] not [60, 60, 5]
    sessions = strategy._split_sessions(
        total_minutes=125,
        min_len=30,
        max_len=60
    )
    
    assert len(sessions) == 2
    assert sum(sessions) == 125


def test_split_sessions_edge_case_exact_min():
    """Test edge case where total equals minimum"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=30,
        min_len=30,
        max_len=60
    )
    
    assert len(sessions) == 1
    assert sessions[0] == 30


def test_split_sessions_edge_case_exact_max():
    """Test edge case where total equals maximum"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=60,
        min_len=30,
        max_len=60
    )
    
    assert len(sessions) == 1
    assert sessions[0] == 60


def test_split_sessions_multiple_of_max():
    """Test when total is exact multiple of max"""
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=180,
        min_len=30,
        max_len=60
    )
    
    assert len(sessions) == 3
    assert all(s == 60 for s in sessions)
