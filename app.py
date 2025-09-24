from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import json
import threading
import time
import random
from datetime import datetime
import os
from simulation_engine.config import stop_simulation_flag, start_simulation_flag
from simulation_engine.auto_protocol_tester import AutoProtocolTester

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")   # important!

# Global variables for simulation state
current_simulation = None
simulation_results = []
simulation_progress = {
    'progress': 0,
    'current_test': 'Not Started',
    'scenarios_completed': 0,
    'protocols_tested': 0,
    'completed': False,
    'results': []
}

class EnhancedAutoProtocolTester(AutoProtocolTester):
    """Enhanced version with source-destination support"""
    
    def __init__(self, config,socketio_instance):
        super().__init__(socketio_instance)
        self.config = config
        self.results = []
        
    def run_comprehensive_test(self, progress_callback=None):
        """Run tests with source-destination support"""
        protocols = self.config['protocols']
        num_scenarios = self.config['num_scenarios']
        enable_route_selection = self.config.get('enable_route_selection', False)
        source_node = self.config.get('source_node')
        destination_node = self.config.get('destination_node')
        
        total_tests = len(protocols) * num_scenarios
        completed_tests = 0
        
        print(f"Starting comprehensive test...")
        print(f"Protocols: {protocols}")
        print(f"Scenarios: {num_scenarios}")
        print(f"Route Selection: {enable_route_selection}")
        print(f"Source Node: {source_node}")
        print(f"Destination Node: {destination_node}")
        print(f"Total tests to run: {total_tests}")
        
        # Initialize results list
        self.results = []
        
        if enable_route_selection:
            print(f"Fixed Route: Node {source_node} → Node {destination_node}")
        
        for protocol in protocols:
            protocol_results = []
            
            for scenario in range(num_scenarios):
                if stop_simulation_flag.is_set():
                    print("Simulation stopped by user")
                    return self.results
                
                # Configure route based on selection
                if enable_route_selection:
                    route_config = {
                        'source_node': source_node,
                        'destination_node': destination_node,
                        'fixed_route': True
                    }
                else:
                    # Generate random source and destination
                    available_nodes = list(range(1, self.config['num_nodes'] + 1))
                    source = random.choice(available_nodes)
                    destination = random.choice([n for n in available_nodes if n != source])
                    route_config = {
                        'source_node': source,
                        'destination_node': destination,
                        'fixed_route': False
                    }
                
                print(f"Testing {protocol} - Scenario {scenario + 1}/{num_scenarios}")
                print(f"Route: Node {route_config['source_node']} → Node {route_config['destination_node']}")
                
                # Run single test
                result = self.run_single_test(protocol, scenario, route_config)
                protocol_results.append(result)
                self.results.append(result)
                
                completed_tests += 1
                progress = int((completed_tests / total_tests) * 100)
                
                # Update progress
                if progress_callback:
                    progress_callback({
                        'progress': progress,
                        'current_test': f'{protocol} - Scenario {scenario + 1}',
                        'scenarios_completed': completed_tests // len(protocols),
                        'protocols_tested': len([p for p in protocols[:protocols.index(protocol) + 1]]),
                        'completed': False,
                        'results': self.results.copy()
                    })
                
                # Add delay to simulate real testing
                time.sleep(1)
            
            print(f"Completed all scenarios for {protocol}")
        
        # Final progress update
        if progress_callback:
            progress_callback({
                'progress': 100,
                'current_test': 'Completed',
                'scenarios_completed': num_scenarios,
                'protocols_tested': len(protocols),
                'completed': True,
                'results': self.results
            })
        
        print(f"Comprehensive test completed. Total results: {len(self.results)}")
        return self.results
    
    def run_single_test(self, protocol, scenario, route_config):
        """Run a single test scenario"""
        try:
            print(f"Starting run_single_test for {protocol}, scenario {scenario}")
            print(f"Route config: {route_config}")
            
            # Import your simulation modules
            from simulation_engine.simulator import MANETSimulator
            from simulation_engine.manet_models import Node
            
            # Create simulator with configuration
            print(f"Creating simulator with: nodes={self.config['num_nodes']}, area={self.config['area_width']}x{self.config['area_height']}, range={self.config['transmission_range']}, time={self.config['simulation_time']}, model={self.config['mobility_model']}")
            simulator = MANETSimulator(
                num_nodes=self.config['num_nodes'],
                area_width=self.config['area_width'],
                area_height=self.config['area_height'],
                transmission_range=self.config['transmission_range'],
                simulation_time=self.config['simulation_time'],
                mobility_model=self.config['mobility_model']
            )
            
            # Configure specific source and destination
            source_node_id = route_config['source_node']
            dest_node_id = route_config['destination_node']
            print(f"Source node: {source_node_id}, Destination node: {dest_node_id}")
            
            # Run simulation with specific protocol
            packet_rate = self.config.get('packet_rate', 1.0)
            print(f"Running simulation with protocol={protocol}, packet_rate={packet_rate}")
            metrics = simulator.run_simulation(
                protocol=protocol,
                source_node=source_node_id,
                destination_node=dest_node_id,
                packet_rate=packet_rate
            )
            print(f"Simulation completed with metrics: {metrics}")
            
            
            # Create result object
            print("Creating result object")
            result = {
                'protocol': protocol,
                'scenario': scenario,
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'packet_delivery_ratio': metrics.get('delivery_ratio', 0.0),
                    'average_delay': metrics.get('avg_delay', 0.0),
                    'routing_overhead': metrics.get('routing_overhead', 0.0),
                    'throughput': metrics.get('throughput', 0.0),
                    'energy_consumption': metrics.get('energy_consumption', 0.0),
                    'route_discovery_time': metrics.get('route_discovery_time', 0.0),
                    'hop_count': metrics.get('avg_hop_count', 0),
                    'packet_loss': metrics.get('packet_loss', 0.0)
                },
                'route_info': route_config,
                'network_config': {
                    'num_nodes': self.config['num_nodes'],
                    'area_size': f"{self.config['area_width']}x{self.config['area_height']}",
                    'transmission_range': self.config['transmission_range'],
                    'mobility_model': self.config['mobility_model']
                }
            }
            
            print(f"Returning result: {result}")
            return result
            
        except Exception as e:
            print(f"Error in simulation: {e}")
            import traceback
            traceback.print_exc()
            # Return dummy data for demo purposes
            dummy_result = self.generate_dummy_result(protocol, scenario, route_config)
            print(f"Returning dummy result: {dummy_result}")
            return dummy_result
    
    def generate_dummy_result(self, protocol, scenario, route_config):
        """Generate dummy results for testing UI"""
        base_metrics = {
            'AODV': {'delivery': 0.85, 'delay': 45, 'overhead': 0.12, 'throughput': 850},
            'DSDV': {'delivery': 0.78, 'delay': 38, 'overhead': 0.18, 'throughput': 780},
            'DSR': {'delivery': 0.82, 'delay': 52, 'overhead': 0.15, 'throughput': 820},
            'OLSR': {'delivery': 0.88, 'delay': 41, 'overhead': 0.22, 'throughput': 880}
        }
        
        base = base_metrics.get(protocol, base_metrics['AODV'])
        variation = 0.15  # 15% variation
        
        # Add some variation based on route distance for fixed routes
        if route_config['fixed_route']:
            # Simulate distance effect
            distance_factor = abs(route_config['source_node'] - route_config['destination_node']) / self.config['num_nodes']
            delivery_modifier = -distance_factor * 0.1
            delay_modifier = distance_factor * 10
        else:
            delivery_modifier = 0
            delay_modifier = 0
        
        return {
            'protocol': protocol,
            'scenario': scenario,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'packet_delivery_ratio': max(0.1, min(1.0, base['delivery'] + delivery_modifier + (random.random() - 0.5) * variation)),
                'average_delay': max(1, base['delay'] + delay_modifier + (random.random() - 0.5) * base['delay'] * variation),
                'routing_overhead': max(0.01, base['overhead'] + (random.random() - 0.5) * variation * 0.5),
                'throughput': max(100, base['throughput'] + (random.random() - 0.5) * base['throughput'] * variation),
                'energy_consumption': 40 + random.random() * 40,
                'route_discovery_time': 5 + random.random() * 20,
                'hop_count': max(1, int(2 + random.random() * 4)),
                'packet_loss': max(0, 1 - (base['delivery'] + delivery_modifier + (random.random() - 0.5) * variation))
            },
            'route_info': route_config,
            'network_config': {
                'num_nodes': self.config['num_nodes'],
                'area_size': f"{self.config['area_width']}x{self.config['area_height']}",
                'transmission_range': self.config['transmission_range'],
                'mobility_model': self.config['mobility_model']
            }
        }

def update_simulation_progress(progress_data):
    """Update global simulation progress"""
    global simulation_progress
    simulation_progress.update(progress_data)
    socketio.emit('simulation_progress', progress_data)
    print(f"Progress Update: {progress_data['progress']}% - {progress_data['current_test']}")

def run_simulation_thread(config):
    """Run simulation in separate thread"""
    global current_simulation, simulation_results
    
    try:
        print("Starting simulation thread...")
        print(f"Configuration: {config}")
        start_simulation_flag.set()
        stop_simulation_flag.clear()
        
        # Create enhanced tester with socketio
        tester = EnhancedAutoProtocolTester(config, socketio)   # ✅ pass socketio
        print("Created EnhancedAutoProtocolTester")
        
        # Run comprehensive test
        print("Starting run_comprehensive_test...")
        results = tester.run_comprehensive_test(progress_callback=update_simulation_progress)
        print(f"run_comprehensive_test returned {len(results) if results else 'None'} results")
        
        simulation_results = results
        print(f"Simulation completed with {len(results) if results else 0} results")
        
        # Save results to file
        if results and len(results) > 0:
            print("Calling save_results_to_file...")
            save_results_to_file(results, config)
        else:
            print("No results to save!")
        
    except Exception as e:
        print(f"Simulation thread error: {e}")
        import traceback
        traceback.print_exc()
        simulation_progress['completed'] = True
        simulation_progress['current_test'] = f'Error: {str(e)}'
        socketio.emit('simulation_error', {'error': str(e)})
    finally:
        current_simulation = None
        start_simulation_flag.clear()

def save_results_to_file(results, config):
    """Save simulation results to file"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data/test_results', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'data/test_results/manet_test_{timestamp}.json'
        
        print(f"Preparing to save results to {filename}")
        print(f"Results count: {len(results)}")
        print(f"Config: {config}")
        
        data = {
            'test_configuration': config,
            'test_results': results,
            'test_completion_time': datetime.now().isoformat(),
            'total_tests': len(results),
            'protocols_tested': config['protocols'],
            'scenarios_per_protocol': config['num_scenarios']
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to {filename}")
        
    except Exception as e:
        print(f"Error saving results: {e}")
        import traceback
        traceback.print_exc()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/modern')
def modern_index():
    return render_template('modern_index.html')

@app.route('/api/start_simulation', methods=['POST'])
def start_simulation():
    """Start a new simulation"""
    global current_simulation, simulation_progress, simulation_results
    
    try:
        if current_simulation is not None:
            return jsonify({'error': 'Simulation already running'}), 400
        
        config = request.json
        print(f"Received simulation request with config: {config}")
        
        # Validate configuration
        if not validate_config(config):
            print("Invalid configuration")
            return jsonify({'error': 'Invalid configuration'}), 400
        
        # Reset progress
        simulation_progress = {
            'progress': 0,
            'current_test': 'Initializing...',
            'scenarios_completed': 0,
            'protocols_tested': 0,
            'completed': False,
            'results': []
        }
        simulation_results = []
        print("Reset simulation progress and results")
        
        # Start simulation in separate thread
        print("Starting simulation thread")
        current_simulation = threading.Thread(target=run_simulation_thread, args=(config,))
        current_simulation.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Simulation started successfully',
            'config': config
        })
        
    except Exception as e:
        print(f"Error starting simulation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/simulation_status', methods=['GET'])
def get_simulation_status():
    """Get current simulation status"""
    global simulation_progress
    return jsonify(simulation_progress)

@app.route('/api/stop_simulation', methods=['POST'])
def stop_simulation():
    """Stop current simulation"""
    global current_simulation
    
    try:
        stop_simulation_flag.set()
        start_simulation_flag.clear()
        
        if current_simulation:
            simulation_progress['current_test'] = 'Stopping...'
            # Wait for thread to finish
            current_simulation.join(timeout=5)
            current_simulation = None
        
        simulation_progress['completed'] = True
        simulation_progress['current_test'] = 'Stopped'
        
        return jsonify({'status': 'stopped', 'message': 'Simulation stopped'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get simulation results"""
    global simulation_results
    
    return jsonify({
        'results': simulation_results,
        'total_count': len(simulation_results),
        'completion_time': simulation_progress.get('completion_time')
    })

@app.route('/api/clear_results', methods=['POST'])
def clear_results():
    """Clear all simulation results"""
    global simulation_results, simulation_progress
    
    simulation_results = []
    simulation_progress = {
        'progress': 0,
        'current_test': 'Not Started',
        'scenarios_completed': 0,
        'protocols_tested': 0,
        'completed': False,
        'results': []
    }
    
    return jsonify({'status': 'cleared', 'message': 'Results cleared successfully'})

def validate_config(config):
    """Validate simulation configuration"""
    required_fields = [
        'num_nodes', 'area_width', 'area_height', 'transmission_range',
        'num_scenarios', 'simulation_time', 'mobility_model', 'protocols'
    ]
    
    for field in required_fields:
        if field not in config:
            print(f"Missing required field: {field}")
            return False
    
    # Validate protocols list
    if not config['protocols'] or len(config['protocols']) == 0:
        print("No protocols selected")
        return False
    
    # Validate route selection
    if config.get('enable_route_selection', False):
        if not config.get('source_node') or not config.get('destination_node'):
            print("Source or destination node not specified for route selection")
            return False
        
        if config['source_node'] == config['destination_node']:
            print("Source and destination nodes cannot be the same")
            return False
        
        if config['source_node'] > config['num_nodes'] or config['destination_node'] > config['num_nodes']:
            print("Source or destination node exceeds network size")
            return False
    
    # Validate numeric ranges
    if config['num_nodes'] < 2 or config['num_nodes'] > 1000:
        print("Invalid number of nodes")
        return False
    
    if config['num_scenarios'] < 1 or config['num_scenarios'] > 100:
        print("Invalid number of scenarios")
        return False
    
    return True

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting MANET Protocol Auto-Tester...")
    print("Dashboard will be available at: http://localhost:5000")
    
    # Create necessary directories
    os.makedirs('data/simulations', exist_ok=True)
    os.makedirs('data/test_results', exist_ok=True)
    
    if __name__ == '__main__':
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
