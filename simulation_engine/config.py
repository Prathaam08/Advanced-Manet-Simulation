# File: simulation_engine/config.py

import threading

# Global simulation control flags
stop_simulation_flag = threading.Event()
start_simulation_flag = threading.Event()

# For backward compatibility with protocols that check config.stop_simulation
stop_simulation = False

def set_stop_simulation(value: bool):
    """Set the stop simulation flag"""
    global stop_simulation
    stop_simulation = value
    if value:
        stop_simulation_flag.set()
        start_simulation_flag.clear()
    else:
        stop_simulation_flag.clear()
        start_simulation_flag.set()

def get_stop_simulation() -> bool:
    """Get the current stop simulation status"""
    return stop_simulation_flag.is_set()

def is_simulation_stopped():
    """Function for backward compatibility"""
    return get_stop_simulation()

def get_stop():
    """Alias for get_stop_simulation for backward compatibility"""
    return get_stop_simulation()

# Simulation configuration parameters
DEFAULT_SIMULATION_CONFIG = {
    'num_nodes': 20,
    'area_width': 1000,
    'area_height': 1000,
    'transmission_range': 250,
    'simulation_time': 0,
    'mobility_model': 'random_waypoint',
    'packet_rate': 1.0,
    'protocols': ['AODV', 'DSDV', 'DSR', 'OLSR'],
    'num_scenarios': 5
}

# Protocol-specific configuration
PROTOCOL_CONFIG = {
    'AODV': {
        'hello_interval': 1.0,
        'allowed_hello_loss': 3,
        'rreq_retries': 3,
        'rreq_rate_limit': 10,
        'timeout_buffer': 2,
        'ttl_start': 1,
        'ttl_increment': 2,
        'ttl_threshold': 7,
        'ttl_max': 255,
        'net_diameter': 35
    },
    'DSDV': {
        'periodic_update_interval': 15.0,
        'triggered_update_interval': 5.0,
        'weighted_settling_time': 6.0,
        'route_hold_time': 120.0
    },
    'DSR': {
        'send_buffer_timeout': 30.0,
        'request_table_size': 64,
        'request_table_timeout': 10.0,
        'max_request_rexmt': 16,
        'max_request_period': 10.0,
        'request_period': 0.5,
        'nonprop_request_timeout': 0.03
    },
    'OLSR': {
        'hello_interval': 2.0,
        'tc_interval': 5.0,
        'mid_interval': 5.0,
        'hna_interval': 5.0,
        'refresh_timeout': 2.0,
        'dup_hold_time': 30.0,
        'mpr_coverage': 7
    }
}

# Node configuration
NODE_CONFIG = {
    'initial_energy': 100.0,
    'tx_power': 0.1,
    'rx_power': 0.05,
    'idle_power': 0.01,
    'sleep_power': 0.001,
    'speed_range': (1, 10),  # m/s
    'pause_time_range': (1, 10)  # seconds
}

# Packet configuration
PACKET_CONFIG = {
    'default_size': 64,  # bytes
    'max_size': 1024,    # bytes
    'header_size': 20,   # bytes
    'ttl': 64,          # time to live
    'buffer_size': 50   # max packets in buffer
}

# Mobility model configuration
MOBILITY_CONFIG = {
    'random_waypoint': {
        'min_speed': 0.5,
        'max_speed': 3.0,
        'pause_time': 5.0
    },
    'random_walk': {
        'min_speed': 1.0,
        'max_speed': 5.0,
        'direction_change_prob': 0.1
    },
    'static': {
        'speed': 0.0
    }
}

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'simulation.log',
    'console_output': True
}

# Performance configuration
PERFORMANCE_CONFIG = {
    'max_concurrent_simulations': 4,
    'simulation_timeout': 300,  # seconds
    'memory_limit_mb': 1024,
    'enable_progress_updates': True,
    'progress_update_interval': 1.0
}