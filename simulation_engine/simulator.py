# File: simulation_engine/simulator.py
# CORRECTED SIMULATION ENGINE

import simpy
import random
import math
import time
from typing import Dict, List, Tuple, Optional
import json
from datetime import datetime
from .manet_models import Node, Packet
from .protocols import AODV, DSDV, DSR, OLSR
from .config import stop_simulation_flag

class MANETSimulator:
    """CORRECTED MANET Simulator with proper routing and metrics"""
    
    def __init__(self, num_nodes: int, area_width: int, area_height: int, 
                 transmission_range: int, simulation_time: int, mobility_model: str):
        self.num_nodes = num_nodes
        self.area_width = area_width
        self.area_height = area_height
        self.transmission_range = transmission_range
        self.simulation_time = simulation_time
        self.mobility_model = mobility_model
        
        # Simulation state
        self.env = None
        self.nodes = []
        self.routing = None
        self.stop_flag = False
        
        # Enhanced metrics tracking
        self.metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'packets_delivered': 0,
            'packets_dropped': 0,
            'total_delay': 0.0,
            'routing_packets_sent': 0,
            'data_packets_sent': 0,
            'energy_consumed': 0.0,
            'route_discoveries': 0,
            'route_discovery_time': 0.0,
            'hop_counts': [],
            'packet_loss_events': 0,
            'route_errors': 0,
            'collision_events': 0
        }
        
        # Route tracking
        self.active_routes = {}
        self.source_node_id = None
        self.destination_node_id = None
        
    def create_network_topology(self):
        """Create network nodes with proper positioning and connectivity"""
        self.nodes = []
        
        # Create nodes with better positioning
        for node_id in range(1, self.num_nodes + 1):
            # Better positioning algorithm to ensure connectivity
            if node_id == 1:
                # First node at center
                position = [self.area_width / 2, self.area_height / 2]
            else:
                # Place nodes to ensure connectivity
                attempts = 0
                while attempts < 100:  # Prevent infinite loops
                    position = [
                        random.uniform(0, self.area_width),
                        random.uniform(0, self.area_height)
                    ]
                    
                    # Check if node is too far from others
                    too_far = True
                    for existing_node in self.nodes:
                        distance = math.sqrt(
                            (position[0] - existing_node.position[0])**2 + 
                            (position[1] - existing_node.position[1])**2
                        )
                        if distance <= self.transmission_range * 1.5:  # Ensure some connectivity
                            too_far = False
                            break
                    
                    if not too_far or attempts > 50:  # Accept after 50 attempts
                        break
                    attempts += 1
            
            # Create node with proper parameters
            node = Node(
                id=node_id,
                position=position,
                area_size=[self.area_width, self.area_height],
                speed=random.uniform(1, 5),  # 1-5 m/s
                pause_time=random.uniform(1, 5),  # 1-5 seconds
                tx_range=self.transmission_range
            )
            
            # Set simulator reference
            node.simulator = self
            
            # Set mobility parameters based on model
            if self.mobility_model == 'random_walk':
                node.speed = random.uniform(1, 3)  # 1-3 m/s
            elif self.mobility_model == 'random_waypoint':
                node.speed = random.uniform(0.5, 2)  # 0.5-2 m/s
            elif self.mobility_model == 'static':
                node.speed = 0  # No movement
            
            self.nodes.append(node)
        
        print(f"Created network topology with {len(self.nodes)} nodes")
        print(f"Transmission range: {self.transmission_range}m")
        print(f"Area: {self.area_width}x{self.area_height}m")
        
        # Update neighbors for all nodes
        for node in self.nodes:
            node.update_neighbors()
        
        # Print connectivity information
        total_connections = sum(len(node.neighbors) for node in self.nodes)
        print(f"Total connections: {total_connections}")
        for i, node in enumerate(self.nodes[:5]):  # Show first 5 nodes
            print(f"Node {node.id}: {len(node.neighbors)} neighbors")
    
    def setup_protocol(self, protocol_name: str):
        """Initialize the specified routing protocol"""
        protocol_classes = {
            'AODV': AODV,
            'DSDV': DSDV,
            'DSR': DSR,
            'OLSR': OLSR
        }
        
        if protocol_name not in protocol_classes:
            raise ValueError(f"Unknown protocol: {protocol_name}")
        
        # Initialize SimPy environment first
        if self.env is None:
            self.env = simpy.Environment()
        
        # Initialize protocol
        self.routing = protocol_classes[protocol_name](self.env, self.nodes, None)
        self.routing.simulator = self  # Set simulator reference
        
        # Set routing reference in nodes
        for node in self.nodes:
            node.routing = self.routing
        
        # Update neighbors after protocol setup
        self.routing.update_neighbors()
        
        print(f"Initialized {protocol_name} protocol")
        print(f"Network connectivity after protocol setup:")
        total_connections = sum(len(node.neighbors) for node in self.nodes)
        print(f"Total connections: {total_connections}")
    
    def packet_generator(self, source_node_id: int, dest_node_id: int, packet_rate: float):
        """Generate packets from source to destination at specified rate"""
        packet_interval = 1.0 / packet_rate
        packet_id = 1
        
        source_node = None
        for node in self.nodes:
            if node.id == source_node_id:
                source_node = node
                break
        
        if not source_node:
            print(f"Source node {source_node_id} not found")
            return
        
        print(f"Starting packet generation: {source_node_id} -> {dest_node_id}")
        print(f"Packet rate: {packet_rate} packets/s")
        # Get destination node
        dest_node_obj = None
        for node in self.nodes:
            if node.id == dest_node_id:
                dest_node_obj = node
                break
        
        print(f"Source node neighbors: {len(source_node.neighbors)}")
        print(f"Destination node neighbors: {len(dest_node_obj.neighbors) if dest_node_obj else 0}")
        
        # Check if source and destination are direct neighbors
        if dest_node_obj and dest_node_obj in source_node.neighbors:
            print("Source and destination are direct neighbors!")
        else:
            print("Source and destination are NOT direct neighbors")
        
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                print("Packet generation stopped")
                break
            
            # Create packet
            packet = Packet(
                src_id=source_node_id,
                dst_id=dest_node_id,
                creation_time=self.env.now,
                size=64  # 64 bytes
            )
            
            # Send packet through routing protocol
            try:
                self.metrics['packets_sent'] += 1
                self.metrics['data_packets_sent'] += 1
                
                print(f"Generated packet {packet_id}: {source_node_id} -> {dest_node_id}")
                
                # Try to send packet directly to source node
                success = source_node.receive(packet)
                if not success:
                    self.metrics['packets_dropped'] += 1
                
            except Exception as e:
                print(f"Error sending packet {packet_id}: {e}")
                import traceback
                traceback.print_exc()
                self.metrics['packets_dropped'] += 1
            
            packet_id += 1
            
            # Wait for next packet
            yield self.env.timeout(packet_interval)
    
    def mobility_update_process(self):
        """Process for updating node positions with proper mobility"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
            
            # Update node positions based on mobility model
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                if self.mobility_model == 'random_waypoint':
                    # Random waypoint model
                    if not hasattr(node, 'destination') or node.destination is None:
                        # Choose new destination
                        node.destination = [
                            random.uniform(0, self.area_width),
                            random.uniform(0, self.area_height)
                        ]
                        node.direction = [
                            node.destination[0] - node.position[0],
                            node.destination[1] - node.position[1]
                        ]
                        # Normalize direction
                        norm = math.sqrt(node.direction[0]**2 + node.direction[1]**2)
                        if norm > 0:
                            node.direction[0] /= norm
                            node.direction[1] /= norm
                    
                    # Move towards destination
                    distance_to_dest = math.sqrt(
                        (node.destination[0] - node.position[0])**2 + 
                        (node.destination[1] - node.position[1])**2
                    )
                    
                    if distance_to_dest < 10:  # Close to destination
                        node.destination = None  # Choose new destination next time
                    else:
                        # Move towards destination
                        node.position[0] += node.direction[0] * node.speed * 0.1
                        node.position[1] += node.direction[1] * node.speed * 0.1
                        
                        # Keep within bounds
                        node.position[0] = max(0, min(self.area_width, node.position[0]))
                        node.position[1] = max(0, min(self.area_height, node.position[1]))
                
                elif self.mobility_model == 'random_walk':
                    # Random walk model
                    if random.random() < 0.1:  # 10% chance to change direction
                        angle = random.uniform(0, 2 * math.pi)
                        node.direction = [math.cos(angle), math.sin(angle)]
                    
                    # Move in current direction
                    node.position[0] += node.direction[0] * node.speed * 0.1
                    node.position[1] += node.direction[1] * node.speed * 0.1
                    
                    # Bounce off boundaries
                    if node.position[0] < 0 or node.position[0] > self.area_width:
                        node.direction[0] *= -1
                        node.position[0] = max(0, min(self.area_width, node.position[0]))
                    
                    if node.position[1] < 0 or node.position[1] > self.area_height:
                        node.direction[1] *= -1
                        node.position[1] = max(0, min(self.area_height, node.position[1]))
                
                # Update neighbors after movement
                self.routing.update_neighbors()
            
            yield self.env.timeout(0.1)  # Update every 0.1 seconds
    
    def energy_monitoring_process(self):
        """Monitor energy consumption"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
            
            # Calculate total energy consumption
            total_energy = sum(node.energy_used for node in self.nodes)
            self.metrics['energy_consumed'] = total_energy
            
            # Check for dead nodes
            dead_nodes = [node for node in self.nodes if node.energy <= 0]
            if dead_nodes:
                print(f"Dead nodes: {[node.id for node in dead_nodes]}")
            
            yield self.env.timeout(1.0)
    
    def run_simulation(self, protocol: str, source_node: int, destination_node: int, 
                      packet_rate: float = 1.0) -> Dict:
        """Run simulation with specified parameters"""
        print(f"Starting simulation: {protocol} protocol")
        print(f"Route: Node {source_node} → Node {destination_node}")
        print(f"Packet rate: {packet_rate} packets/s")
        print(f"Simulation time: {self.simulation_time} seconds")
        
        # Initialize simulation environment
        self.env = simpy.Environment()
        self.stop_flag = False
        
        # Store route information
        self.source_node_id = source_node
        self.destination_node_id = destination_node
        
        # Create network topology
        self.create_network_topology()
        
        # Setup protocol
        self.setup_protocol(protocol)
        
        # Reset metrics
        self.metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'packets_delivered': 0,
            'packets_dropped': 0,
            'total_delay': 0.0,
            'routing_packets_sent': 0,
            'data_packets_sent': 0,
            'energy_consumed': 0.0,
            'route_discoveries': 0,
            'route_discovery_time': 0.0,
            'hop_counts': [],
            'packet_loss_events': 0,
            'route_errors': 0,
            'collision_events': 0
        }
        
        # Validate source and destination nodes
        if source_node < 1 or source_node > self.num_nodes:
            raise ValueError(f"Invalid source node: {source_node}")
        if destination_node < 1 or destination_node > self.num_nodes:
            raise ValueError(f"Invalid destination node: {destination_node}")
        if source_node == destination_node:
            raise ValueError("Source and destination nodes cannot be the same")
        
        # Check if source and destination are alive
        source_node_obj = self.nodes[source_node - 1]
        dest_node_obj = self.nodes[destination_node - 1]
        
        if source_node_obj.energy <= 0:
            raise ValueError(f"Source node {source_node} is dead")
        if dest_node_obj.energy <= 0:
            raise ValueError(f"Destination node {destination_node} is dead")
        
        # Start simulation processes
        self.env.process(self.packet_generator(source_node, destination_node, packet_rate))
        self.env.process(self.mobility_update_process())
        self.env.process(self.energy_monitoring_process())
        
        # Run simulation
        start_time = time.time()
        try:
            self.env.run(until=self.simulation_time)
        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_flag = True
        
        # Calculate final metrics
        results = self.calculate_final_metrics()
        
        print(f"Simulation completed in {time.time() - start_time:.2f} seconds")
        print(f"Packets sent: {self.metrics['packets_sent']}")
        print(f"Packets received: {self.metrics['packets_received']}")
        print(f"Delivery ratio: {results['delivery_ratio']:.3f}")
        print(f"Average delay: {results['avg_delay']:.2f} ms")
        print(f"Routing overhead: {results['routing_overhead']:.3f}")
        
        return results
    
    def calculate_final_metrics(self) -> Dict:
        """Calculate final simulation metrics with proper calculations"""
        # Packet delivery ratio
        if self.metrics['packets_sent'] > 0:
            delivery_ratio = self.metrics['packets_received'] / self.metrics['packets_sent']
        else:
            delivery_ratio = 0.0
        
        # Average delay
        if self.metrics['packets_received'] > 0:
            avg_delay = (self.metrics['total_delay'] / self.metrics['packets_received']) * 1000  # Convert to ms
        else:
            avg_delay = 0.0
        
        # Routing overhead
        total_packets = self.metrics['packets_sent'] + self.metrics['routing_packets_sent']
        if total_packets > 0:
            routing_overhead = self.metrics['routing_packets_sent'] / total_packets
        else:
            routing_overhead = 0.0
        
        # Throughput (successful packets per second)
        if self.simulation_time > 0:
            throughput = (self.metrics['packets_received'] * 64 * 8) / self.simulation_time  # bits per second
        else:
            throughput = 0.0
        
        # Average hop count
        if self.metrics['hop_counts']:
            avg_hop_count = sum(self.metrics['hop_counts']) / len(self.metrics['hop_counts'])
        else:
            avg_hop_count = 0.0
        
        # Average route discovery time
        if self.metrics['route_discoveries'] > 0:
            avg_route_discovery_time = self.metrics['route_discovery_time'] / self.metrics['route_discoveries']
        else:
            avg_route_discovery_time = 0.0
        
        # Packet loss ratio
        packet_loss = 1.0 - delivery_ratio
        
        # Network connectivity
        total_possible_links = self.num_nodes * (self.num_nodes - 1) // 2
        active_links = 0
        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                node1 = self.nodes[i]
                node2 = self.nodes[j]
                if (node1.energy > 0 and node2.energy > 0 and 
                    node1.distance_to(node2) <= self.transmission_range):
                    active_links += 1
        
        connectivity_ratio = active_links / total_possible_links if total_possible_links > 0 else 0
        
        return {
            'delivery_ratio': delivery_ratio,
            'avg_delay': avg_delay,
            'routing_overhead': routing_overhead,
            'throughput': throughput,
            'energy_consumption': self.metrics['energy_consumed'],
            'route_discovery_time': avg_route_discovery_time,
            'avg_hop_count': avg_hop_count,
            'packet_loss': packet_loss,
            'total_packets_sent': self.metrics['packets_sent'],
            'total_packets_delivered': self.metrics['packets_received'],
            'total_packets_dropped': self.metrics['packets_dropped'],
            'simulation_time': self.simulation_time,
            'network_size': self.num_nodes,
            'source_node': self.source_node_id,
            'destination_node': self.destination_node_id,
            'connectivity_ratio': connectivity_ratio,
            'active_links': active_links,
            'dead_nodes': len([n for n in self.nodes if n.energy <= 0])
        }
    
    def get_network_topology_info(self) -> Dict:
        """Get current network topology information"""
        node_info = []
        for node in self.nodes:
            neighbors = [n.id for n in node.neighbors if n.energy > 0]
            node_info.append({
                'node_id': node.id,
                'position': {'x': node.position[0], 'y': node.position[1]},
                'neighbors': neighbors,
                'neighbor_count': len(neighbors),
                'energy': node.energy,
                'alive': node.energy > 0
            })
        
        return {
            'nodes': node_info,
            'total_nodes': len(self.nodes),
            'alive_nodes': len([n for n in self.nodes if n.energy > 0]),
            'area_size': {'width': self.area_width, 'height': self.area_height},
            'transmission_range': self.transmission_range,
            'mobility_model': self.mobility_model
        }
