"""
End-to-end integration test for the Diesel Tank Monitor.
Exercises all three demo scenarios through the full pipeline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from tank_model import TankModel, TankConfig
from simulator import TankSimulator, Scenario
from ml_detector import TheftDetector
from bridge import DataBridge

def test_scenario(name, scenario, tank, detector, sim):
    tank.reset()
    readings = sim.generate_scenario(scenario, speed_multiplier=2.0)
    
    theft_detected = False
    pump_on_seen = False
    pump_off_seen = False
    hours_remaining_seen = False
    pump_was_on = False
    
    for r in readings:
        state = tank.process_reading(r.distance_cm, r.generator_on, r.timestamp)
        
        # ML detection
        history = tank.get_level_history()
        if len(history) >= 5:
            ml_result = detector.predict(history, r.generator_on, r.timestamp)
            if ml_result.is_theft:
                theft_detected = True
        
        # Track pump transitions
        if state.pump_on and not pump_was_on:
            pump_on_seen = True
        if not state.pump_on and pump_was_on:
            pump_off_seen = True
        pump_was_on = state.pump_on
        
        if state.hours_remaining is not None:
            hours_remaining_seen = True
    
    return {
        "readings": len(readings),
        "theft_detected": theft_detected,
        "pump_on_seen": pump_on_seen,
        "pump_off_seen": pump_off_seen,
        "hours_remaining_seen": hours_remaining_seen,
        "final_level": state.level_pct,
        "final_status": state.status,
    }

def main():
    tank = TankModel()
    detector = TheftDetector()
    sim = TankSimulator()
    
    print("=" * 60)
    print("DIESEL TANK MONITOR - Integration Test")
    print("=" * 60)
    print(f"ML Model loaded: {detector.is_trained}")
    print()
    
    # Test 1: Hysteresis
    print("TEST 1: Hysteresis Demo (Full->Empty->Full)")
    r = test_scenario("Hysteresis", Scenario.HYSTERESIS, tank, detector, sim)
    print(f"  Readings processed: {r['readings']}")
    print(f"  Pump turned ON:     {r['pump_on_seen']}")
    print(f"  Pump turned OFF:    {r['pump_off_seen']}")
    print(f"  Final level:        {r['final_level']}%")
    assert r['pump_on_seen'], "FAIL: Pump should have turned ON at 20%"
    assert r['pump_off_seen'], "FAIL: Pump should have turned OFF at 90%"
    print("  PASSED\n")
    
    # Test 2: Theft
    print("TEST 2: Theft Demo (Generator OFF, sudden drop)")
    r = test_scenario("Theft", Scenario.THEFT, tank, detector, sim)
    print(f"  Readings processed: {r['readings']}")
    print(f"  Theft detected:     {r['theft_detected']}")
    print(f"  Final level:        {r['final_level']}%")
    assert r['theft_detected'], "FAIL: Theft should have been detected"
    print("  PASSED\n")
    
    # Test 3: Consumption
    print("TEST 3: Consumption Demo (Generator ON, steady drain)")
    r = test_scenario("Consumption", Scenario.CONSUMPTION, tank, detector, sim)
    print(f"  Readings processed: {r['readings']}")
    print(f"  Hours remaining:    {r['hours_remaining_seen']}")
    print(f"  Theft detected:     {r['theft_detected']}")
    print(f"  Final level:        {r['final_level']}%")
    assert r['hours_remaining_seen'], "FAIL: Hours remaining should have appeared"
    assert not r['theft_detected'], "FAIL: No theft during normal gen consumption"
    print("  PASSED\n")
    
    print("=" * 60)
    print("ALL 3 TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
