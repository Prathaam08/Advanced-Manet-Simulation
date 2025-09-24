import requests
import json

# API endpoint
url = 'http://localhost:5000/api/start_simulation'

# Test configuration
config = {
    "num_nodes": 10,
    "area_width": 1000,
    "area_height": 1000,
    "transmission_range": 250,
    "num_scenarios": 1,
    "simulation_time": 100,
    "mobility_model": "random_waypoint",
    "protocols": ["AODV"],
    "enable_route_selection": False
}

# Send POST request
response = requests.post(url, json=config)

# Print response
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")