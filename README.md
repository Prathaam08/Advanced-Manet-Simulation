# Advanced MANET Simulation

## Overview
This project is a comprehensive Mobile Ad-hoc Network (MANET) simulation tool built using **Python** and **SimPy**. It provides a web-based interface for configuring, running, and visualizing MANET simulations. 

**Note:** This project does **NOT** use ns-3. It features a custom-built simulation engine that models network nodes, mobility, and routing protocols purely in Python.

## Key Features
- **Custom Simulation Engine**: Built on top of `simpy` for discrete-event simulation.
- **Protocol Support**: Implements major MANET routing protocols:
  - **AODV** (Ad hoc On-Demand Distance Vector)
  - **DSDV** (Destination-Sequenced Distance-Vector)
  - **DSR** (Dynamic Source Routing)
  - **OLSR** (Optimized Link State Routing)
- **Automated Protocol Tester**: Built-in framework to automatically run comprehensive tests across multiple random scenarios and rank protocols based on a composite performance score.
- **Mobility Models**: Supports Random Waypoint and Random Walk mobility models.
- **Real-time Visualization**: Web-based dashboard to view simulation progress and results.
- **Comprehensive Metrics**: Tracks Packet Delivery Ratio (PDR), End-to-End Delay, Throughput, Routing Overhead, and Energy Consumption.

## Project Structure

```
Advanced-Manet-Simulation/
├── app.py                  # Main Flask application entry point
├── requirements.txt        # Python dependencies
├── simulation_engine/      # Core simulation logic
│   ├── simulator.py        # MANETSimulator class (SimPy environment, topology)
│   ├── protocols.py        # Protocol implementations (AODV, DSDV, DSR, OLSR)
│   ├── manet_models.py     # Node and Packet models
│   ├── auto_protocol_tester.py # Orchestrator for automated testing
│   └── config.py           # Configuration settings
├── static/                 # Static assets (CSS, JS)
├── templates/              # HTML templates
└── data/                   # Simulation results and data storage
```

## How It Works

### 1. Simulation Engine (`simulation_engine/`)
The core of the project lies in the `simulation_engine` directory.
- **`simulator.py`**: Initializes the `simpy.Environment`, creates nodes based on the specified area and density, and manages the simulation loop. It handles packet generation and collects global metrics.
- **`manet_models.py`**: Defines the `Node` class, which represents a network node with properties like position, speed, energy, and transmission range. It also defines the `Packet` class. Nodes move according to the selected mobility model.
- **`protocols.py`**: Contains the logic for routing protocols. Each protocol is a class that manages routing tables, route discovery (for reactive protocols like AODV/DSR), and periodic updates (for proactive protocols like DSDV/OLSR).

### 2. Web Interface (`app.py`)
The Flask application serves as the control center.
- It provides APIs to start, stop, and monitor simulations.
- It uses `Flask-SocketIO` to push real-time updates (progress, current test status) to the frontend.
- Simulation runs in a separate thread to keep the web server responsive.

### 3. Simulation Flow
1.  **Configuration**: User selects parameters (nodes, area, protocol, etc.) via the UI.
2.  **Initialization**: `MANETSimulator` creates the network topology and initializes the selected protocol.
3.  **Execution**:
    - **Traffic Generation**: Source nodes generate packets destined for specific nodes.
    - **Routing**: The protocol determines the path. For AODV/DSR, this involves Route Request (RREQ) and Route Reply (RREP) cycles. For DSDV/OLSR, it uses pre-calculated tables.
    - **Mobility**: Nodes move within the simulation area, dynamically changing the network topology and connectivity.
    - **Energy**: Nodes consume energy for transmission, reception, and movement.
4.  **Metrics**: The simulator tracks successful deliveries, drops, delays, and overhead.
5.  **Reporting**: Results are aggregated and displayed on the dashboard.

## Installation & Usage

### Prerequisites
- Python 3.8+
- pip

### Setup
1.  Clone the repository or navigate to the project directory.
2.  Create a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application
1.  Start the Flask server:
    ```bash
    python app.py
    ```
2.  Open your web browser and go to:
    ```
    http://localhost:5000
    ```

## Configuration Parameters
- **Number of Nodes**: Total nodes in the network.
- **Area Size**: Width and height of the simulation field (in meters).
- **Transmission Range**: Maximum distance a node can transmit data.
- **Simulation Time**: Duration of the simulation (in seconds).
- **Mobility Model**: Strategy for node movement (Random Waypoint, Random Walk).
- **Protocols**: Select one or more protocols to test and compare.

## Dependencies
- `Flask`, `Flask-SocketIO`: Web framework and real-time communication.
- `simpy`: Discrete-event simulation framework.
- `numpy`: Numerical operations for position and distance calculations.
- `networkx`: Graph algorithms (used for some topology analysis).
- `matplotlib`, `pandas`: Data visualization and analysis.
