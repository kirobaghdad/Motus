const PriorityQueue = require('../utils/priorityQueue');

const { getCarPose } = require('../globals/carState');
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
    if (startId === goalId) return [startId];
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
            const neighbourId = hdmap.getNeighbour(currentId, e);
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

function optimizePathStart(path, nearestNodeEdge) {
    if (!nearestNodeEdge || !path || path.length < 2) return;
    const nearestEdge = nearestNodeEdge.edge;
    const nearestNode = nearestNodeEdge.nodeId;
    for (edge of hdmap.getIncomingEdges(nodeId)) {
        if (edge.roadId !== nearestEdge.roadId) continue;
        neighborNodeID = hdmap.getNeighbour(nearestNode, edge);
        if (neighborNodeID && path[1] === neighborNodeID) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.shift();
            return;
        }
    }
    for (edge of hdmap.getOutgoingEdges(nodeId)) {
        if (edge.roadId !== nearestEdge.roadId) continue;
        neighborNodeID = hdmap.getNeighbour(nearestNode, edge);
        if (neighborNodeID && path[1] === neighborNodeID) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.shift();
            return;
        }
    }
}

function optimizePathEnd(path, nearestNodeEdge) {
    if (!nearestNodeEdge || !path || path.length < 2) return;
    const nearestEdge = nearestNodeEdge.edge;
    const nearestNode = nearestNodeEdge.nodeId;
    for (edge of hdmap.getIncomingEdges(nodeId)) {
        if (edge.roadId !== nearestEdge.roadId) continue;
        neighborNodeID = hdmap.getNeighbour(nearestNode, edge);
        if (neighborNodeID && path[path.length - 2] === neighborNodeID) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.pop();
            return;
        }
    }
    for (edge of hdmap.getOutgoingEdges(nodeId)) {
        if (edge.roadId !== nearestEdge.roadId) continue;
        neighborNodeID = hdmap.getNeighbour(nearestNode, edge);
        if (neighborNodeID && path[path.length - 2] === neighborNodeID) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.pop();
            return;
        }
    }
}

function solveSameRoadCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (startNearestNodeEdge.edge.roadId === destNearestNodeEdge.edge.roadId) {
        // same road but must make sure going directly to destination is in the same direction of road
        if (edge.bi_directional) {
            // make car go directly to destination if start and destination are in the same road and road is bi directional
            return [];
        }
        const roadDirection = findDirectionOfRoad(startNearestNodeEdge.edge);
        const startDestDirection = getStartDestDirection(startNearestNodeEdge, destNearestNodeEdge);
        const dotProduct = roadDirection.dx * startDestDirection.dx + roadDirection.dy * startDestDirection.dy;
        if (dotProduct > 0) {
            // make car go directly to destination if start and destination are in the same direction
            return [];
        }
        // different direction car can not go back in wrong direction
        if (startNearestNodeEdge.nodeId === destNearestNodeEdge.nodeId) {
            neighborNodeId = hdmap.getNeighbour(destNearestNodeEdge.nodeId, destNearestNodeEdge.edge);
            path = aStarSearch(startNearestNodeEdge.nodeId, neighborNodeId);
            return path;
        }
        if (startNearestNodeEdge.nodeId !== destNearestNodeEdge.nodeId) {
            path = aStarSearch(startNearestNodeEdge.nodeId, destNearestNodeEdge.nodeId);
            return path;
        }
    }
    return null;
}

function solveSamePlaceCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (!startNearestNodeEdge.place.name || !destNearestNodeEdge.place.name) return null;
    if (startNearestNodeEdge.place.name === destNearestNodeEdge.place.name) {
        return [startNearestNodeEdge.pose, destNearestNodeEdge.pose];
    }
    return null;
}

function solveSameNodeCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge || !path || path.length > 1) return null;
    if (startNearestNodeEdge.nodeId === destNearestNodeEdge.nodeId) {
        if (startNearestNodeEdge.edge.roadId !== destNearestNodeEdge.edge.roadId) {
            // of course both are entring the node so only four cases
            if (!destNearestNodeEdge.edge.bi_directional) {
                // start -> node <- destination && start -- node <- destination
                neighbourNodeId = hdmap.getNeighbour(destNearestNodeEdge.nodeId, destNearestNodeEdge.edge);
                path = aStarSearch(startNearestNodeEdge.nodeId, neighborNodeId);
                return path;
            }
            if (destNearestNodeEdge.edge.bi_directional) {
                // start -> node -- destination && start -- node -- destination
                return [startNearestNodeEdge.nodeId];
            }
        }
    }
    return null;
}

function optimizerPipeline(startNearestNodeEdge, destNearestNodeEdge) {
    let path = solveSamePlaceCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        return path;
    }
    path = solveSameNodeCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        path = optimizePathStart(path, startNearestNodeEdge);
        //path = optimizePathEnd(path,destNearestNodeEdge);
        poses = convertPathtoPoses(path);
        poses = completePath(poses);
        return poses;
    }
    path = solveSameRoadCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        path = optimizePathStart(path, startNearestNodeEdge);
        path = optimizePathEnd(path, destNearestNodeEdge);
        poses = convertPathtoPoses(path);
        poses = completePath(poses);
        return poses;
    }
    let destId = null;
    if (destNearestNodeEdge.edge.bi_directional) {
        destId = destNearestNodeEdge.nodeId;
    } else {
        destId = hdmap.getNeighbour(destNearestNodeEdge.nodeId, destNearestNodeEdge.edge);
    }
    path = aStarSearch(startNearestNodeEdge.nodeId, destId);
    path = optimizePathStart(path, startNearestNodeEdge);
    path = optimizePathEnd(path, destNearestNodeEdge);
    poses = convertPathtoPoses(path);
    poses = completePath(poses);
    return poses;
}

function completePath(startNearestNodeEdge, destNearestNodeEdge, path) {
    let startArr = [startNearestNodeEdge.pose];
    let endArr = [destNearestNodeEdge.pose];
    if (!startNearestNodeEdge.place) startArr.push(startNearestNodeEdge.place.entrance_position);
    if (!destNearestNodeEdge.place) endArr.push(destNearestNodeEdge.place.entrance_position);
    return [...startArr, ...path, ...endArr];
}

function combinePaths(carNearestNodeEdge, startNearestNodeEdge, destNearestNodeEdge) {
    path1 = optimizerPipeline(carNearestNodeEdge, startNearestNodeEdge);
    // remove repeated start
    path1.pop();
    path2 = optimizerPipeline(startNearestNodeEdge, destNearestNodeEdge);
    return [...path1, ...path2];
}

function tripPlanning(start, destination) {
    if (!start || !destination) return null;
    if (start === destination) return null;
    //get places positions
    const starPosition = hdmap.getPlacePosition(start);
    const goalPosition = hdmap.getPlacePosition(destination);
    if (starPosition === null || goalPosition === null) return null;
    return this.getPath(starPosition, goalPosition)
}

function findFinalNearestNode(pose) {
    const NearestNodeEdge = hdmap.getNearestNode(pose);
    if (NearestNodeEdge === null) {
        return null;
    }
    let NearestNodeEdge2 = null;
    if ("place" in NearestNodeEdge) {
        position = NearestNodeEdge.place.entrance_position;
        NearestNodeEdge2 = hdmap.getNearestNode(position);
    }
    let finalId = 0;
    let finalEdge = null;
    let finalPlace = null;
    if (NearestNodeEdge2) {
        finalId = NearestNodeEdge2.nodeId;
        finalEdge = NearestNodeEdge2.edge;
        finalPlace = NearestNodeEdge.place;
    } else {
        finalId = NearestNodeEdge.nodeId;
        finalEdge = NearestNodeEdge.edge;
    }
    return {
        nodeId: finalId,
        edge: finalEdge,
        place: finalPlace,
        pose: pose,
    };
}

function getPath(start, destination) {
    // check if start and destination are valid
    if (!start || !destination) return null;
    if (start.x === destination.x && start.y === destination.y) return null;
    // get car pose and find nearest node
    const carposeInMeter = getCarpose()
    const carpose = convertPoseFromMetersToBlock(carposeInMeter);
    const carNearestNodeEdge = this.findFinalNearestNode(carpose);
    if (carNearestNodeEdge === null) {
        return null;
    }
    // find start nearest node
    const startNearestNodeEdge = this.findFinalNearestNode(start);
    if (startNearestNodeEdge === null) {
        return null;
    }
    // find destination nearest node
    const destNearestNodeEdge = this.findFinalNearestNode(destination);
    if (destNearestNodeEdge === null) {
        return null;
    }
    return combinePaths(carNearestNodeEdge, startNearestNodeEdge, destNearestNodeEdge);
}

function convertPathtoPoses(path) {
    const poses = [];
    for (const nodeId of path) {
        const node = hdmap.getNodeById(nodeId);
        if (!node) continue;
        poses.push({ x: node.x, y: node.y });
    }
    return poses;
}

function findDirectionOfRoad(edge) {
    const fromNode = hdmap.getNodeById(edge.from);
    const toNode = hdmap.getNodeById(edge.to);
    const dx = toNode.x - fromNode.x;
    const dy = toNode.y - fromNode.y;
    return { dx: dx, dy: dy }
}

function findStartDestDirection(startNearestNodeEdge, destNearestNodeEdge) {
    let p1 = null;
    let p2 = null;
    if (startNearestNodeEdge.place) {
        p1 = startNearestNodeEdge.place.entrance_position;
    } else {
        p1 = startNearestNodeEdge.pose;
    }
    if (destNearestNodeEdge.place) {
        p2 = destNearestNodeEdge.place.entrance_position;
    } else {
        p2 = destNearestNodeEdge.pose;
    }
    const dx = p2.x - p1.x;
    const dy = p2.y - p2.y;
    return { dx: dx, dy: dy };
}

function convertPosesTometers(poses) {
    if (!poses || poses.length === 0) return null;
    const convertedPoses = [];
    const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
    for (const pose of poses) {
        convertedPoses.push({ x: pose.x * blockSizeInMeter, y: pose.y * blockSizeInMeter });
    }
    return convertedPoses;
}

function convertPosesToPixels(poses) {
    if (!poses || poses.length === 0) return null;
    const convertedPoses = [];
    const blockSizeInPixel = hdmap.getBlockSizeInPixel();
    for (const pose of poses) {
        convertedPoses.push({ x: pose.x * blockSizeInPixel, y: pose.y * blockSizeInPixel });
    }
    return convertedPoses;
}

function convertPoseFromMetersToPixels(pose) {
    if (!pose) return null;
    const blockSizeInPixel = hdmap.getBlockSizeInPixel();
    const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
    return { x: (pose.x / blockSizeInMeter) * blockSizeInPixel, y: (pose.y / blockSizeInMeter) * blockSizeInPixel };
}

function convertPoseFromMetersToBlock(pose) {
    if (!pose) return null;
    const blockSizeInMeter = hdmap.getBlockSizeInFoot() * hdmap.getFoot();
    return { x: (pose.x / blockSizeInMeter), y: (pose.y / blockSizeInMeter) };
}

module.exports = { tripPlanning, getPath, convertPosesTometers, convertPosesToPixels, convertPoseFromMetersToPixels };
