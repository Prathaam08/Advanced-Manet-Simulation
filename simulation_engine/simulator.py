# File: simulation_engine/simulator.py



import simpy
import networkx as nx
import numpy as np
import json
import os
import time
from .manet_models import Node, Packet
from .protocols import AODV, DSDV, DSR, OLSR
from . import config

class MANETSimulator:
    def __init__(self, num_nodes=50, area_size=(1000,1000), protocol='AODV',
                 sim_time=45, traffic_load=10, node_speed=10, tx_range=100, pause_time=5):
        self.env = simpy.Environment()
        self.nodes = []
        self.G = nx.Graph()
        self.protocol = protocol
        self.metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'total_delay': 0,
            'start_time': 0,
            'energy_used': 0
        }
        self.interval_metrics = {
            'packets_sent': 0,
            'packets_received': 0,
            'total_delay': 0
        }
        self.sim_time = sim_time
        self.traffic_load = traffic_load
        self.area_size = area_size
        self.node_speed = node_speed
        self.tx_range = tx_range
        self.pause_time = pause_time

        for i in range(num_nodes):
            pos = (np.random.uniform(0, area_size[0]),
                   np.random.uniform(0, area_size[1]))
            node = Node(i, pos, area_size, speed=node_speed,
                        pause_time=pause_time, tx_range=tx_range)
            node.simulator = self
            node.simulator.stop_flag = False
            self.nodes.append(node)
            self.G.add_node(i, pos=pos)

        protocol_map = {
            'AODV': AODV,
            'DSDV': DSDV,
            'DSR': DSR,
            'OLSR': OLSR
        }
        self.routing = protocol_map[protocol](self.env, self.nodes, self.G)

    def generate_traffic(self):
        while self.env.now < self.sim_time:
            if config.stop_simulation:
                return

            if len(self.nodes) < 2:
                yield self.env.timeout(1.0 / max(1.0, self.traffic_load))
                continue

            try:
                self.routing.update_neighbors()
            except Exception:
                pass

            src, dst = np.random.choice(self.nodes, 2, replace=False)
            packet = Packet(src.id, dst.id, self.env.now, size=512)

            if hasattr(self.routing, 'try_send'):
                self.routing.try_send(src, packet)
            else:
                self.routing.send_packet(packet)

            self.metrics['packets_sent'] += 1
            self.interval_metrics['packets_sent'] += 1

            yield self.env.timeout(1.0 / max(1.0, self.traffic_load))

    def run(self):
        config.reset()

        for node in self.nodes:
            self.env.process(node.move(self.env))

        try:
            self.routing.update_neighbors()
        except Exception:
            pass

        self.env.process(self.generate_traffic())

        self.start_time = self.env.now
        last_update = 0
        update_interval = 1

        while True:
            try:
                next_event_time = self.env.peek()
            except Exception:
                break

            if next_event_time >= self.sim_time:
                break

            if config.stop_simulation:
                for n in self.nodes:
                    try:
                        n.simulator.stop_flag = True
                    except Exception:
                        pass
                return

            self.env.step()

            current_time = self.env.now - self.start_time
            if current_time - last_update >= update_interval:
                for node in self.nodes:
                    node.neighbors.clear()
                    for other in self.nodes:
                        if node.id != other.id and node.distance_to(other) <= node.tx_range:
                            node.neighbors.append(other)

                try:
                    self.routing.update_neighbors()
                except Exception:
                    pass

                metrics = {
                    'type': 'metrics',
                    'time': current_time,
                    'pdr': self.calculate_pdr(),
                    'delay': self.calculate_avg_delay(),
                    'throughput': self.calculate_throughput(),
                    'energy': self.calculate_energy(),
                    'overhead': self.routing.get_overhead(),
                    'nodes': [
                        {
                            'id': node.id,
                            'x': float(node.position[0]),
                            'y': float(node.position[1]),
                            'energy': float(node.energy)
                        }
                        for node in self.nodes
                    ],
                    'links': [
                        {'source': node.id, 'target': neighbor.id}
                        for node in self.nodes
                        for neighbor in node.neighbors
                        if neighbor.id > node.id
                    ],
                    'areaSize': self.area_size
                }

                yield metrics
                last_update = current_time

                self.interval_metrics = {
                    'packets_sent': 0,
                    'packets_received': 0,
                    'total_delay': 0
                }

        final_metrics = {
            'type': 'final_metrics',
            'pdr': self.calculate_pdr(),
            'avg_delay': self.calculate_avg_delay(),
            'throughput': self.calculate_throughput(),
            'overhead': self.routing.get_overhead(),
            'energy': self.calculate_energy(),
            'sim_time': self.sim_time,
            'protocol': self.protocol,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        os.makedirs('data/simulations', exist_ok=True)
        with open(f"data/simulations/sim_{time.time()}.json", 'w') as f:
            json.dump(final_metrics, f)

        yield final_metrics

    def calculate_pdr(self):
        if self.metrics['packets_sent'] == 0:
            return 0.0
        return self.metrics['packets_received'] / self.metrics['packets_sent']

    def calculate_avg_delay(self):
        if self.metrics['packets_received'] == 0:
            return 0.0
        return self.metrics['total_delay'] / self.metrics['packets_received']

    def calculate_throughput(self):
        if self.interval_metrics['packets_received'] == 0:
            return 0.0
        return (self.interval_metrics['packets_received'] * 512 * 8) / (0.5 * 1000)

    def calculate_energy(self):
        return sum(node.energy_used for node in self.nodes)