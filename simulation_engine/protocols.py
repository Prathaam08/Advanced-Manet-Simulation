# File: simulation_engine/protocols.py

import simpy
from collections import defaultdict, deque
import time
import random
from . import config

class BaseRouting:
    def __init__(self, env, nodes, graph):
        self.env = env
        self.nodes = nodes
        self.node_map = {node.id: node for node in nodes}
        self.graph = graph
        self.routing_overhead = 0
        self.packet_queue = defaultdict(deque)
        self.route_tables = {node.id: {} for node in nodes}
        self.seq_numbers = {node.id: 0 for node in nodes}
        
    def update_neighbors(self):
        """Update neighbor lists for all nodes"""
        for node in self.nodes:
            node.update_neighbors()
    
    def send_packet(self, packet):
        """Send packet through the network"""
        if packet.src_id not in self.node_map:
            return False
            
        src_node = self.node_map[packet.src_id]
        if src_node.energy <= 0:
            return False
            
        # Add to packet queue
        self.packet_queue[src_node.id].append(packet)
        
        # Start routing handler if not running
        if not getattr(src_node, 'routing_handler_running', False):
            src_node.routing_handler_running = True
            # Process packets immediately
            self._process_packets_immediately(src_node)
        
        return True
    
    def _process_packets_immediately(self, node):
        """Process packets immediately without using generator"""
        while self.packet_queue[node.id] and node.energy > 0:
            packet = self.packet_queue[node.id].popleft()
            
            # Check if packet reached destination
            if packet.dst_id == node.id:
                self._deliver_packet(packet, node)
                continue
            
            # Try to route packet
            routed = self._route_packet_sync(node, packet)
            if routed:
                continue
            else:
                # Route discovery needed
                self._initiate_route_discovery_sync(node, packet)
        
        node.routing_handler_running = False
    
    def _handle_packets(self, node):
        """Handle packets in the queue for a specific node"""
        while self.packet_queue[node.id] and node.energy > 0:
            packet = self.packet_queue[node.id].popleft()
            
            # Check if packet reached destination
            if packet.dst_id == node.id:
                self._deliver_packet(packet, node)
                continue
            
            # Try to route packet
            routed = yield from self._route_packet(node, packet)
            if routed:
                continue
            else:
                # Route discovery needed
                self._initiate_route_discovery(node, packet)
        
        node.routing_handler_running = False
    
    def _deliver_packet(self, packet, dest_node):
        """Deliver packet to destination"""
        packet.delivery_time = self.env.now
        delay = packet.delivery_time - packet.creation_time
        
        # Update metrics
        if hasattr(self, 'simulator'):
            self.simulator.metrics['packets_received'] += 1
            self.simulator.metrics['total_delay'] += delay
            self.simulator.metrics['hop_counts'].append(len(packet.hops))
        
        # Consume energy for reception
        dest_node.consume_energy(0.05)
    
    def _route_packet(self, node, packet):
        """Try to route packet using existing route"""
        # Check if we have a route to destination
        if packet.dst_id in node.routing_table:
            next_hop_id = node.routing_table[packet.dst_id]
            next_hop_node = self.node_map.get(next_hop_id)
            
            if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                # Forward packet
                packet.hops.append(node.id)
                packet.last_hop = node.id
                
                # Consume energy for transmission
                node.consume_energy(0.1)
                
                # Add transmission delay
                yield self.env.timeout(packet.size / (2 * 1024))  # 2 Mbps
                
                # Forward to next hop
                yield from self._forward_packet_to_node(next_hop_node, packet)
                return True
        
        return False
    
    def _route_packet_sync(self, node, packet):
        """Synchronous version of route packet"""
        # Check if we have a route to destination
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop_id = route_info['next_hop']
            else:
                next_hop_id = route_info
            
            next_hop_node = self.node_map.get(next_hop_id)
            
            if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                # Consume energy for transmission
                node.consume_energy(0.1)
                
                # Add transmission delay to packet
                transmission_delay = 0.001 + (packet.size / 1000000.0)
                packet.transmission_delay = getattr(packet, 'transmission_delay', 0) + transmission_delay
                
                # Track routing overhead
                if hasattr(self, 'simulator') and self.simulator:
                    self.simulator.metrics['routing_packets_sent'] += 1
                
                # Forward directly to next hop
                success = next_hop_node.receive(packet)
                return success
        
        return False
    
    def _try_route_through_neighbor(self, node, neighbor, packet):
        """Try to route packet through a specific neighbor"""
        # Set up route through this neighbor
        node.routing_table[packet.dst_id] = neighbor.id
        self.route_tables[node.id][packet.dst_id] = {
            'next_hop': neighbor.id,
            'hop_count': 1,
            'expiry': self.env.now + 30.0
        }
        
        # Forward packet directly to neighbor
        node.consume_energy(0.1)
        
        # Add transmission delay to packet
        transmission_delay = 0.001 + (packet.size / 1000000.0)
        packet.transmission_delay = getattr(packet, 'transmission_delay', 0) + transmission_delay
        
        # Track routing overhead (this is a routing decision)
        if hasattr(self, 'simulator') and self.simulator:
            self.simulator.metrics['routing_packets_sent'] += 1
        
        success = neighbor.receive(packet)
        return success
    
    def _initiate_route_discovery_sync(self, node, packet):
        """Synchronous version of route discovery"""
        # Check if destination is a direct neighbor
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # This will be implemented by specific protocols
        return False
    
    def _initiate_route_discovery(self, node, packet):
        """Initiate route discovery process"""
        # Check if destination is a direct neighbor
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet(node, packet)
        
        # This will be implemented by specific protocols
        pass
    
    def _forward_packet_to_node(self, next_hop_node, packet):
        """Forward packet to next hop node"""
        if next_hop_node.energy <= 0:
            return
        
        # Add packet to next hop's queue
        self.packet_queue[next_hop_node.id].append(packet)
        
        # Start routing handler if not running
        if not getattr(next_hop_node, 'routing_handler_running', False):
            next_hop_node.routing_handler_running = True
            yield from self._handle_packets(next_hop_node)
    
    def get_overhead(self):
        return self.routing_overhead
    
    def get_next_hop(self, current_id, destination_id):
        """Get next hop for routing"""
        table = self.route_tables.get(current_id, {})
        entry = table.get(destination_id)
        
        if isinstance(entry, dict):
            return entry.get('next_hop')
        return entry


class AODV(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.rreq_id = 0
        self.pending_packets = defaultdict(list)
        self.route_requests = {}  # Track active route requests
        self.route_replies = {}   # Track route replies
        self.route_timeouts = {}  # Track route timeouts
        
        # Start periodic processes
        self.env.process(self._periodic_neighbor_update())
        self.env.process(self._route_maintenance())
    
    def _initiate_route_discovery_sync(self, node, packet):
        """AODV synchronous route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # For AODV, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet_sync(node, packet)
        
        # AODV is reactive - try to find a route through neighbors
        # Simple flooding approach for now
        for neighbor in node.neighbors:
            if neighbor.energy > 0 and neighbor.id != packet.src_id:
                # Try to route through this neighbor
                if self._try_route_through_neighbor(node, neighbor, packet):
                    return True
        
        # No route found
        return False
    
    def _periodic_neighbor_update(self):
        """Periodically update neighbor lists"""
        while not config.get_stop_simulation():
            self.update_neighbors()
            yield self.env.timeout(1.0)
    
    def _route_maintenance(self):
        """Maintain routes and handle timeouts"""
        while not config.get_stop_simulation():
            current_time = self.env.now
            
            # Remove expired routes
            for node_id, routes in list(self.route_tables.items()):
                for dest_id, route_info in list(routes.items()):
                    if isinstance(route_info, dict) and 'expiry' in route_info:
                        if current_time > route_info['expiry']:
                            del routes[dest_id]
                            node = self.node_map.get(node_id)
                            if node and dest_id in node.routing_table:
                                del node.routing_table[dest_id]
            
            yield self.env.timeout(5.0)
    
    def _initiate_route_discovery(self, node, packet):
        """Initiate AODV route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet(node, packet)
        
        # Check if we already have a pending request
        key = (node.id, packet.dst_id)
        if key in self.route_requests:
            # Add packet to pending list
            self.pending_packets[key].append(packet)
            return
        
        # Create new route request
        self.rreq_id += 1
        rreq = {
            'src_id': node.id,
            'dst_id': packet.dst_id,
            'rreq_id': self.rreq_id,
            'src_seq': self.seq_numbers[node.id],
            'dst_seq': 0,
            'hop_count': 0,
            'ttl': 7,  # Initial TTL
            'timestamp': self.env.now
        }
        
        # Store pending packet
        self.pending_packets[key].append(packet)
        self.route_requests[key] = rreq
        
        # Broadcast RREQ
        self.env.process(self._broadcast_rreq(rreq, node))
    
    def _broadcast_rreq(self, rreq, node):
        """Broadcast route request to neighbors"""
        if node.energy <= 0:
            return
        
        self.routing_overhead += 1
        node.consume_energy(0.1)  # Energy for RREQ transmission
        
        # Add small delay for transmission
        yield self.env.timeout(0.01)
        
        # Forward to all neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0:
                self.env.process(self._process_rreq(rreq.copy(), neighbor, node.id))
    
    def _process_rreq(self, rreq, node, last_hop):
        """Process received route request"""
        if node.energy <= 0:
            return
        
        rreq['hop_count'] += 1
        rreq['ttl'] -= 1
        
        # Check if we're the destination
        if node.id == rreq['dst_id']:
            # Send route reply
            self.env.process(self._send_rrep(rreq, node))
            return
        
        # Check TTL
        if rreq['ttl'] <= 0:
            return
        
        # Update route to source
        self._update_route(node.id, rreq['src_id'], last_hop, rreq['hop_count'])
        
        # Check if we have a route to destination
        if rreq['dst_id'] in node.routing_table:
            # Send route reply
            self.env.process(self._send_rrep(rreq, node))
            return
        
        # Forward RREQ to neighbors (except sender)
        for neighbor in node.neighbors:
            if neighbor.id != last_hop and neighbor.energy > 0:
                self.env.process(self._process_rreq(rreq.copy(), neighbor, node.id))
    
    def _send_rrep(self, rreq, node):
        """Send route reply back to source"""
        if node.energy <= 0:
            return
        
        # Create route reply
        rrep = {
            'src_id': rreq['src_id'],
            'dst_id': rreq['dst_id'],
            'dst_seq': self.seq_numbers[node.id],
            'hop_count': 0,
            'timestamp': self.env.now
        }
        
        self.routing_overhead += 1
        node.consume_energy(0.1)
        
        # Send RREP back to source
        self.env.process(self._forward_rrep(rrep, node, rreq['src_id']))
    
    def _forward_rrep(self, rrep, node, dest_id):
        """Forward route reply to destination"""
        if node.energy <= 0:
            return
        
        rrep['hop_count'] += 1
        
        # Check if we reached the source
        if node.id == dest_id:
            # Route established, send pending packets
            key = (dest_id, rrep['dst_id'])
            if key in self.pending_packets:
                pending = self.pending_packets.pop(key, [])
                for packet in pending:
                    self.send_packet(packet)
                del self.route_requests[key]
            return
        
        # Find next hop to source
        if dest_id in node.routing_table:
            next_hop_id = node.routing_table[dest_id]
            next_hop_node = self.node_map.get(next_hop_id)
            
            if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                # Forward RREP
                yield self.env.timeout(0.01)
                self.env.process(self._forward_rrep(rrep, next_hop_node, dest_id))
    
    def _update_route(self, node_id, dest_id, next_hop, hop_count):
        """Update routing table entry"""
        self.route_tables.setdefault(node_id, {})
        self.route_tables[node_id][dest_id] = {
            'next_hop': next_hop,
            'hop_count': hop_count,
            'expiry': self.env.now + 30.0  # 30 second timeout
        }
        
        # Update node routing table
        node = self.node_map.get(node_id)
        if node:
            node.routing_table[dest_id] = next_hop


class DSDV(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        
        # Initialize routing tables with self routes
        for node in self.nodes:
            self.route_tables[node.id][node.id] = {
                'next_hop': node.id,
                'metric': 0,
                'seq_num': 0,
                'timestamp': self.env.now
            }
        
        # Start periodic processes
        self.env.process(self._periodic_neighbor_update())
        self.env.process(self._periodic_update())
        self.env.process(self._triggered_update())
    
    def _initiate_route_discovery_sync(self, node, packet):
        """DSDV synchronous route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'metric': 1,
                'seq_num': self.seq_numbers[node.id],
                'timestamp': self.env.now
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # For DSDV, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet_sync(node, packet)
        
        # DSDV is proactive - try to find route through neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0 and neighbor.id != packet.src_id:
                # Try to route through this neighbor
                if self._try_route_through_neighbor(node, neighbor, packet):
                    return True
        
        # No route found
        return False
    
    def _initiate_route_discovery(self, node, packet):
        """Initiate DSDV route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'metric': 1,
                'seq_num': self.seq_numbers[node.id],
                'timestamp': self.env.now
            }
            # Try routing again
            return self._route_packet(node, packet)
        
        # For DSDV, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet(node, packet)
        
        # DSDV is proactive, so routes should already exist
        # If no route exists, packet will be dropped
        return False
    
    def _periodic_neighbor_update(self):
        """Update neighbor lists periodically"""
        while not config.get_stop_simulation():
            self.update_neighbors()
            yield self.env.timeout(2.0)
    
    def _periodic_update(self):
        """Periodic routing table updates"""
        while not config.get_stop_simulation():
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                # Increment sequence number
                self.seq_numbers[node.id] += 1
                
                # Broadcast routing table to neighbors
                for neighbor in node.neighbors:
                    if neighbor.energy > 0:
                        self.env.process(self._send_update(node, neighbor))
            
            yield self.env.timeout(15.0)  # 15 second update interval
    
    def _triggered_update(self):
        """Triggered updates when topology changes"""
        while not config.get_stop_simulation():
            # Check for topology changes
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                # Check if any routes need updating
                for dest_id, route_info in list(self.route_tables[node.id].items()):
                    if isinstance(route_info, dict):
                        next_hop = route_info.get('next_hop')
                        if next_hop and next_hop != node.id:
                            next_hop_node = self.node_map.get(next_hop)
                            if not next_hop_node or next_hop_node.energy <= 0 or next_hop_node not in node.neighbors:
                                # Route broken, mark as unreachable
                                self.route_tables[node.id][dest_id] = {
                                    'next_hop': None,
                                    'metric': float('inf'),
                                    'seq_num': self.seq_numbers[node.id],
                                    'timestamp': self.env.now
                                }
                                node.routing_table[dest_id] = None
                                
                                # Send triggered update
                                for neighbor in node.neighbors:
                                    if neighbor.energy > 0:
                                        self.env.process(self._send_update(node, neighbor))
            
            yield self.env.timeout(1.0)
    
    def _send_update(self, src_node, dest_node):
        """Send routing update to neighbor"""
        if src_node.energy <= 0 or dest_node.energy <= 0:
            return
        
        # Create update message
        update_msg = {
            'src_id': src_node.id,
            'seq_num': self.seq_numbers[src_node.id],
            'routes': {}
        }
        
        # Include all routes
        for dest_id, route_info in self.route_tables[src_node.id].items():
            if isinstance(route_info, dict):
                update_msg['routes'][dest_id] = {
                    'metric': route_info.get('metric', float('inf')),
                    'seq_num': route_info.get('seq_num', 0)
                }
        
        self.routing_overhead += 1
        src_node.consume_energy(0.1)
        
        # Process update at destination
        yield self.env.timeout(0.01)
        self.env.process(self._process_update(update_msg, dest_node))
    
    def _process_update(self, update_msg, node):
        """Process received routing update"""
        if node.energy <= 0:
            return
        
        src_id = update_msg['src_id']
        src_seq = update_msg['seq_num']
        updated = False
        
        # Update routes based on received information
        for dest_id, route_info in update_msg['routes'].items():
            received_metric = route_info['metric']
            received_seq = route_info['seq_num']
            
            if received_metric == float('inf'):
                # Route is unreachable
                if dest_id in self.route_tables[node.id]:
                    current_route = self.route_tables[node.id][dest_id]
                    if isinstance(current_route, dict) and current_route.get('next_hop') == src_id:
                        # Remove route through this neighbor
                        del self.route_tables[node.id][dest_id]
                        if dest_id in node.routing_table:
                            del node.routing_table[dest_id]
                        updated = True
            else:
                # Calculate new metric
                new_metric = received_metric + 1
                current_route = self.route_tables[node.id].get(dest_id, {})
                
                if isinstance(current_route, dict):
                    current_metric = current_route.get('metric', float('inf'))
                    current_seq = current_route.get('seq_num', 0)
                else:
                    current_metric = float('inf')
                    current_seq = 0
                
                # Update if better route or newer sequence number
                if (new_metric < current_metric or 
                    (new_metric == current_metric and received_seq > current_seq) or
                    received_seq > current_seq):
                    
                    self.route_tables[node.id][dest_id] = {
                        'next_hop': src_id,
                        'metric': new_metric,
                        'seq_num': received_seq,
                        'timestamp': self.env.now
                    }
                    node.routing_table[dest_id] = src_id
                    updated = True
        
        # Send triggered update if we made changes
        if updated:
            self.seq_numbers[node.id] += 1
            for neighbor in node.neighbors:
                if neighbor.id != src_id and neighbor.energy > 0:
                    self.env.process(self._send_update(node, neighbor))


class DSR(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.route_cache = {}  # Cache for discovered routes
        self.route_requests = {}  # Active route requests
        self.route_replies = {}  # Route replies
        self.pending_packets = defaultdict(list)  # Packets waiting for route discovery
        
        # Start periodic processes
        self.env.process(self._periodic_neighbor_update())
        self.env.process(self._cache_maintenance())
    
    def _initiate_route_discovery_sync(self, node, packet):
        """DSR synchronous route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # Check cache first
        key = (node.id, packet.dst_id)
        if key in self.route_cache:
            route = self.route_cache[key]['route']
            if self._validate_route(route):
                # Use cached route
                self._setup_route(route)
                return self._route_packet_sync(node, packet)
        
        # DSR is reactive - try to find route through neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0 and neighbor.id != packet.src_id:
                # Try to route through this neighbor
                if self._try_route_through_neighbor(node, neighbor, packet):
                    return True
        
        # No route found
        return False
    
    def _periodic_neighbor_update(self):
        """Update neighbor lists periodically"""
        while not config.get_stop_simulation():
            self.update_neighbors()
            yield self.env.timeout(1.0)
    
    def _cache_maintenance(self):
        """Maintain route cache"""
        while not config.get_stop_simulation():
            current_time = self.env.now
            
            # Remove expired routes from cache
            for key, route_info in list(self.route_cache.items()):
                if current_time > route_info.get('expiry', current_time + 300):
                    del self.route_cache[key]
            
            yield self.env.timeout(30.0)
    
    def _initiate_route_discovery(self, node, packet):
        """Initiate DSR route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'hop_count': 1,
                'expiry': self.env.now + 30.0
            }
            # Try routing again
            return self._route_packet(node, packet)
        
        # Check cache first
        key = (node.id, packet.dst_id)
        if key in self.route_cache:
            route = self.route_cache[key]['route']
            if self._validate_route(route):
                # Use cached route
                self._setup_route(route)
                self.send_packet(packet)
                return
        
        # Start route discovery
        yield from self._route_discovery(node, packet)
    
    def _route_discovery(self, node, packet):
        """DSR route discovery process"""
        if node.energy <= 0:
            return
        
        # Create route request
        rreq_id = random.randint(1, 1000000)
        rreq = {
            'src_id': node.id,
            'dst_id': packet.dst_id,
            'rreq_id': rreq_id,
            'path': [node.id],
            'timestamp': self.env.now
        }
        
        # Store pending packet
        key = (node.id, packet.dst_id)
        self.pending_packets[key].append(packet)
        
        # Broadcast route request
        self.routing_overhead += 1
        node.consume_energy(0.1)
        
        # Add small delay for transmission
        yield self.env.timeout(0.01)
        
        for neighbor in node.neighbors:
            if neighbor.energy > 0:
                self.env.process(self._process_route_request(rreq.copy(), neighbor))
    
    def _process_route_request(self, rreq, node):
        """Process received route request"""
        if node.energy <= 0:
            return
        
        # Check if we're the destination
        if node.id == rreq['dst_id']:
            # Send route reply
            self.env.process(self._send_route_reply(rreq, node))
            return
        
        # Check if we have a route to destination
        key = (node.id, rreq['dst_id'])
        if key in self.route_cache:
            cached_route = self.route_cache[key]['route']
            if self._validate_route(cached_route):
                # Send route reply with cached route
                full_route = rreq['path'] + cached_route[1:]  # Skip first node (current node)
                self.env.process(self._send_route_reply_with_route(rreq, node, full_route))
                return
        
        # Add ourselves to path and forward
        rreq['path'].append(node.id)
        
        # Forward to neighbors (avoid loops)
        for neighbor in node.neighbors:
            if neighbor.id not in rreq['path'] and neighbor.energy > 0:
                self.env.process(self._process_route_request(rreq.copy(), neighbor))
    
    def _send_route_reply(self, rreq, node):
        """Send route reply back to source"""
        if node.energy <= 0:
            return
        
        # Create route reply
        rrep = {
            'src_id': rreq['src_id'],
            'dst_id': rreq['dst_id'],
            'path': rreq['path'][::-1],  # Reverse path
            'timestamp': self.env.now
        }
        
        # Send back to source
        self.env.process(self._forward_route_reply(rrep, node, rreq['src_id']))
    
    def _send_route_reply_with_route(self, rreq, node, route):
        """Send route reply with specific route"""
        if node.energy <= 0:
            return
        
        # Create route reply with route
        rrep = {
            'src_id': rreq['src_id'],
            'dst_id': rreq['dst_id'],
            'path': route,
            'timestamp': self.env.now
        }
        
        # Send back to source
        self.env.process(self._forward_route_reply(rrep, node, rreq['src_id']))
    
    def _forward_route_reply(self, rrep, node, dest_id):
        """Forward route reply to destination"""
        if node.energy <= 0:
            return
        
        # Check if we reached the source
        if node.id == dest_id:
            # Route discovered, cache it and send pending packets
            key = (dest_id, rrep['dst_id'])
            self.route_cache[key] = {
                'route': rrep['path'],
                'expiry': self.env.now + 300.0  # 5 minute cache
            }
            
            # Send pending packets
            if key in self.pending_packets:
                pending = self.pending_packets.pop(key, [])
                for packet in pending:
                    self.send_packet(packet)
            return
        
        # Find next hop in path
        if dest_id in rrep['path']:
            idx = rrep['path'].index(dest_id)
            if idx > 0:
                next_hop_id = rrep['path'][idx - 1]
                next_hop_node = self.node_map.get(next_hop_id)
                
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    yield self.env.timeout(0.01)
                    self.env.process(self._forward_route_reply(rrep, next_hop_node, dest_id))
    
    def _validate_route(self, route):
        """Validate if route is still valid"""
        for i in range(len(route) - 1):
            current_id = route[i]
            next_id = route[i + 1]
            
            current_node = self.node_map.get(current_id)
            next_node = self.node_map.get(next_id)
            
            if not current_node or not next_node:
                return False
            
            if (next_node not in current_node.neighbors or 
                current_node.energy <= 0 or next_node.energy <= 0):
                return False
        
        return True
    
    def _setup_route(self, route):
        """Setup routing tables based on route"""
        for i in range(len(route) - 1):
            current_id = route[i]
            next_id = route[i + 1]
            
            current_node = self.node_map.get(current_id)
            if current_node:
                current_node.routing_table[route[-1]] = next_id


class OLSR(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.mpr_selectors = {}  # Nodes that selected this node as MPR
        self.mprs = {}  # MPR sets for each node
        self.topology_table = {}  # Network topology information
        self.tc_messages = {}  # Topology control messages
        
        # Start periodic processes
        self.env.process(self._periodic_neighbor_update())
        self.env.process(self._hello_messages())
        self.env.process(self._tc_messages())
        self.env.process(self._mpr_selection())
    
    def _initiate_route_discovery_sync(self, node, packet):
        """OLSR synchronous route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'metric': 1,
                'timestamp': self.env.now
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # For OLSR, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet_sync(node, packet)
        
        # OLSR is proactive - try to find route through neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0 and neighbor.id != packet.src_id:
                # Try to route through this neighbor
                if self._try_route_through_neighbor(node, neighbor, packet):
                    return True
        
        # No route found
        return False
    
    def _initiate_route_discovery_sync(self, node, packet):
        """OLSR-specific synchronous route discovery"""
        # Check if destination is a direct neighbor
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'metric': 1,
                'timestamp': self.env.now
            }
            # Try routing again
            return self._route_packet_sync(node, packet)
        
        # For OLSR, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet_sync(node, packet)
        
        # OLSR is proactive - try to find route through neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0 and neighbor.id != packet.src_id:
                # Try to route through this neighbor
                if self._try_route_through_neighbor(node, neighbor, packet):
                    return True
        
        # No route found
        return False
    
    def _initiate_route_discovery(self, node, packet):
        """Initiate OLSR route discovery"""
        # Check if destination is a direct neighbor first
        dest_node = self.node_map.get(packet.dst_id)
        if dest_node and dest_node in node.neighbors and dest_node.energy > 0:
            # Direct neighbor - set up direct route
            node.routing_table[packet.dst_id] = packet.dst_id
            self.route_tables[node.id][packet.dst_id] = {
                'next_hop': packet.dst_id,
                'metric': 1,
                'timestamp': self.env.now
            }
            # Try routing again
            return self._route_packet(node, packet)
        
        # For OLSR, try to find route through routing table
        if packet.dst_id in self.route_tables[node.id]:
            route_info = self.route_tables[node.id][packet.dst_id]
            if isinstance(route_info, dict) and route_info.get('next_hop'):
                next_hop = route_info['next_hop']
                next_hop_node = self.node_map.get(next_hop)
                if next_hop_node and next_hop_node in node.neighbors and next_hop_node.energy > 0:
                    # Route exists, try routing
                    return self._route_packet(node, packet)
        
        # OLSR is proactive, so routes should already exist
        # If no route exists, packet will be dropped
        return False
    
    def _periodic_neighbor_update(self):
        """Update neighbor lists periodically"""
        while not config.get_stop_simulation():
            self.update_neighbors()
            yield self.env.timeout(1.0)
    
    def _hello_messages(self):
        """Send hello messages periodically"""
        while not config.get_stop_simulation():
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                # Send hello message to neighbors
                for neighbor in node.neighbors:
                    if neighbor.energy > 0:
                        self.env.process(self._send_hello(node, neighbor))
            
            yield self.env.timeout(2.0)  # 2 second hello interval
    
    def _send_hello(self, src_node, dest_node):
        """Send hello message"""
        if src_node.energy <= 0 or dest_node.energy <= 0:
            return
        
        hello_msg = {
            'src_id': src_node.id,
            'neighbors': [n.id for n in src_node.neighbors if n.energy > 0],
            'timestamp': self.env.now
        }
        
        self.routing_overhead += 1
        src_node.consume_energy(0.05)
        
        # Process hello message
        yield self.env.timeout(0.01)
        self.env.process(self._process_hello(hello_msg, dest_node))
    
    def _process_hello(self, hello_msg, node):
        """Process received hello message"""
        if node.energy <= 0:
            return
        
        src_id = hello_msg['src_id']
        neighbors = hello_msg['neighbors']
        
        # Update neighbor information
        self.topology_table.setdefault(node.id, {})
        self.topology_table[node.id][src_id] = {
            'neighbors': neighbors,
            'timestamp': self.env.now
        }
    
    def _mpr_selection(self):
        """Select MPRs (Multipoint Relays)"""
        while not config.get_stop_simulation():
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                # Simple MPR selection: select all 2-hop neighbors
                mprs = set()
                for neighbor in node.neighbors:
                    if neighbor.energy > 0:
                        # Add neighbors of this neighbor
                        for n2 in neighbor.neighbors:
                            if n2.id != node.id and n2.energy > 0:
                                mprs.add(neighbor.id)
                                break
                
                self.mprs[node.id] = list(mprs)
                
                # Update MPR selectors
                for mpr_id in mprs:
                    self.mpr_selectors.setdefault(mpr_id, set()).add(node.id)
            
            yield self.env.timeout(10.0)  # 10 second MPR selection interval
    
    def _tc_messages(self):
        """Send topology control messages"""
        while not config.get_stop_simulation():
            for node in self.nodes:
                if node.energy <= 0:
                    continue
                
                # Send TC message if we're an MPR
                if node.id in self.mpr_selectors:
                    self.env.process(self._send_tc_message(node))
            
            yield self.env.timeout(5.0)  # 5 second TC interval
    
    def _send_tc_message(self, node):
        """Send topology control message"""
        if node.energy <= 0:
            return
        
        tc_msg = {
            'src_id': node.id,
            'mprs': self.mprs.get(node.id, []),
            'timestamp': self.env.now
        }
        
        self.routing_overhead += 1
        node.consume_energy(0.1)
        
        # Broadcast to neighbors
        for neighbor in node.neighbors:
            if neighbor.energy > 0:
                self.env.process(self._process_tc_message(tc_msg, neighbor))
    
    def _process_tc_message(self, tc_msg, node):
        """Process received TC message"""
        if node.energy <= 0:
            return
        
        src_id = tc_msg['src_id']
        mprs = tc_msg['mprs']
        
        # Update topology table
        self.topology_table.setdefault(node.id, {})
        self.topology_table[node.id][src_id] = {
            'mprs': mprs,
            'timestamp': self.env.now
        }
        
        # Recalculate routing table
        self._calculate_routing_table()
    
    def _calculate_routing_table(self):
        """Calculate routing table using Dijkstra's algorithm"""
        for src_node in self.nodes:
            if src_node.energy <= 0:
                continue
            
            # Initialize distances
            distances = {n.id: float('inf') for n in self.nodes}
            distances[src_node.id] = 0
            previous = {}
            unvisited = {n.id for n in self.nodes if n.energy > 0}
            
            while unvisited:
                # Find node with minimum distance
                current = min(unvisited, key=lambda x: distances[x])
                if distances[current] == float('inf'):
                    break
                
                unvisited.remove(current)
                
                # Check direct neighbors
                current_node = self.node_map.get(current)
                if current_node and current_node.energy > 0:
                    for neighbor in current_node.neighbors:
                        if neighbor.id in unvisited and neighbor.energy > 0:
                            alt = distances[current] + 1
                            if alt < distances[neighbor.id]:
                                distances[neighbor.id] = alt
                                previous[neighbor.id] = current
                
                # Check topology table for MPR information
                topology_info = self.topology_table.get(current, {})
                for dest_id, info in topology_info.items():
                    if dest_id in unvisited:
                        mprs = info.get('mprs', [])
                        for mpr_id in mprs:
                            if mpr_id in unvisited:
                                alt = distances[current] + 2  # 2-hop through MPR
                                if alt < distances[mpr_id]:
                                    distances[mpr_id] = alt
                                    previous[mpr_id] = current
            
            # Build routing table
            for dest_node in self.nodes:
                if (dest_node.id != src_node.id and 
                    dest_node.id in previous and 
                    dest_node.energy > 0):
                    
                    # Find next hop
                    path = []
                    current = dest_node.id
                    while current in previous:
                        path.append(current)
                        current = previous[current]
                    
                    if len(path) > 0:
                        next_hop = path[-1] if len(path) == 1 else path[-2]
                        
                        # Update routing tables
                        self.route_tables.setdefault(src_node.id, {})
                        self.route_tables[src_node.id][dest_node.id] = {
                            'next_hop': next_hop,
                            'metric': distances[dest_node.id]
                        }
                        src_node.routing_table[dest_node.id] = next_hop
