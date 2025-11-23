#  File: simulation_engine/manet_models.py
import math
import numpy as np
import random

class Node:
    def __init__(self, id, position, area_size, speed=10, pause_time=5, tx_range=100):
        self.id = id
        self.position = np.array(position, dtype=float)
        self.area_size = area_size
        self.speed = speed
        self.pause_time = pause_time
        self.tx_range = tx_range
        self.neighbors = []
        self.routing_table = {}
        self.energy = 100.0
        self.energy_used = 0.0
        self.direction = np.array([random.uniform(-1, 1), random.uniform(-1, 1)])
        norm = np.linalg.norm(self.direction)
        if norm > 0:
            self.direction /= norm
        self.move_timer = 0
        self.simulator = None
        self.routing_handler_running = False

    def move(self, env):
        """SimPy process: move the node and periodically update neighbor list."""
        while True:
            if hasattr(self, 'simulator') and getattr(self.simulator, 'stop_flag', False):
                return

            self.direction = np.array([random.uniform(-1, 1), random.uniform(-1, 1)])
            norm = np.linalg.norm(self.direction)
            if norm > 0:
                self.direction /= norm

            move_duration = self.pause_time
            start_time = env.now

            while env.now - start_time < move_duration:
                if hasattr(self, 'simulator') and getattr(self.simulator, 'stop_flag', False):
                    return

                self.position += self.direction * self.speed * 0.1

                for i in range(2):
                    if self.position[i] < 0:
                        self.position[i] = 0
                        self.direction[i] = abs(self.direction[i])
                    elif self.position[i] > self.area_size[i]:
                        self.position[i] = self.area_size[i]
                        self.direction[i] = -abs(self.direction[i])

                self.consume_energy(0.01 * self.speed)
                self.update_neighbors()

                yield env.timeout(0.1)

            yield env.timeout(self.pause_time)

    def update_neighbors(self):
        if not self.simulator:
            return
        self.neighbors.clear()
        for node in self.simulator.nodes:
            if node.id != self.id and self.distance_to(node) <= self.tx_range:
                self.neighbors.append(node)

    def distance_to(self, other_node):
        return np.linalg.norm(self.position - other_node.position)

    def consume_energy(self, amount):
        self.energy -= amount
        self.energy_used += amount
        if self.energy < 0:
            self.energy = 0

    def receive(self, packet):
        """Synchronous packet reception"""
        if not self.simulator:
            return False
            
        if packet.dst_id == self.id:
            # Packet reached destination
            packet.delivery_time = self.simulator.env.now
            self.simulator.metrics['packets_received'] += 1
            
            # Calculate delay including transmission delays
            base_delay = packet.delivery_time - packet.creation_time
            transmission_delay = getattr(packet, 'transmission_delay', 0)
            total_delay = base_delay + transmission_delay
            
            self.simulator.metrics['total_delay'] += total_delay
            self.simulator.metrics['hop_counts'].append(len(packet.hops))
            self.consume_energy(0.05)  # Energy for reception
            return True

        # Check for infinite loops - if this node already processed this packet
        if self.id in packet.hops:
            # Loop detected, drop packet
            self.simulator.metrics['packets_dropped'] += 1
            return False

        # Add this node to the hop list to prevent loops
        packet.hops.append(self.id)
        packet.last_hop = self.id

        # Try to route packet
        routing = self.simulator.routing
        if routing and hasattr(routing, '_route_packet_sync'):
            # Use synchronous routing
            routed = routing._route_packet_sync(self, packet)
            if routed:
                return True
        
        # If no route found, try route discovery
        if routing and hasattr(routing, '_initiate_route_discovery_sync'):
            routed = routing._initiate_route_discovery_sync(self, packet)
            if routed:
                return True
        
        # Packet dropped
        self.simulator.metrics['packets_dropped'] += 1
        return False


class Packet:
    def __init__(self, src_id, dst_id, creation_time, size=512):
        self.src_id = src_id
        self.dst_id = dst_id
        self.creation_time = creation_time
        self.size = size
        self.hops = []
        self.last_hop = src_id
        self.delivery_time = None