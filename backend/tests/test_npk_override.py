import pytest
from app.services.dev.npk_override import NPKOverrideState, NPK_PROFILES

def test_npk_override_null():
    state = NPKOverrideState()
    n, p, k, ok = state.apply(0, 0.0, 0, False)
    assert n == 0
    assert p == 0.0
    assert k == 0
    assert ok is False

def test_npk_override_sample1():
    state = NPKOverrideState()
    state.set("sample1")
    n, p, k, ok = state.apply(0, 0.0, 0, False)
    
    assert ok is True
    assert NPK_PROFILES["sample1"]["n"][0] <= n <= NPK_PROFILES["sample1"]["n"][1]
    assert NPK_PROFILES["sample1"]["p"][0] <= p <= NPK_PROFILES["sample1"]["p"][1]
    assert NPK_PROFILES["sample1"]["k"][0] <= k <= NPK_PROFILES["sample1"]["k"][1]
