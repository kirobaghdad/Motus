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
    if (startId === null || startId === undefined || goalId === null || goalId === undefined) return null;
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
        const edges = hdmap.getOutgoingEdges(currentId);
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
    if (!nearestNodeEdge || !path) return;
    const nearestEdge = nearestNodeEdge.edge;
    const nearestNode = nearestNodeEdge.nodeId;
    if (nearestEdge && path.length > 1) {
        const from = nearestEdge.from;
        const to = nearestEdge.to;
        if (path[0] === from || path[1] === to) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.shift();
            return;
        }
        if (path[0] === to || path[1] === from) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.shift();
            return;
        }
    }
    if (nearestNode !== null && nearestNode !== undefined) {
        if (path.length === 2) {
            path.shift();
        }
    }
}

function optimizePathEnd(path, nearestNodeEdge) {
    if (!nearestNodeEdge || !path) return;
    const nearestEdge = nearestNodeEdge.edge;
    const nearestNode = nearestNodeEdge.nodeId;
    if (nearestEdge && path.length > 1) {
        const from = nearestEdge.from;
        const to = nearestEdge.to;
        if (path[path.length - 2] === from || path[path.length - 1] === to) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.pop();
            return;
        }
        if (path[path.length - 2] === to || path[path.length - 1] === from) {
            // nearest node could be skiped and car go directly to next node remove first element of path
            path.pop();
            return;
        }
    }
    if (nearestNode !== null && nearestNode !== undefined) {
        path.pop();
    }
}

function solveEdgeNodeCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (startNearestNodeEdge.edge && destNearestNodeEdge.nodeId !== null && destNearestNodeEdge.nodeId !== undefined) {
        const edge = startNearestNodeEdge.edge;
        const nodeId = destNearestNodeEdge.nodeId;
        if ((edge.from === nodeId && edge.bi_directional) || edge.to === nodeId) {
            return [];
        }
    }
    if (destNearestNodeEdge.edge && startNearestNodeEdge.nodeId !== null && startNearestNodeEdge.nodeId !== undefined) {
        const edge = destNearestNodeEdge.edge;
        const nodeId = startNearestNodeEdge.nodeId;
        if (edge.from === nodeId || (edge.to === nodeId && edge.bi_directional)) {
            return [];
        }
    }
    return null;
}

function solveSameRoadCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (!startNearestNodeEdge.edge || !destNearestNodeEdge.edge) return null;
    if (startNearestNodeEdge.edge.roadId === destNearestNodeEdge.edge.roadId) {
        // same road but must make sure going directly to destination is in the same direction of road
        let pose1 = startNearestNodeEdge.pose;
        let pose2 = destNearestNodeEdge.pose;
        if (startNearestNodeEdge.place) {
            pose1 = startNearestNodeEdge.place.entrance_position;
        }
        if (destNearestNodeEdge.place) {
            pose2 = destNearestNodeEdge.place.entrance_position;
        }
        if (hdmap.IsValidDirection(startNearestNodeEdge.edge, pose1, pose2)) {
            return [];
        }
    }
    return null;
}

function solveSamePlaceCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (!startNearestNodeEdge.place || !destNearestNodeEdge.place) return null;
    if (startNearestNodeEdge.place.name === destNearestNodeEdge.place.name) {
        return [startNearestNodeEdge.pose, destNearestNodeEdge.pose];
    }
    return null;
}

function solveSameNodeCase(startNearestNodeEdge, destNearestNodeEdge) {
    if (!startNearestNodeEdge || !destNearestNodeEdge) return null;
    if (startNearestNodeEdge.nodeId === null || startNearestNodeEdge.nodeId === undefined || destNearestNodeEdge.nodeId === null || destNearestNodeEdge.nodeId === undefined) return null;
    if (startNearestNodeEdge.nodeId === destNearestNodeEdge.nodeId) {
        return [];
    }
    return null;
}

function optimizerPipeline(startNearestNodeEdge, destNearestNodeEdge) {
    let path = solveSamePlaceCase(startNearestNodeEdge, destNearestNodeEdge);
    let poses = null;
    if (path) {
        return path;
    }
    //if (!path) return null;
    path = solveSameNodeCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        poses = completePath(startNearestNodeEdge, destNearestNodeEdge, path);
        return poses;
    }
    path = solveSameRoadCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        poses = completePath(startNearestNodeEdge, destNearestNodeEdge, path);
        return poses;
    }
    path = solveEdgeNodeCase(startNearestNodeEdge, destNearestNodeEdge);
    if (path) {
        poses = completePath(startNearestNodeEdge, destNearestNodeEdge, path);
        return poses;
    }
    const destId = getAstarNode(destNearestNodeEdge, false);
    const startId = getAstarNode(startNearestNodeEdge, true);
    console.log("startId:", startId);
    console.log("destId:", destId);
    path = aStarSearch(startId, destId);
    console.log("Path after aStarSearch:", JSON.stringify(path));
    optimizePathStart(path, startNearestNodeEdge);
    console.log("Path after start optimization:", JSON.stringify(path));
    optimizePathEnd(path, destNearestNodeEdge);
    console.log("Path after end optimization:", JSON.stringify(path));
    if (!path)
        return null;
    poses = convertPathtoPoses(path);
    poses = completePath(startNearestNodeEdge, destNearestNodeEdge, poses);
    return poses;
}

function getAstarNode(nearestNodeEdge, isStart) {
    if (!nearestNodeEdge)
        return null;
    if (nearestNodeEdge.nodeId !== null && nearestNodeEdge.nodeId !== undefined)
        return nearestNodeEdge.nodeId;
    if (nearestNodeEdge.edge.bi_directional) {
        let pose = nearestNodeEdge.pose;
        if (nearestNodeEdge.place)
            pose = nearestNodeEdge.place.entrance_position;
        return hdmap.getNearestNodeInEdge(nearestNodeEdge.edge, pose)
    }
    if (isStart)
        return nearestNodeEdge.edge.to;
    else
        return nearestNodeEdge.edge.from;
}

function completePath(startNearestNodeEdge, destNearestNodeEdge, path) {
    let startArr = [startNearestNodeEdge.pose];
    let endArr = [destNearestNodeEdge.pose];
    if (startNearestNodeEdge.place) startArr.push(startNearestNodeEdge.place.entrance_position);
    if (destNearestNodeEdge.place) endArr.unshift(destNearestNodeEdge.place.entrance_position);
    return [...startArr, ...path, ...endArr];
}

function combinePaths(carNearestNodeEdge, startNearestNodeEdge, destNearestNodeEdge) {
    const path1 = optimizerPipeline(carNearestNodeEdge, startNearestNodeEdge);
    if (!path1) return null;
    // remove repeated start
    path1.pop();
    const path2 = optimizerPipeline(startNearestNodeEdge, destNearestNodeEdge);
    if (!path2) return null;
    return [...path1, ...path2];
}

function tripPlanning(start, destination) {
    if (!start || !destination) return null;
    if (start === destination) return null;
    //get places positions
    const starPosition = hdmap.getPlacePosition(start);
    const goalPosition = hdmap.getPlacePosition(destination);
    if (starPosition === null || goalPosition === null) return null;

    const path = getPath(starPosition, goalPosition)
    return path;
}

function findFinalNearestNode(pose) {
    const nearestNodeEdge = hdmap.findRegionInMap(pose);
    if (nearestNodeEdge === null) {
        return null;
    }
    let nearestNodeEdge2 = null;
    let finalPlace = null;
    if ("place" in nearestNodeEdge) {
        finalPlace = nearestNodeEdge.place;
        const position = nearestNodeEdge.place.entrance_position;
        nearestNodeEdge2 = hdmap.findRegionInMap(position);
    }
    let finalId = null;
    let finalEdge = null;

    if (nearestNodeEdge2) {
        //finalPlace = nearestNodeEdge.place;
        if ("edge" in nearestNodeEdge2) {
            finalEdge = nearestNodeEdge2.edge;
        } else {
            finalId = nearestNodeEdge2.nodeId;
        }
    } else {
        if ("edge" in nearestNodeEdge) {
            finalEdge = nearestNodeEdge.edge;
        } else {
            finalId = nearestNodeEdge.nodeId;
        }
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
    const carposeInMeter = getCarPose();
    const carpose = convertPoseFromMetersToBlock(carposeInMeter);
    const carNearestNodeEdge = findFinalNearestNode(carpose);
    if (carNearestNodeEdge === null) {
        return null;
    }
    // find start nearest node
    const startNearestNodeEdge = findFinalNearestNode(start);
    if (startNearestNodeEdge === null) {
        return null;
    }
    // find destination nearest node
    const destNearestNodeEdge = findFinalNearestNode(destination);
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

function convertPosesToMeters(poses) {
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

module.exports = { tripPlanning, getPath, convertPosesToMeters, convertPosesToPixels, convertPoseFromMetersToPixels };
