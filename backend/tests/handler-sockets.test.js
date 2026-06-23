import { describe, test, expect, beforeAll, afterAll, beforeEach, vi } from 'vitest';
import mongoose from 'mongoose';
import { connectDB, disconnectDB, clearDB } from './db-setup';

// Import globals to monitor car modifications
const { updateCarState } = require('../src/globals/carState');

// Setup environment variables expected by your registration handlers
process.env.CAR_USERNAME = 'autonomous_car';
process.env.CAR_PASSWORD = 'secure_car_password';

describe('Socket Handlers Tests (Register, Track, and Trip Complete)', () => {
    let User;
    let Trip;
    let mockIo;
    let mockSocket;

    beforeAll(async () => {
        await connectDB();

        // Explicitly register your database models
        require('../src/models/user');
        require('../src/models/trip');
        User = mongoose.model('user');
        Trip = mongoose.model('trip');
    });

    afterAll(async () => {
        await disconnectDB();
    });

    beforeEach(async () => {
        await clearDB();
        vi.clearAllMocks();

        // Re-initialize mock io architecture based on socketManager.js
        mockIo = {
            users: new Map(),
            to: vi.fn().mockReturnThis(),
            emit: vi.fn().mockReturnThis()
        };

        // Re-initialize mock individual client socket
        mockSocket = {
            id: 'mock_socket_123',
            join: vi.fn()
        };
    });

    // ==========================================
    // 1. TESTS FOR registerUser.js
    // ==========================================
    describe('registerUser Handler', () => {
        const registerUser = require('../src/sockets/registerUser');

        test('should register the autonomous car into its specific private room', async () => {
            const carPayload = {
                username: 'autonomous_car',
                password: 'secure_car_password'
            };

            await registerUser(carPayload, mockSocket, mockIo);

            // Car should join the isolated room and map its ID
            expect(mockSocket.join).toHaveBeenCalledWith('only-car');
            expect(mockIo.users.get('autonomous_car')).toBe('mock_socket_123');
        });

        test('should authenticate a standard user, save socket map, and join rooms', async () => {
            // Seed a valid user inside our in-memory database
            await User.create({
                username: 'ali_samy',
                password: 'hashed_password_abc123',
                email: 'alisamy@gmail.com'
            });

            const userPayload = {
                username: 'ali_samy',
                password: 'hashed_password_abc123'
            };

            await registerUser(userPayload, mockSocket, mockIo);

            // User should join regular room structures and map properly
            expect(mockSocket.join).toHaveBeenCalledWith('all-users');
            expect(mockSocket.join).toHaveBeenCalledWith('exact-ali_samy');
            expect(mockIo.users.get('ali_samy')).toBe('mock_socket_123');
        });

        test('should reject registration if payload attributes do not match validation definitions', async () => {
            const badPayload = { username: 'ali_samy' }; // Missing password completely

            await registerUser(badPayload, mockSocket, mockIo);

            expect(mockSocket.join).not.toHaveBeenCalled();
            expect(mockIo.users.size).toBe(0);
        });
    });

    // ==========================================
    // 2. TESTS FOR trackingHandler.js
    // ==========================================
    describe('trackingHandler Handler', () => {
        const trackingHandler = require('../src/sockets/trackingHandler');

        test('should update car coordinates and broadcast to all users if event comes from car socket', async () => {
            // Map the car username to our testing socket identifier
            mockIo.users.set('autonomous_car', 'mock_socket_123');

            const trackingPayload = { x: 12.5, y: 45.2 };

            await trackingHandler(trackingPayload, mockSocket, mockIo);

            // Verify room broadcast happened safely
            expect(mockIo.to).toHaveBeenCalledWith('all-users');
            expect(mockIo.emit).toHaveBeenCalledWith('update-car-position', expect.any(Object));
        });

        test('should completely ignore tracking update if sender is an ordinary user socket', async () => {
            // Map car to a completely different socket identifier
            mockIo.users.set('autonomous_car', 'different_car_socket_999');

            const trackingPayload = { x: 12.5, y: 45.2 };

            await trackingHandler(trackingPayload, mockSocket, mockIo);

            // Broadcast should never trigger
            expect(mockIo.to).not.toHaveBeenCalled();
            expect(mockIo.emit).toHaveBeenCalledTimes(0);
        });
    });

    // ==========================================
    // 3. TESTS FOR tripHandler.js
    // ==========================================
    describe('tripHandler Handler', () => {
        const tripHandler = require('../src/sockets/tripHandler');

        test('should update database trip state to past and notify user upon routine trip completion', async () => {
            // Set car socket identity match
            mockIo.users.set('autonomous_car', 'mock_socket_123');
            updateCarState(false); // Make car busy initially

            // Seed a live test trip document inside database
            const activeTrip = await Trip.create({
                username: 'ali_samy',
                startLocation: 'library',
                destination: 'lab-3708',
                tripDateTime: new Date(),
                state: 'live'
            });

            const completePayload = {
                tripId: activeTrip._id.toString(),
                immediate: false,
                completed: true,
                username: 'ali_samy'
            };

            await tripHandler(completePayload, mockSocket, mockIo);

            // Car state tracker global should be freed up instantly
            // (Assumes updateCarState tracks status cleanly)

            // Database status verification
            const updatedTrip = await Trip.findById(activeTrip._id);
            expect(updatedTrip.state).toBe('past');

            // Verify socket response room notifications
            expect(mockIo.to).toHaveBeenCalledWith('exact-ali_samy');
            expect(mockIo.emit).toHaveBeenCalledWith('trip-status', completePayload);
        });

        test('should keep car available and broadcast payload updates directly on immediate trips without db update', async () => {
            mockIo.users.set('autonomous_car', 'mock_socket_123');

            const immediatePayload = {
                tripId: new mongoose.Types.ObjectId().toString(),
                immediate: true,
                completed: true,
                username: 'ali_samy'
            };

            await tripHandler(immediatePayload, mockSocket, mockIo);

            // Socket status changes still broadcast out to target client
            expect(mockIo.to).toHaveBeenCalledWith('exact-ali_samy');
            expect(mockIo.emit).toHaveBeenCalledWith('trip-status', immediatePayload);
        });
    });
});