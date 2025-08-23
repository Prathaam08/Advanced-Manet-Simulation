
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from simulation_engine.simulator import MANETSimulator
from simulation_engine.auto_protocol_tester import AutoProtocolTester
import threading
import os
import json
import time
from uuid import uuid4
from simulation_engine import config

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the auto protocol tester
auto_tester = AutoProtocolTester(socketio)

# Keep original simulator for manual testing
simulator = None
sim_thread = None
current_run_id = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_auto_testing', methods=['POST'])
def start_auto_testing():
    """Start comprehensive automatic protocol testing"""
    data = request.json or {}
    num_scenarios = data.get('num_scenarios', 5)
    
    result = auto_tester.start_comprehensive_testing(num_scenarios)
    return jsonify(result)

@app.route('/stop_auto_testing', methods=['POST'])
def stop_auto_testing():
    """Stop the automatic testing"""
    result = auto_tester.stop_testing()
    return jsonify(result)

@app.route('/get_testing_status', methods=['GET'])
def get_testing_status():
    """Get current testing status"""
    status = auto_tester.get_current_status()
    return jsonify(status)

@app.route('/start_simulation', methods=['POST'])
def start_simulation():
    """Original manual simulation endpoint"""
    global simulator, sim_thread, current_run_id
    cfg = request.json or {}
    
    run_id = str(uuid4())
    current_run_id = run_id

    if simulator and sim_thread and sim_thread.is_alive():
        config.set_stop()
        time.sleep(1)

    area_size_val = cfg.get('areaSize', 1000)
    area_size = (area_size_val, area_size_val)

    simulator = MANETSimulator(
        num_nodes=cfg.get('numNodes', 50),
        area_size=area_size,
        protocol=cfg.get('protocol', 'AODV'),
        sim_time=cfg.get('simTime', 45),
        traffic_load=cfg.get('trafficLoad', 10),
        node_speed=cfg.get('nodeSpeed', 5),
        tx_range=cfg.get('txRange', 100),
        pause_time=cfg.get('pauseTime', 2)
    )

    def _bg(local_run_id):
        try:
            for event in simulator.run():
                if config.get_stop():
                    socketio.emit('sim_stopped', {'message': 'Simulation stopped', 'run_id': local_run_id})
                    return

                if isinstance(event, dict):
                    event['run_id'] = local_run_id
                    event['manual_mode'] = True

                socketio.emit('sim_update', event)
                if event.get('type') == 'final_metrics':
                    socketio.emit('sim_complete', dict(event, run_id=local_run_id))
        except Exception as e:
            socketio.emit('sim_error', {'error': str(e), 'run_id': local_run_id})

    sim_thread = threading.Thread(target=_bg, args=(run_id,), daemon=True)
    sim_thread.start()

    return jsonify({"status": "started", "run_id": run_id})

@app.route('/stop_simulation', methods=['POST'])
def stop_simulation_route():
    config.set_stop()
    return jsonify({"status": "stopping"})

@app.route('/get_history')
def get_history():
    simulations = []
    sim_dir = 'data/simulations'
    if not os.path.exists(sim_dir):
        os.makedirs(sim_dir, exist_ok=True)
    
    for file in os.listdir(sim_dir):
        if file.endswith('.json'):
            with open(os.path.join(sim_dir, file)) as f:
                try:
                    simulations.append(json.load(f))
                except:
                    pass
    return jsonify(simulations)

if __name__ == '__main__':
    os.makedirs('data/simulations', exist_ok=True)
    os.makedirs('data/test_results', exist_ok=True)
    socketio.run(app, debug=True, port=5000)
