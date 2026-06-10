const PriorityQueue = require('../utils/priorityQueue');

const getCarState = require('../globals/carState')
const hdmap = require('../globals/mapState');

// Euclidean distance heuristic for A*
function heuristic(nodeA, nodeB) {
  if (!nodeA || !nodeB) return 0;
  const dx = nodeA.x - nodeB.x;
  const dy = nodeA.y - nodeB.y;
  return Math.sqrt(dx * dx + dy * dy);
}

// A* search on the HDMap between node ids
// Returns array of nodeIds from start -> goal or null if no path
function aStarSearch(startId, goalId) {
  if (!startId || !goalId) return null;
  const startNode = hdmap.getNodeById(startId);
  const goalNode = hdmap.getNodeById(goalId);
  if (!startNode || !goalNode) return null;

  const frontier = new PriorityQueue();
  const exploredset = new Set();
  frontier.push(startId, 0);

  const cameFrom = new Map(); // to reconstruct path
  const gScore = new Map(); // to store cost to reach each node from start
  gScore.set(startId, 0);

  while (!frontier.isEmpty()) {
    const current = frontier.pop();
    exploredset.add(current.key);
    if (!current) break;
    const currentId = current.key;

    if (currentId === goalId) {
      // reconstruct path
      const pathArr = [];
      let cur = goalId;
      while (cur !== undefined && cur !== null) {
        pathArr.push(cur);
        cur = cameFrom.get(cur);
      }
      return pathArr.reverse();
    }
    const edges = hdmap.getNodeEdges(currentId);
    for (const e of edges) {
      const neighbourId = hdmap.getNeighbour(currentId,e);
      if (exploredset.has(neighbourId)) continue;
      const travelcost = e.length + gScore.get(currentId);
      // if g cost of neighbour is greater than current one refuse it
      if (travelcost < (gScore.get(neighbourId) || Infinity)) {
        cameFrom.set(neighbourId, currentId);
        gScore.set(neighbourId, travelcost);
        const f = travelcost + heuristic(hdmap.getNodeById(neighbourId), goalNode);
        frontier.push(neighbourId, f);
      }
    }
  }
  return null; // no path
}

function tripPlanning(start, destination) {
  // get car pose and find nearest node
  const carState = getCarState()
  const carpose = {x:carState.x,y:carState.y};
  const region = hdmap.findRegion(carpose);
  let nearestNode = null;
  if (region) {
    nearestNode = region.entrance_node_id;
  } else {
    nearestNode = hdmap.getNearestNode(carpose);
  }
  if (nearestNode === null){
    return null;
  }
  //get places ids
  const startId = hdmap.getPlaceId(start);
  const goalId = hdmap.getPlaceId(destination);
  if (startId === null || goalId === null) return null;
  // use a star search
  const path1 = aStarSearch(nearestNode, startId);
  const path2 = aStarSearch(startId, goalId);
  if (path1 === null || path2 === null){
    return null;
  }
  // get poses to send to car
  // remove duplicate start node
  path1.pop();
  const poses = [];
  for (const nodeId of path1) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  for (const nodeId of path2) {
    const node = hdmap.getNodeById(nodeId);
    if (!node) continue;
    poses.push({ x: node.x, y: node.y });
  }
  return poses;
}

module.exports = { tripPlanning};
