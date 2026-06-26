from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any

from .math_utils import distance
from .settings import load_json


@dataclass(frozen=True)
class MapNode:
    node_id: str
    name: str
    x: float
    y: float
    goal: bool
    speed_pwm: float | None = None


class RoutePlanner:
    def __init__(self) -> None:
        graph = load_json("graph.json")
        self.nodes: dict[str, MapNode] = {}
        self.links: dict[str, list[tuple[str, float]]] = {}

        for item in graph["nodes"]:
            node = MapNode(
                node_id=item["id"],
                name=item.get("name", item["id"]),
                x=float(item["x"]),
                y=float(item["y"]),
                goal=bool(item.get("goal", False)),
                speed_pwm=None if item.get("speed_pwm") is None else float(item["speed_pwm"]),
            )
            self.nodes[node.node_id] = node
            self.links[node.node_id] = []

        for edge in graph["edges"]:
            a = edge["a"]
            b = edge["b"]
            cost = float(edge.get("cost", distance(self.point(a), self.point(b))))
            self.links[a].append((b, cost))
            if not edge.get("one_way", False):
                self.links[b].append((a, cost))

    def point(self, node_id: str) -> tuple[float, float]:
        node = self.nodes[node_id]
        return node.x, node.y

    def nearest_node(self, x: float, y: float) -> str:
        return min(self.nodes, key=lambda node_id: distance((x, y), self.point(node_id)))

    def plan(self, start_xy: tuple[float, float], goal_id: str) -> list[tuple[float, float]]:
        if goal_id not in self.nodes:
            raise ValueError(f"Unknown goal: {goal_id}")

        start_id = self.nearest_node(*start_xy)
        node_route = self._a_star(start_id, goal_id)
        points = [start_xy]
        points.extend(self.point(node_id) for node_id in node_route)
        return self._resample(points, step_m=0.08)

    def _a_star(self, start_id: str, goal_id: str) -> list[str]:
        queue: list[tuple[float, str]] = [(0.0, start_id)]
        came_from: dict[str, str | None] = {start_id: None}
        cost_so_far: dict[str, float] = {start_id: 0.0}

        while queue:
            _, current = heapq.heappop(queue)
            if current == goal_id:
                break

            for next_id, edge_cost in self.links[current]:
                new_cost = cost_so_far[current] + edge_cost
                if next_id not in cost_so_far or new_cost < cost_so_far[next_id]:
                    cost_so_far[next_id] = new_cost
                    heuristic = distance(self.point(next_id), self.point(goal_id))
                    heapq.heappush(queue, (new_cost + heuristic, next_id))
                    came_from[next_id] = current

        if goal_id not in came_from:
            raise ValueError(f"No graph route from {start_id} to {goal_id}")

        route: list[str] = []
        current: str | None = goal_id
        while current is not None:
            route.append(current)
            current = came_from[current]
        route.reverse()
        return route

    @staticmethod
    def _resample(points: list[tuple[float, float]], step_m: float) -> list[tuple[float, float]]:
        if len(points) < 2:
            return points

        output = [points[0]]
        for start, end in zip(points, points[1:]):
            length = distance(start, end)
            count = max(1, math.ceil(length / step_m))
            for index in range(1, count + 1):
                ratio = index / count
                output.append(
                    (
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    )
                )
        return output

    def public_data(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": node.node_id,
                    "name": node.name,
                    "x": node.x,
                    "y": node.y,
                    "goal": node.goal,
                    "speed_pwm": node.speed_pwm,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {"a": node_id, "b": other}
                for node_id, links in self.links.items()
                for other, _ in links
                if node_id < other
            ],
        }
