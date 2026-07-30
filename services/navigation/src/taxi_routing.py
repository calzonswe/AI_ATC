from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Set, Tuple

from geo import haversine_distance
from models import (
    LatLon,
    NodeType,
    TaxiEdge,
    TaxiGraph,
    TaxiNode,
    TaxiRoute,
)


class TaxiRoutePlanner:
    MIN_EDGE_LENGTH_M = 1.0

    def __init__(self, graph: Optional[TaxiGraph] = None) -> None:
        self.graph = graph or TaxiGraph()

    def set_graph(self, graph: TaxiGraph) -> None:
        self.graph = graph

    def build_graph_from_segments(
        self,
        segments: List[Dict],
        nodes: List[Dict],
        closed_taxiways: Optional[Set[str]] = None,
    ) -> TaxiGraph:
        graph = TaxiGraph()
        for nd in nodes:
            graph.add_node(TaxiNode(
                node_id=nd["id"],
                position=LatLon(lat=nd["lat"], lon=nd["lon"]),
                node_type=NodeType(nd.get("type", "intersection")),
                name=nd.get("name", ""),
            ))
        for seg in segments:
            frm = seg["from_node"]
            to = seg["to_node"]
            if frm not in graph.nodes or to not in graph.nodes:
                continue
            a = graph.nodes[frm].position
            b = graph.nodes[to].position
            dist_m = haversine_distance(a.lat, a.lon, b.lat, b.lon) * 1852.0
            if dist_m < self.MIN_EDGE_LENGTH_M:
                continue
            closed = seg.get("taxiway_name", "") in (closed_taxiways or set())
            edge_id = f"{frm}->{to}"
            graph.add_edge(TaxiEdge(
                edge_id=edge_id,
                from_node=frm,
                to_node=to,
                distance_m=dist_m,
                taxiway_name=seg.get("taxiway_name", ""),
                closed=closed or seg.get("closed", False),
                width_ft=seg.get("width_ft", 75.0),
            ))
        self.graph = graph
        return graph

    def find_shortest_path(
        self,
        start_node_id: str,
        end_node_id: str,
        avoid_closed: bool = True,
        max_taxi_speed_mps: float = 10.0,
    ) -> Optional[TaxiRoute]:
        if start_node_id not in self.graph.nodes:
            return None
        if end_node_id not in self.graph.nodes:
            return None

        start = self.graph.nodes[start_node_id].position
        end = self.graph.nodes[end_node_id].position

        open_set: List[Tuple[float, float, str, Optional[str]]] = []
        start_h = haversine_distance(start.lat, start.lon, end.lat, end.lon) * 1852.0
        heapq.heappush(open_set, (start_h, 0.0, start_node_id, None))

        g_score: Dict[str, float] = {start_node_id: 0.0}
        came_from: Dict[str, Tuple[str, str]] = {}

        visited: Set[str] = set()

        while open_set:
            _, current_g, current, _ = heapq.heappop(open_set)

            if current in visited:
                continue
            visited.add(current)

            if current == end_node_id:
                return self._reconstruct_path(came_from, current, max_taxi_speed_mps)

            if current not in self.graph.adjacency:
                continue

            for neighbor, edge_id in self.graph.adjacency[current].items():
                edge = self.graph.edges.get(edge_id)
                if edge is None:
                    continue
                if avoid_closed and edge.closed:
                    continue

                tentative_g = g_score[current] + edge.distance_m

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    nb_pos = self.graph.nodes[neighbor].position
                    h = haversine_distance(nb_pos.lat, nb_pos.lon, end.lat, end.lon) * 1852.0
                    f = tentative_g + h
                    heapq.heappush(open_set, (f, tentative_g, neighbor, edge_id))
                    came_from[neighbor] = (current, edge_id)

        return None

    def _reconstruct_path(
        self,
        came_from: Dict[str, Tuple[str, str]],
        current: str,
        max_taxi_speed_mps: float,
    ) -> TaxiRoute:
        nodes: List[TaxiNode] = []
        edges: List[TaxiEdge] = []
        path_nodes = [current]

        while current in came_from:
            prev, edge_id = came_from[current]
            path_nodes.append(prev)
            current = prev

        path_nodes.reverse()

        total_m = 0.0
        for i in range(len(path_nodes)):
            nid = path_nodes[i]
            if nid in self.graph.nodes:
                nodes.append(self.graph.nodes[nid])
            if i > 0:
                prev_id = path_nodes[i - 1]
                adj = self.graph.adjacency.get(prev_id, {})
                eid = adj.get(nid)
                if eid and eid in self.graph.edges:
                    edge = self.graph.edges[eid]
                    edges.append(edge)
                    total_m += edge.distance_m

        total_s = total_m / max_taxi_speed_mps if max_taxi_speed_mps > 0 else 0.0
        return TaxiRoute(
            nodes=nodes,
            edges=edges,
            total_distance_m=total_m,
            total_duration_s=total_s,
        )


class ShortestPathSolver:
    @staticmethod
    def solve(
        graph: TaxiGraph,
        start: str,
        end: str,
        weight_fn=None,
        avoid_nodes: Optional[Set[str]] = None,
    ) -> Optional[TaxiRoute]:
        planner = TaxiRoutePlanner(graph)
        if avoid_nodes:
            for nid in avoid_nodes:
                if nid in graph.nodes:
                    for neighbor in graph.adjacency.get(nid, {}):
                        eid = graph.adjacency[nid][neighbor]
                        if eid in graph.edges:
                            graph.edges[eid].closed = True
        return planner.find_shortest_path(start, end)

    @staticmethod
    def compute_route_distance(route: TaxiRoute) -> float:
        return route.total_distance_m

    @staticmethod
    def compute_route_duration(
        route: TaxiRoute, speed_mps: float = 10.0
    ) -> float:
        return route.total_distance_m / speed_mps if speed_mps > 0 else 0.0
