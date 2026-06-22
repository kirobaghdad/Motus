// tests/pathPlanningOptimization.test.js
import { describe, test, expect, beforeAll } from 'vitest';
const { getPath } = require('../src/services/pathPlanning');
const { updateCarPose } = require('../src/globals/carState');
const hdmap = require('../src/globals/mapState');

const BLOCK_SIZE_IN_METER = 1.5765; // 5.255 * 0.3

describe('Path Planning Optimization Tests', () => {

    test('Case 1: Car Pose in Place (Library), Start in Node 1, Destination in Node 0', () => {
        // Library entrance is {x: 27.5, y: 8.1}
        // Set car pose inside Library (e.g., {x: 25, y: 4})
        updateCarPose(25 * BLOCK_SIZE_IN_METER, 4 * BLOCK_SIZE_IN_METER);

        const start = { x: 29.5, y: 9 }; // Node 1
        const destination = { x: 3.65, y: 9 }; // Node 0

        const poses = getPath(start, destination);

        expect(poses).toBeDefined();
        expect(poses.length).toBeGreaterThan(0);

        console.log("Case 1 Poses:", JSON.stringify(poses));

        // Expected path sequence (simplified):
        // 1. Car pose (25, 4)
        // 2. Library entrance (27.5, 8.1)
        // 3. Node 1 (29.5, 9)
        // 4. Node 0 (3.65, 9)

        const roundPose = (p) => ({ x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100 });

        expect(roundPose(poses[0])).toEqual({ x: 25, y: 4 });
        expect(roundPose(poses[1])).toEqual({ x: 27.5, y: 8.1 });
        expect(roundPose(poses[poses.length - 2])).toEqual({ x: 29.5, y: 9 });
        expect(roundPose(poses[poses.length - 1])).toEqual({ x: 3.65, y: 9 });
    });

    test('Case 2: Car Pose at Node 1, Start in Place (Library), Destination in Node 0', () => {
        // Set car pose at Node 1 {x: 29.5, y: 9}
        updateCarPose(29.5 * BLOCK_SIZE_IN_METER, 9 * BLOCK_SIZE_IN_METER);

        const start = { x: 27.5, y: 8.1 }; // Library entrance (in Library)
        const destination = { x: 3.65, y: 9 }; // Node 0

        const poses = getPath(start, destination);

        expect(poses).toBeDefined();
        expect(poses.length).toBeGreaterThan(0);

        // Expected path sequence:
        // 1. Car pose (29.5, 9)
        // 2. Library entrance (27.5, 8.1)
        // 3. Node 0 (3.65, 9)

        const roundPose = (p) => ({ x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100 });

        expect(roundPose(poses[0])).toEqual({ x: 29.5, y: 9 });
        expect(roundPose(poses[1])).toEqual({ x: 27.5, y: 8.1 });
        expect(roundPose(poses[poses.length - 1])).toEqual({ x: 3.65, y: 9 });
    });

    test('Case 3: Car Pose at Node 0, Start in Node 1, Destination in Place (Lab-3708)', () => {
        // Set car pose at Node 0 {x: 3.65, y: 9}
        updateCarPose(3.65 * BLOCK_SIZE_IN_METER, 9 * BLOCK_SIZE_IN_METER);

        const start = { x: 29.5, y: 9 }; // Node 1
        const destination = { x: 11.5, y: 8.1 }; // Lab-3708 entrance

        const poses = getPath(start, destination);

        expect(poses).toBeDefined();
        expect(poses.length).toBeGreaterThan(0);

        // Expected path sequence:
        // 1. Car pose (3.65, 9)
        // 2. Node 1 (29.5, 9)
        // 3. Lab-3708 entrance (11.5, 8.1)

        const roundPose = (p) => ({ x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100 });

        expect(roundPose(poses[0])).toEqual({ x: 3.65, y: 9 });
        expect(roundPose(poses[poses.length - 2])).toEqual({ x: 29.5, y: 9 });
        expect(roundPose(poses[poses.length - 1])).toEqual({ x: 11.5, y: 8.1 });
    });
});
