# simulator.py 
import simpy
import random
import math
from typing import Dict, List, Tuple, Optional
import json
from datetime import datetime
from .manet_models import Node, Packet
from .protocols import AODV, DSDV, DSR, OLSR
from .config import stop_simulation_flag

class MANETSimulator:
    """Enhanced MANET Simulator with source-destination route support"""
    
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
        self.protocol_handler = None
        self.routing = None  # Add routing protocol handler
        
        # Metrics tracking
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
            'hop_counts': []
        }
        
        # Interval metrics for periodic updates
        self.interval_metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'packets_delivered': 0,
            'total_delay': 0.0
        }
        
        # Route tracking
        self.active_routes = {}
        self.source_node_id = None
        self.destination_node_id = None
        self.stop_flag = False
        
    def create_network_topology(self):
        """Create network nodes with random or configured positions"""
        self.nodes = []
        
        for node_id in range(1, self.num_nodes + 1):
            # Random position within the area
            position = [random.uniform(0, self.area_width), random.uniform(0, self.area_height)]
            area_size = [self.area_width, self.area_height]
            
            # Create node with proper parameters
            node = Node(
                id=node_id, 
                position=position, 
                area_size=area_size,
                speed=random.uniform(1, 10),
                pause_time=random.uniform(1, 10),
                tx_range=self.transmission_range
            )
            
            # Set simulator reference
            node.simulator = self
            
            # Set mobility parameters based on model
            if self.mobility_model == 'random_walk':
                node.speed = random.uniform(1, 5)  # 1-5 m/s
            elif self.mobility_model == 'random_waypoint':
                node.speed = random.uniform(0.5, 3)  # 0.5-3 m/s
            elif self.mobility_model == 'static':
                node.speed = 0  # No movement
            
            self.nodes.append(node)
        
        print(f"Created network topology with {len(self.nodes)} nodes")
    
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
        
        # Create a simple graph representation (can be None for basic protocols)
        graph = None
        
        # Initialize protocol with correct parameters
        self.routing = protocol_classes[protocol_name](self.env, self.nodes, graph)
        
        # Set routing reference in nodes
        for node in self.nodes:
            node.routing = self.routing
        
        print(f"Initialized {protocol_name} protocol")
    
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
        
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
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
                self.interval_metrics['packets_sent'] += 1
                
                # Try to route the packet
                if hasattr(self.routing, 'try_send'):
                    success = self.routing.try_send(source_node, packet)
                else:
                    # Fallback to basic send
                    self.routing.send_packet(packet)
                    success = True
                
            except Exception as e:
                print(f"Error sending packet {packet_id}: {e}")
                self.metrics['packets_dropped'] += 1
                success = False
            
            packet_id += 1
            
            # Wait for next packet
            yield self.env.timeout(packet_interval)
    
    def mobility_update_process(self):
        """Process for updating node positions"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
                
            # Start mobility processes for all nodes
            for node in self.nodes:
                if not hasattr(node, 'mobility_process_started'):
                    self.env.process(node.move(self.env))
                    node.mobility_process_started = True
            
            yield self.env.timeout(1.0)
    
    def protocol_maintenance_process(self):
        """Process for protocol maintenance tasks"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
                
            # Update neighbor lists
            if self.routing:
                self.routing.update_neighbors()
            
            # Update routing overhead
            if hasattr(self.routing, 'get_overhead'):
                self.metrics['routing_packets_sent'] = self.routing.get_overhead()
            
            yield self.env.timeout(1.0)  # Maintenance every second
    
    def energy_monitoring_process(self):
        """Monitor energy consumption"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
                
            # Calculate energy consumption for all nodes
            total_energy = 0
            for node in self.nodes:
                total_energy += node.energy_used
            
            self.metrics['energy_consumed'] = total_energy
            yield self.env.timeout(1.0)
    
    def metrics_collection_process(self):
        """Collect metrics periodically"""
        while True:
            if stop_simulation_flag.is_set() or self.stop_flag:
                break
                
            # Reset interval metrics
            self.interval_metrics = {
                'packets_sent': 0,
                'packets_received': 0,
                'packets_delivered': 0,
                'total_delay': 0.0
            }
            
            yield self.env.timeout(1.0)
    
    def run_simulation(self, protocol: str, source_node: int, destination_node: int, 
                      packet_rate: float = 1.0) -> Dict:
        """Run simulation with specified parameters"""
        print(f"Starting simulation: {protocol} protocol")
        print(f"Route: Node {source_node} → Node {destination_node}")
        print(f"Packet rate: {packet_rate} packets/s")
        
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
            'hop_counts': []
        }
        
        self.interval_metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'packets_delivered': 0,
            'total_delay': 0.0
        }
        
        # Validate source and destination nodes
        if source_node < 1 or source_node > self.num_nodes:
            raise ValueError(f"Invalid source node: {source_node}")
        if destination_node < 1 or destination_node > self.num_nodes:
            raise ValueError(f"Invalid destination node: {destination_node}")
        if source_node == destination_node:
            raise ValueError("Source and destination nodes cannot be the same")
        
        # Start simulation processes
        self.env.process(self.packet_generator(source_node, destination_node, packet_rate))
        self.env.process(self.mobility_update_process())
        self.env.process(self.protocol_maintenance_process())
        self.env.process(self.energy_monitoring_process())
        self.env.process(self.metrics_collection_process())
        
        # Run simulation
        try:
            self.env.run(until=self.simulation_time)
        except Exception as e:
            print(f"Simulation error: {e}")
        finally:
            self.stop_flag = True
        
        # Calculate final metrics
        results = self.calculate_final_metrics()
        
        print(f"Simulation completed")
        print(f"Packets sent: {self.metrics['packets_sent']}")
        print(f"Packets received: {self.metrics['packets_received']}")
        print(f"Delivery ratio: {results['delivery_ratio']:.3f}")
        
        return results
    
    def calculate_final_metrics(self) -> Dict:
        """Calculate final simulation metrics"""
        # Packet delivery ratio
        if self.metrics['packets_sent'] > 0:
            delivery_ratio = self.metrics['packets_received'] / self.metrics['packets_sent']
        else:
            delivery_ratio = 0.0
        
        # Average delay
        if self.metrics['packets_received'] > 0:
            avg_delay = (self.metrics['total_delay'] / self.metrics['packets_received'])  # in seconds
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
        
        return {
            'delivery_ratio': delivery_ratio,
            'avg_delay': avg_delay * 1000,  # Convert to milliseconds
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
            'destination_node': self.destination_node_id
        }
    
    def get_neighbors(self, node: Node) -> List[Node]:
        """Get all nodes within transmission range"""
        neighbors = []
        for other_node in self.nodes:
            if other_node.id != node.id:
                distance = node.distance_to(other_node)
                if distance <= self.transmission_range:
                    neighbors.append(other_node)
        return neighbors
    
    def get_network_topology_info(self) -> Dict:
        """Get current network topology information"""
        node_info = []
        for node in self.nodes:
            neighbors = self.get_neighbors(node)
            node_info.append({
                'node_id': node.id,
                'position': {'x': node.position[0], 'y': node.position[1]},
                'neighbors': [n.id for n in neighbors],
                'neighbor_count': len(neighbors),
                'energy': node.energy
            })
        
        return {
            'nodes': node_info,
            'total_nodes': len(self.nodes),
            'area_size': {'width': self.area_width, 'height': self.area_height},
            'transmission_range': self.transmission_range,
            'mobility_model': self.mobility_model
        }
    
    def save_simulation_state(self, filename: str):
        """Save current simulation state to file"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'configuration': {
                'num_nodes': self.num_nodes,
                'area_width': self.area_width,
                'area_height': self.area_height,
                'transmission_range': self.transmission_range,
                'simulation_time': self.simulation_time,
                'mobility_model': self.mobility_model
            },
            'metrics': self.metrics,
            'topology': self.get_network_topology_info(),
            'route': {
                'source': self.source_node_id,
                'destination': self.destination_node_id
            }
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(state, f, indent=2)
            print(f"Simulation state saved to {filename}")
        except Exception as e:
            print(f"Error saving simulation state: {e}")

class SimulationMetrics:
    """Class for tracking and analyzing simulation metrics"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics to initial state"""
        self.packet_stats = {
            'sent': 0,
            'delivered': 0,
            'dropped': 0,
            'in_transit': 0
        }
        
        self.delay_stats = {
            'total_delay': 0.0,
            'min_delay': float('inf'),
            'max_delay': 0.0,
            'delays': []
        }
        
        self.routing_stats = {
            'route_requests': 0,
            'route_replies': 0,
            'route_errors': 0,
            'routing_overhead': 0,
            'active_routes': 0
        }
        
        self.energy_stats = {
            'total_consumed': 0.0,
            'transmission_energy': 0.0,
            'reception_energy': 0.0,
            'idle_energy': 0.0
        }
        
        self.hop_stats = {
            'hop_counts': [],
            'total_hops': 0,
            'min_hops': float('inf'),
            'max_hops': 0
        }
    
    def record_packet_sent(self):
        """Record a packet being sent"""
        self.packet_stats['sent'] += 1
    
    def record_packet_delivered(self, delay: float, hop_count: int = 0):
        """Record a packet being successfully delivered"""
        self.packet_stats['delivered'] += 1
        
        # Record delay
        self.delay_stats['total_delay'] += delay
        self.delay_stats['delays'].append(delay)
        self.delay_stats['min_delay'] = min(self.delay_stats['min_delay'], delay)
        self.delay_stats['max_delay'] = max(self.delay_stats['max_delay'], delay)
        
        # Record hop count
        if hop_count > 0:
            self.hop_stats['hop_counts'].append(hop_count)
            self.hop_stats['total_hops'] += hop_count
            self.hop_stats['min_hops'] = min(self.hop_stats['min_hops'], hop_count)
            self.hop_stats['max_hops'] = max(self.hop_stats['max_hops'], hop_count)
    
    def record_packet_dropped(self):
        """Record a packet being dropped"""
        self.packet_stats['dropped'] += 1
    
    def record_routing_overhead(self, control_packets: int):
        """Record routing control packets"""
        self.routing_stats['routing_overhead'] += control_packets
    
    def record_energy_consumption(self, tx_energy: float, rx_energy: float, idle_energy: float):
        """Record energy consumption"""
        self.energy_stats['transmission_energy'] += tx_energy
        self.energy_stats['reception_energy'] += rx_energy
        self.energy_stats['idle_energy'] += idle_energy
        self.energy_stats['total_consumed'] = (
            self.energy_stats['transmission_energy'] + 
            self.energy_stats['reception_energy'] + 
            self.energy_stats['idle_energy']
        )
    
    def get_delivery_ratio(self) -> float:
        """Calculate packet delivery ratio"""
        if self.packet_stats['sent'] == 0:
            return 0.0
        return self.packet_stats['delivered'] / self.packet_stats['sent']
    
    def get_average_delay(self) -> float:
        """Calculate average packet delay"""
        if not self.delay_stats['delays']:
            return 0.0
        return sum(self.delay_stats['delays']) / len(self.delay_stats['delays'])
    
    def get_average_hop_count(self) -> float:
        """Calculate average hop count"""
        if not self.hop_stats['hop_counts']:
            return 0.0
        return sum(self.hop_stats['hop_counts']) / len(self.hop_stats['hop_counts'])
    
    def get_routing_overhead_ratio(self) -> float:
        """Calculate routing overhead ratio"""
        total_packets = self.packet_stats['sent'] + self.routing_stats['routing_overhead']
        if total_packets == 0:
            return 0.0
        return self.routing_stats['routing_overhead'] / total_packets
    
    def get_comprehensive_report(self) -> Dict:
        """Get comprehensive metrics report"""
        return {
            'packet_delivery_ratio': self.get_delivery_ratio(),
            'average_delay_ms': self.get_average_delay() * 1000,  # Convert to ms
            'min_delay_ms': self.delay_stats['min_delay'] * 1000 if self.delay_stats['min_delay'] != float('inf') else 0,
            'max_delay_ms': self.delay_stats['max_delay'] * 1000,
            'average_hop_count': self.get_average_hop_count(),
            'min_hop_count': self.hop_stats['min_hops'] if self.hop_stats['min_hops'] != float('inf') else 0,
            'max_hop_count': self.hop_stats['max_hops'],
            'routing_overhead_ratio': self.get_routing_overhead_ratio(),
            'total_energy_consumption': self.energy_stats['total_consumed'],
            'packets_sent': self.packet_stats['sent'],
            'packets_delivered': self.packet_stats['delivered'],
            'packets_dropped': self.packet_stats['dropped'],
            'packet_loss_ratio': 1.0 - self.get_delivery_ratio()
        }

class RouteAnalyzer:
    """Analyze routes and network connectivity"""
    
    def __init__(self, nodes: List[Node], get_neighbors_func):
        self.nodes = nodes
        self.get_neighbors = get_neighbors_func
        self.connectivity_matrix = None
        self.shortest_paths = {}
    
    def build_connectivity_matrix(self):
        """Build network connectivity matrix"""
        n = len(self.nodes)
        self.connectivity_matrix = [[False for _ in range(n)] for _ in range(n)]
        
        for i, node in enumerate(self.nodes):
            neighbors = self.get_neighbors(node)
            for neighbor in neighbors:
                j = neighbor.id - 1  # Convert to 0-based index
                if 0 <= j < n:
                    self.connectivity_matrix[i][j] = True
                    self.connectivity_matrix[j][i] = True  # Bidirectional links
    
    def find_shortest_path(self, source_id: int, dest_id: int) -> List[int]:
        """Find shortest path using Dijkstra's algorithm"""
        if not self.connectivity_matrix:
            self.build_connectivity_matrix()
        
        n = len(self.nodes)
        source_idx = source_id - 1
        dest_idx = dest_id - 1
        
        if source_idx < 0 or source_idx >= n or dest_idx < 0 or dest_idx >= n:
            return []
        
        # Dijkstra's algorithm
        distances = [float('inf')] * n
        previous = [-1] * n
        visited = [False] * n
        
        distances[source_idx] = 0
        
        for _ in range(n):
            # Find minimum distance unvisited node
            min_dist = float('inf')
            min_node = -1
            
            for i in range(n):
                if not visited[i] and distances[i] < min_dist:
                    min_dist = distances[i]
                    min_node = i
            
            if min_node == -1:
                break
            
            visited[min_node] = True
            
            # Update distances to neighbors
            for i in range(n):
                if (self.connectivity_matrix[min_node][i] and 
                    not visited[i] and 
                    distances[min_node] + 1 < distances[i]):
                    distances[i] = distances[min_node] + 1
                    previous[i] = min_node
        
        # Reconstruct path
        if distances[dest_idx] == float('inf'):
            return []  # No path exists
        
        path = []
        current = dest_idx
        while current != -1:
            path.append(current + 1)  # Convert back to 1-based node IDs
            current = previous[current]
        
        path.reverse()
        return path
    
    def analyze_network_connectivity(self) -> Dict:
        """Analyze overall network connectivity"""
        if not self.connectivity_matrix:
            self.build_connectivity_matrix()
        
        n = len(self.nodes)
        total_connections = sum(sum(row) for row in self.connectivity_matrix) // 2  # Divide by 2 for undirected graph
        max_connections = n * (n - 1) // 2
        
        # Check if network is connected (can reach all nodes from any node)
        visited = [False] * n
        def dfs(node_idx):
            visited[node_idx] = True
            for i in range(n):
                if self.connectivity_matrix[node_idx][i] and not visited[i]:
                    dfs(i)
        
        if n > 0:
            dfs(0)
        is_connected = all(visited)
        
        # Calculate node degrees
        node_degrees = []
        for i in range(n):
            degree = sum(self.connectivity_matrix[i])
            node_degrees.append(degree)
        
        return {
            'is_connected': is_connected,
            'total_links': total_connections,
            'max_possible_links': max_connections,
            'connectivity_ratio': total_connections / max_connections if max_connections > 0 else 0,
            'average_node_degree': sum(node_degrees) / len(node_degrees) if node_degrees else 0,
            'min_node_degree': min(node_degrees) if node_degrees else 0,
            'max_node_degree': max(node_degrees) if node_degrees else 0,
            'isolated_nodes': sum(1 for degree in node_degrees if degree == 0)
        }
    
    def get_route_quality_metrics(self, source_id: int, dest_id: int) -> Dict:
        """Get quality metrics for a specific route"""
        path = self.find_shortest_path(source_id, dest_id)
        
        if not path:
            return {
                'path_exists': False,
                'hop_count': -1,
                'path_reliability': 0.0,
                'bottleneck_capacity': 0.0
            }
        
        # Calculate path reliability (simplified)
        # Assumes each link has 95% reliability
        link_reliability = 0.95
        path_reliability = link_reliability ** (len(path) - 1)
        
        # Calculate bottleneck capacity (minimum neighbor count along path)
        bottleneck_capacity = float('inf')
        for i in range(len(path) - 1):
            node = self.nodes[path[i] - 1]  # Convert to 0-based index
            neighbors = self.get_neighbors(node)
            capacity = len(neighbors)
            bottleneck_capacity = min(bottleneck_capacity, capacity)
        
        if bottleneck_capacity == float('inf'):
            bottleneck_capacity = 0
        
        return {
            'path_exists': True,
            'hop_count': len(path) - 1,
            'path': path,
            'path_reliability': path_reliability,
            'bottleneck_capacity': bottleneck_capacity
        }