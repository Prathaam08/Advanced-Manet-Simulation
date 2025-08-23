# File: simulation_engine/protocols.py


import simpy
from collections import defaultdict, deque
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

    def update_neighbors(self):
        for node in self.nodes:
            node.neighbors.clear()
            for other in self.nodes:
                if node.id != other.id and node.distance_to(other) <= node.tx_range:
                    node.neighbors.append(other)

    def send_packet(self, packet):
        src_node = self.node_map[packet.src_id]
        self.packet_queue[src_node.id].append(packet)

        if not getattr(src_node, 'routing_handler_running', False):
            src_node.routing_handler_running = True

            def _handler_wrapper():
                yield from self._handle_packets(src_node)
                src_node.routing_handler_running = False

            self.env.process(_handler_wrapper())

    def _handle_packets(self, node):
        while self.packet_queue[node.id]:
            packet = self.packet_queue[node.id].popleft()

            if packet.dst_id == node.id:
                self.env.process(node.receive(packet))
                yield self.env.timeout(0)
                continue

            if packet.dst_id in node.routing_table:
                next_hop_id = node.routing_table[packet.dst_id]
                if next_hop_id in [n.id for n in node.neighbors]:
                    packet.hops.append((node.id, self.env.now))
                    packet.last_hop = node.id

                    yield self.env.timeout(packet.size / (2 * 1024))

                    node.consume_energy(0.1)

                    next_hop_node = self.node_map.get(next_hop_id)
                    if next_hop_node:
                        self.env.process(next_hop_node.receive(packet))
                    continue

            yield self.env.timeout(0.001)

    def get_overhead(self):
        return self.routing_overhead

    def get_next_hop(self, current_id, destination_id):
        table = self.route_tables.get(current_id, {})
        if table is None:
            return None

        entry = table.get(destination_id)
        if isinstance(entry, dict):
            next_hop_id = entry.get('next_hop')
        else:
            next_hop_id = entry

        if next_hop_id is None:
            return None

        return self.node_map.get(next_hop_id)


class AODV(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.rreq_id = 0
        self.pending_packets = defaultdict(list)
        self.seq_num = 0
        self.env.process(self._periodic_neighbor_update())

    def _periodic_neighbor_update(self):
        while not config.stop_simulation:
            self.update_neighbors()
            yield self.env.timeout(1.0)

    def _route_packet(self, node, packet):
        next_hop = self.route_tables.get(node.id, {}).get(packet.dst_id)
        if isinstance(next_hop, dict):
            next_hop = next_hop.get('next_hop')
        if next_hop is not None:
            node.routing_table[packet.dst_id] = next_hop
            return True
        return False

    def _route_discovery(self, src_node, packet):
        self.rreq_id += 1
        rreq = {
            'src_id': src_node.id,
            'dst_id': packet.dst_id,
            'rreq_id': self.rreq_id,
            'src_seq': self.seq_num,
            'dst_seq': 0,
            'hop_count': 0,
            'ttl': 10,
            'last_hop': src_node.id
        }
        self.seq_num += 1

        self.pending_packets[(src_node.id, packet.dst_id)].append(packet)
        self.routing_overhead += 1

        for neighbor in src_node.neighbors:
            self.env.process(self._forward_rreq(dict(rreq), neighbor.id))

    def _forward_rreq(self, rreq, node_id):
        yield self.env.timeout(0.01)
        rreq['hop_count'] += 1
        rreq['ttl'] -= 1

        node = self.node_map.get(node_id)
        if not node:
            return

        if node.id != rreq['src_id']:
            self.route_tables.setdefault(node.id, {})
            self.route_tables[node.id][rreq['src_id']] = rreq.get('last_hop')

        if node.id == rreq['dst_id']:
            self.env.process(self._send_rrep(rreq, node.id))
            return

        if rreq['ttl'] > 0:
            for neighbor in node.neighbors:
                if neighbor.id != rreq.get('last_hop'):
                    new_rreq = dict(rreq)
                    new_rreq['last_hop'] = node.id
                    self.env.process(self._forward_rreq(new_rreq, neighbor.id))

    def _send_rrep(self, rreq, dst_node_id):
        yield self.env.timeout(0.01)
        path = []
        current = dst_node_id
        src = rreq['src_id']
        visited = set()

        while True:
            path.append(current)
            if current == src:
                break
            visited.add(current)
            next_hop = self.route_tables.get(current, {}).get(src)
            if isinstance(next_hop, dict):
                next_hop = next_hop.get('next_hop')
            if next_hop is None or next_hop in visited:
                break
            current = next_hop

        path.reverse()

        for i in range(len(path) - 1):
            node_id = path[i]
            next_hop_id = path[i + 1]
            self.route_tables.setdefault(node_id, {})
            self.route_tables[node_id][rreq['dst_id']] = next_hop_id
            node_obj = self.node_map.get(node_id)
            if node_obj:
                node_obj.routing_table[rreq['dst_id']] = next_hop_id

        self.routing_overhead += max(0, len(path) - 1)

        pending = self.pending_packets.pop((rreq['src_id'], rreq['dst_id']), [])
        for pkt in pending:
            self.send_packet(pkt)

    def try_send(self, src_node, packet):
        if self._route_packet(src_node, packet):
            self.send_packet(packet)
            return True
        self._route_discovery(src_node, packet)
        return False


class DSDV(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        for node in nodes:
            for other in nodes:
                if node.id == other.id:
                    self.route_tables[node.id][other.id] = {'next_hop': other.id, 'metric': 0}
                else:
                    self.route_tables[node.id][other.id] = {'next_hop': None, 'metric': float('inf')}
        self.env.process(self._periodic_update())
        self.env.process(self._periodic_neighbor_update())

    def _periodic_neighbor_update(self):
        while not config.stop_simulation:
            self.update_neighbors()
            yield self.env.timeout(2.0)

    def _periodic_update(self):
        while not config.stop_simulation:
            for node in self.nodes:
                for neighbor in node.neighbors:
                    self.routing_overhead += len(self.route_tables[node.id])
                    for dest, route in list(self.route_tables[node.id].items()):
                        new_metric = route['metric'] + 1
                        neighbor_table = self.route_tables[neighbor.id]
                        if new_metric < neighbor_table[dest]['metric']:
                            neighbor_table[dest] = {'next_hop': node.id, 'metric': new_metric}
                            neighbor_obj = self.node_map.get(neighbor.id)
                            if neighbor_obj:
                                neighbor_obj.routing_table[dest] = node.id
            yield self.env.timeout(5.0)

    def _route_packet(self, node, packet):
        entry = self.route_tables.get(node.id, {}).get(packet.dst_id)
        if entry and entry.get('next_hop') is not None:
            node.routing_table[packet.dst_id] = entry.get('next_hop')
            return True
        return False


class DSR(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.route_cache = {}
        self.env.process(self._periodic_neighbor_update())

    def _periodic_neighbor_update(self):
        while not config.stop_simulation:
            self.update_neighbors()
            yield self.env.timeout(1.0)

    def _route_packet(self, node, packet):
        key = (packet.src_id, packet.dst_id)
        if key in self.route_cache:
            route = self.route_cache[key]
            if node.id in route:
                idx = route.index(node.id) + 1
                if idx < len(route):
                    next_hop_id = route[idx]
                    node.routing_table[packet.dst_id] = next_hop_id
                    return True
        return False


class OLSR(BaseRouting):
    def __init__(self, env, nodes, graph):
        super().__init__(env, nodes, graph)
        self.mpr_selectors = {}
        self.env.process(self._periodic_neighbor_update())
        self.env.process(self._mpr_selection())

    def _periodic_neighbor_update(self):
        while not config.stop_simulation:
            self.update_neighbors()
            yield self.env.timeout(1.0)

    def _mpr_selection(self):
        while not config.stop_simulation:
            for node in self.nodes:
                node.mprs = [n.id for n in node.neighbors]
                for mpr in node.mprs:
                    self.mpr_selectors.setdefault(mpr, set()).add(node.id)
            yield self.env.timeout(10.0)

    def _route_packet(self, node, packet):
        entry = self.route_tables.get(node.id, {}).get(packet.dst_id)
        if isinstance(entry, dict):
            next_hop_id = entry.get('next_hop')
        else:
            next_hop_id = entry
        if next_hop_id is not None:
            node.routing_table[packet.dst_id] = next_hop_id
            return True
        return False
