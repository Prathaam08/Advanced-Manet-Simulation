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
        yield self.simulator.env.timeout(0.001)

        if packet.dst_id == self.id:
            packet.delivery_time = self.simulator.env.now
            self.simulator.metrics['packets_received'] += 1
            self.simulator.interval_metrics['packets_received'] += 1
            delay = packet.delivery_time - packet.creation_time
            self.simulator.metrics['total_delay'] += delay
            self.simulator.interval_metrics['total_delay'] += delay
            return

        routing = self.simulator.routing
        next_hop = routing.get_next_hop(self.id, packet.dst_id)
        if next_hop is not None:
            packet.hops.append(self.id)
            packet.last_hop = self.id
            self.simulator.env.process(next_hop.receive(packet))
        else:
            routing.packet_queue[self.id].append(packet)

            if not self.routing_handler_running:
                self.routing_handler_running = True

                def _handler_wrapper():
                    yield from routing._handle_packets(self)
                    self.routing_handler_running = False

                self.simulator.env.process(_handler_wrapper())


class Packet:
    def __init__(self, src_id, dst_id, creation_time, size=512):
        self.src_id = src_id
        self.dst_id = dst_id
        self.creation_time = creation_time
        self.size = size
        self.hops = []
        self.last_hop = src_id
        self.delivery_time = None