# File: simulation_engine/auto_protocol_tester.py

import random
import numpy as np
from .simulator import MANETSimulator
from . import config
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple
import threading
import json
import os

@dataclass
class NetworkScenario:
    """Represents a random network scenario with all parameters"""
    num_nodes: int
    area_size: Tuple[int, int]
    node_speed: float
    pause_time: float
    tx_range: float
    traffic_load: float
    sim_time: int
    scenario_id: str

@dataclass
class ProtocolResult:
    """Results for a protocol in a specific scenario"""
    protocol: str
    scenario_id: str
    pdr: float
    avg_delay: float
    throughput: float
    energy_consumption: float
    overhead: float
    score: float

class AutoProtocolTester:
    """Automatically tests all protocols across random scenarios to find the best one"""
    
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self.protocols = ['AODV', 'DSDV', 'DSR', 'OLSR']
        self.scenarios = []
        self.results = []
        self.current_scenario = None
        self.current_protocol = None
        self.testing_active = False
        self.progress = 0
        
    def generate_random_scenarios(self, num_scenarios=5):
        """Generate multiple random network scenarios"""
        self.scenarios = []
        
        for i in range(num_scenarios):
            scenario = NetworkScenario(
                num_nodes=random.randint(20, 80),
                area_size=(random.randint(500, 1500), random.randint(500, 1500)),
                node_speed=random.uniform(2, 25),
                pause_time=random.uniform(1, 10),
                tx_range=random.randint(100, 250),
                traffic_load=random.randint(5, 30),
                sim_time=45,
                scenario_id=f"scenario_{i+1}"
            )
            self.scenarios.append(scenario)
            
        return self.scenarios
    
    def calculate_protocol_score(self, pdr, avg_delay, throughput, energy, overhead):
        """Calculate composite score for protocol performance"""
        pdr_score = min(pdr, 1.0) * 100
        delay_score = max(0, 100 - min(avg_delay, 1000) / 10)
        throughput_score = min(throughput / 50.0, 1.0) * 100
        energy_score = max(0, 100 - min(energy, 5000) / 50)
        overhead_score = max(0, 100 - min(overhead, 1000) / 10)
        
        weights = {
            'pdr': 0.3,
            'delay': 0.25,
            'throughput': 0.2,
            'energy': 0.15,
            'overhead': 0.1
        }
        
        total_score = (
            pdr_score * weights['pdr'] +
            delay_score * weights['delay'] +
            throughput_score * weights['throughput'] +
            energy_score * weights['energy'] +
            overhead_score * weights['overhead']
        )
        
        return round(total_score, 2)
    
    def run_protocol_test(self, protocol, scenario):
        """Run a single protocol test on a scenario"""
        simulator = MANETSimulator(
            num_nodes=scenario.num_nodes,
            area_size=scenario.area_size,
            protocol=protocol,
            sim_time=scenario.sim_time,
            traffic_load=scenario.traffic_load,
            node_speed=scenario.node_speed,
            tx_range=scenario.tx_range,
            pause_time=scenario.pause_time
        )
        
        final_result = None
        
        for event in simulator.run():
            if config.get_stop_simulation():
                return None
                
            if isinstance(event, dict):
                event['current_protocol'] = protocol
                event['current_scenario'] = scenario.scenario_id
                event['testing_mode'] = True
                self.socketio.emit('protocol_test_update', event)
            
            if event.get('type') == 'final_metrics':
                final_result = event
                break
        
        if final_result:
            score = self.calculate_protocol_score(
                final_result['pdr'],
                final_result['avg_delay'],
                final_result['throughput'],
                final_result['energy'],
                final_result['overhead']
            )
            
            return ProtocolResult(
                protocol=protocol,
                scenario_id=scenario.scenario_id,
                pdr=final_result['pdr'],
                avg_delay=final_result['avg_delay'],
                throughput=final_result['throughput'],
                energy_consumption=final_result['energy'],
                overhead=final_result['overhead'],
                score=score
            )
        
        return None
    
    def start_comprehensive_testing(self, num_scenarios=5):
        """Start comprehensive protocol testing across multiple scenarios"""
        if self.testing_active:
            return {"status": "already_running"}
            
        self.testing_active = True
        self.results = []
        config.reset()
        
        self.scenarios = self.generate_random_scenarios(num_scenarios)
        
        def _test_all_protocols():
            total_tests = len(self.protocols) * len(self.scenarios)
            completed_tests = 0
            
            try:
                scenario_info = [
                    {
                        'id': s.scenario_id,
                        'nodes': s.num_nodes,
                        'area': f"{s.area_size[0]}x{s.area_size[1]}",
                        'speed': f"{s.node_speed:.1f} m/s",
                        'traffic': f"{s.traffic_load} pkt/s",
                        'tx_range': f"{s.tx_range}m"
                    }
                    for s in self.scenarios
                ]
                
                self.socketio.emit('testing_started', {
                    'scenarios': scenario_info,
                    'protocols': self.protocols,
                    'total_tests': total_tests
                })
                
                for scenario in self.scenarios:
                    if config.get_stop():
                        break
                        
                    self.current_scenario = scenario
                    
                    for protocol in self.protocols:
                        if config.get_stop():
                            break
                            
                        self.current_protocol = protocol
                        
                        self.socketio.emit('current_test', {
                            'protocol': protocol,
                            'scenario': scenario.scenario_id,
                            'progress': (completed_tests / total_tests) * 100
                        })
                        
                        result = self.run_protocol_test(protocol, scenario)
                        
                        if result:
                            self.results.append(result)
                            
                            self.socketio.emit('test_completed', {
                                'result': {
                                    'protocol': result.protocol,
                                    'scenario': result.scenario_id,
                                    'pdr': result.pdr,
                                    'delay': result.avg_delay,
                                    'throughput': result.throughput,
                                    'energy': result.energy_consumption,
                                    'overhead': result.overhead,
                                    'score': result.score
                                }
                            })
                        
                        completed_tests += 1
                
                if not config.get_stop() and self.results:
                    analysis = self.analyze_results()
                    self.save_test_results(analysis)
                    self.socketio.emit('testing_complete', analysis)
                else:
                    self.socketio.emit('testing_stopped', {'message': 'Testing was stopped'})
                    
            except Exception as e:
                self.socketio.emit('testing_error', {'error': str(e)})
                
            finally:
                self.testing_active = False
        
        test_thread = threading.Thread(target=_test_all_protocols, daemon=True)
        test_thread.start()
        
        return {"status": "started", "total_scenarios": num_scenarios}
    
    def analyze_results(self):
        """Analyze all results to determine the best protocol"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        protocol_stats = {}
        
        for result in self.results:
            protocol = result.protocol
            if protocol not in protocol_stats:
                protocol_stats[protocol] = {
                    'scores': [],
                    'pdrs': [],
                    'delays': [],
                    'throughputs': [],
                    'energies': [],
                    'overheads': [],
                    'test_count': 0
                }
            
            stats = protocol_stats[protocol]
            stats['scores'].append(result.score)
            stats['pdrs'].append(result.pdr)
            stats['delays'].append(result.avg_delay)
            stats['throughputs'].append(result.throughput)
            stats['energies'].append(result.energy_consumption)
            stats['overheads'].append(result.overhead)
            stats['test_count'] += 1
        
        protocol_averages = {}
        for protocol, stats in protocol_stats.items():
            protocol_averages[protocol] = {
                'avg_score': np.mean(stats['scores']),
                'avg_pdr': np.mean(stats['pdrs']),
                'avg_delay': np.mean(stats['delays']),
                'avg_throughput': np.mean(stats['throughputs']),
                'avg_energy': np.mean(stats['energies']),
                'avg_overhead': np.mean(stats['overheads']),
                'consistency': 100 - (np.std(stats['scores']) / max(np.mean(stats['scores']), 0.1) * 100),
                'test_count': stats['test_count']
            }
        
        best_protocol = max(protocol_averages.keys(), 
                          key=lambda p: protocol_averages[p]['avg_score'])
        
        analysis = {
            'best_protocol': best_protocol,
            'best_score': protocol_averages[best_protocol]['avg_score'],
            'protocol_rankings': sorted(
                [(protocol, data['avg_score']) for protocol, data in protocol_averages.items()],
                key=lambda x: x[1],
                reverse=True
            ),
            'detailed_results': protocol_averages,
            'total_tests': len(self.results),
            'scenarios_tested': len(set(r.scenario_id for r in self.results)),
            'recommendation_confidence': self._calculate_confidence(protocol_averages, best_protocol),
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return analysis
    
    def _calculate_confidence(self, protocol_averages, best_protocol):
        """Calculate confidence level for the recommendation"""
        if len(protocol_averages) < 2:
            return 1.0
            
        scores = [data['avg_score'] for data in protocol_averages.values()]
        best_score = protocol_averages[best_protocol]['avg_score']
        second_best_score = sorted(scores, reverse=True)[1] if len(scores) > 1 else 0
        
        score_diff = best_score - second_best_score
        consistency = protocol_averages[best_protocol]['consistency']
        
        confidence = min(1.0, (score_diff / 20.0) * (consistency / 100.0) + 0.5)
        return round(confidence, 3)
    
    def save_test_results(self, analysis):
        """Save test results to file"""
        os.makedirs('data/test_results', exist_ok=True)
        filename = f"data/test_results/auto_test_{int(time.time())}.json"
        
        results_data = {
            'analysis': analysis,
            'raw_results': [
                {
                    'protocol': r.protocol,
                    'scenario': r.scenario_id,
                    'pdr': r.pdr,
                    'delay': r.avg_delay,
                    'throughput': r.throughput,
                    'energy': r.energy_consumption,
                    'overhead': r.overhead,
                    'score': r.score
                }
                for r in self.results
            ],
            'scenarios': [
                {
                    'id': s.scenario_id,
                    'num_nodes': s.num_nodes,
                    'area_size': s.area_size,
                    'node_speed': s.node_speed,
                    'pause_time': s.pause_time,
                    'tx_range': s.tx_range,
                    'traffic_load': s.traffic_load
                }
                for s in self.scenarios
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
    
    def stop_testing(self):
        """Stop the current testing process"""
        config.set_stop()
        self.testing_active = False
        return {"status": "stopping"}
    
    def get_current_status(self):
        """Get current testing status"""
        return {
            'active': self.testing_active,
            'current_protocol': self.current_protocol,
            'current_scenario': self.current_scenario.scenario_id if self.current_scenario else None,
            'total_results': len(self.results)
        }