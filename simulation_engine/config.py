# File: simulation_engine/config.py

# Global flag to control simulation execution
stop_simulation = False

def reset():
    """Reset the global stop flag."""
    global stop_simulation
    stop_simulation = False

def set_stop():
    """Set the stop flag to True."""
    global stop_simulation
    stop_simulation = True

def get_stop():
    """Return the current stop flag."""
    return stop_simulation