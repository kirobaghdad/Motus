import { describe, test, expect, beforeAll, afterAll, beforeEach, vi } from 'vitest';
import mongoose from 'mongoose';

// Import our DB helpers
import { connectDB, disconnectDB, clearDB } from './db-setup';

// Import carState globals to control them
const { updateCarState, updateCarPose } = require('../src/globals/carState');

describe('Cron Job and Socket Logic Tests', () => {
    let cronCallback;
    let mockIo;
    let Trip;
    let cron;
    let pathHandler;

    beforeAll(async () => {
        await connectDB();
        // Explicitly register models
        require('../src/models/trip');
        Trip = mongoose.model('trip');

        // Mock node-cron before requiring pathHandler
        cron = require('node-cron');
        vi.spyOn(cron, 'schedule').mockImplementation((pattern, cb) => {
            cronCallback = cb;
            return { stop: vi.fn(), start: vi.fn() };
        });

        // We must clear require cache to ensure it uses the mocked cron 
        // if it was already required elsewhere
        delete require.cache[require.resolve('../src/sockets/pathHandler')];
        pathHandler = require('../src/sockets/pathHandler');

        mockIo = {
            to: vi.fn().mockReturnThis(),
            emit: vi.fn().mockReturnThis()
        };

        // Initialize pathHandler which calls cron.schedule
        await pathHandler(mockIo);
    });

    afterAll(async () => {
        await disconnectDB();
    });

    beforeEach(async () => {
        await clearDB();
        vi.clearAllMocks();
        updateCarState(true); // Car is free by default

        // Initialize car pose (node 0 is approx 28, 9)
        const blockSizeInMeter = 5.255 * 0.3;
        updateCarPose(27 * blockSizeInMeter, 9 * blockSizeInMeter);
    });

    test('Trip should execute when time is due and car is free', async () => {
        const now = Date.now();
        const trip = await Trip.create({
            username: 'user1',
            startLocation: 'library',
            destination: 'lab-3708',
            tripDateTime: new Date(now),
            state: 'active'
        });

        // Trigger cron
        await cronCallback();

        // Verify trip state changed to live
        const updatedTrip = await Trip.findById(trip._id);
        expect(updatedTrip.state).toBe('live');

        // Verify socket emits
        expect(mockIo.to).toHaveBeenCalledWith('only-car');
        expect(mockIo.emit).toHaveBeenCalledWith('path', expect.objectContaining({
            tripId: trip._id,
            username: 'user1'
        }));
    });

    test('Trip should execute within 5-minute tolerance', async () => {
        const now = Date.now();
        const trip = await Trip.create({
            username: 'user1',
            startLocation: 'library',
            destination: 'lab-3708',
            tripDateTime: new Date(now - 4 * 60 * 1000), // 4 mins late
            state: 'active'
        });

        await cronCallback();

        const updatedTrip = await Trip.findById(trip._id);
        expect(updatedTrip.state).toBe('live');
    });

    test('Trip should be cancelled after 5-minute tolerance', async () => {
        const now = Date.now();
        const trip = await Trip.create({
            username: 'user1',
            startLocation: 'library',
            destination: 'lab-3708',
            tripDateTime: new Date(now - 6 * 60 * 1000), // 6 mins late
            state: 'active'
        });

        await cronCallback();

        const updatedTrip = await Trip.findById(trip._id);
        expect(updatedTrip.state).toBe('past');

        // Verify cancellation emit
        expect(mockIo.to).toHaveBeenCalledWith('exact-user1');
        expect(mockIo.emit).toHaveBeenCalledWith('canceled', { tripId: trip._id });
    });

    test('Trip should be delayed if car is busy', async () => {
        updateCarState(false); // Car is BUSY

        const now = Date.now();
        const trip = await Trip.create({
            username: 'user1',
            startLocation: 'library',
            destination: 'lab-3708',
            tripDateTime: new Date(now),
            state: 'active'
        });

        await cronCallback();

        // Trip should still be active (not live, not past)
        const updatedTrip = await Trip.findById(trip._id);
        expect(updatedTrip.state).toBe('active');

        // No path emitted
        const pathEmits = mockIo.emit.mock.calls.filter(call => call[0] === 'path');
        expect(pathEmits.length).toBe(0);
    });
});
