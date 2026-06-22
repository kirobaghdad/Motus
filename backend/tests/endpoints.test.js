// tests/endpoints.test.js
import { describe, test, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import axios from 'axios';
import mongoose from 'mongoose';
import jwt from 'jsonwebtoken';

// Import car state to mock car position
const { updateCarPose, updateCarState } = require('../src/globals/carState');

// Import our DB helpers
import { connectDB, disconnectDB, clearDB } from './db-setup';

const API_URL = 'http://localhost:3000';
const JWT_SECRET = 'test-secret';

const validTripBooking = {
    startLocation: "library",
    destination: "lab-3708",
    tripDateTime: new Date(Date.now() + 10 * 60 * 1000).toISOString() // 10 minutes from now
};

const validImmediateTrip = {
    startLocation: { x: 27.5, y: 8.1 }, // Near library
    destination: { x: 11.5, y: 8.1 }    // Near lab-3708
};

const boundryImmediateTrip = {
    startLocation: { x: 27.5, y: 8.1 }, // Near library
    destination: { x: 5.5, y: 10 }    // boundry of hall-3704
};

// Mock environment variables BEFORE requiring app
process.env.JWT_SECRET_KEY = JWT_SECRET;
process.env.CAR_USERNAME = 'car1';

describe('Trip Routes Tests - GET /trips', () => {
    let authToken;
    const testUser = {
        username: 'user1',
        password: 'user1',
        email: 'user1@example.com'
    };

    beforeAll(async () => {
        // Start memory DB
        await connectDB();
        process.env.MONGO_URI = mongoose.connection._connectionString;

        // Start the server
        try {
            // Ensure fresh require
            delete require.cache[require.resolve('../src/app.js')];
            require('../src/app.js');
        } catch (err) {
            console.log("Server startup info (expected if models compiled):", err.message);
        }

        // Wait for server to be ready
        await new Promise(resolve => setTimeout(resolve, 3000));
    });

    beforeEach(async () => {
        await clearDB();

        // Get models from mongoose (they should be registered by app.js)
        const User = mongoose.model('user');
        const Token = mongoose.model('token');
        const Trip = mongoose.model('trip');

        // 1. Seed the test user
        await User.create(testUser);

        // 2. Generate and seed a valid token
        const payload = { username: testUser.username, email: testUser.email };
        const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });
        await Token.create({ username: testUser.username, token: token });
        authToken = `Bearer ${token}`;

        // 3. Seed some trips for this user
        await Trip.create([
            {
                username: testUser.username,
                startLocation: 'library',
                destination: 'lab-3708',
                tripDateTime: new Date(),
                state: 'active'
            },
            {
                username: testUser.username,
                startLocation: 'hall-3704',
                destination: 'lab-3707',
                tripDateTime: new Date(),
                state: 'past'
            }
        ]);

        // 4. Set car pose near node 0 (x=28, y=9)
        // blockSizeInMeter = 5.255 * 0.3 = 1.5765
        updateCarPose(27 * 1.5765, 9 * 1.5765);
        updateCarState(true);
    });

    afterAll(async () => {
        await disconnectDB();
    });

    test('GET /trips should return all trips for the authenticated user', async () => {
        const res = await axios.get(`${API_URL}/trips`, {
            headers: { authorization: authToken }
        });

        expect(res.status).toBe(200);
        expect(res.data.trips).toBeDefined();
        expect(Array.isArray(res.data.trips)).toBe(true);
        expect(res.data.trips.length).toBe(2);

        // Check contents
        const destinations = res.data.trips.map(t => t.destination);
        expect(destinations).toContain('lab-3708');
        expect(destinations).toContain('lab-3707');
    });

    test('POST /book-trip should successfully book a trip', async () => {
        try {
            const res = await axios.post(`${API_URL}/book-trip`, validTripBooking, {
                headers: { authorization: authToken }
            });
            console.log("Response status:", res.status);
            expect(res.status).toBe(201);
            expect(res.data.message).toBe('Trip received successfully');
        } catch (error) {
            if (error.response) {
                console.log("Error response body:", error.response.data);
                throw new Error(`POST /book-trip failed with status ${error.response.status}: ${JSON.stringify(error.response.data)}`);
            }
            throw error;
        }

        // Verify in DB - Trip created
        const Trip = mongoose.model('trip');
        const trip = await Trip.findOne({ username: testUser.username, destination: validTripBooking.destination });
        expect(trip).toBeDefined();
        expect(trip.startLocation).toBe(validTripBooking.startLocation);

        // Verify in DB - User popularPlaces updated
        const User = mongoose.model('user');
        const user = await User.findOne({ username: testUser.username });
        expect(user.popularPlaces).toContain(validTripBooking.destination);
    });

    test('DELETE /delete-trip should mark a trip as deleted', async () => {
        // 1. Seed a trip to delete
        const Trip = mongoose.model('trip');
        const trip = await Trip.create({
            username: testUser.username,
            startLocation: 'library',
            destination: 'lab-3708',
            tripDateTime: new Date(),
            state: 'active'
        });

        // 2. Send delete request
        const res = await axios.delete(`${API_URL}/delete-trip`, {
            data: { id: trip._id.toString() },
            headers: { authorization: authToken }
        });

        expect(res.status).toBe(201);
        expect(res.data.message).toBe('Trip deleted successfully');

        // 3. Verify in DB
        const updatedTrip = await Trip.findById(trip._id);
        expect(updatedTrip.state).toBe('deleted');
    });

    test('GET /immediate-trip should return a planned path', async () => {
        try {
            const res = await axios.get(`${API_URL}/immediate-trip`, {
                data: validImmediateTrip,
                headers: { authorization: authToken }
            });

            expect(res.status).toBe(200);
            expect(res.data.poses).toBeDefined();
            expect(Array.isArray(res.data.poses)).toBe(true);
            expect(res.data.poses.length).toBeGreaterThan(0);
        } catch (error) {
            if (error.response) {
                console.log("Error response body:", error.response.data);
                throw new Error(`GET /immediate-trip failed with status ${error.response.status}: ${JSON.stringify(error.response.data)}`);
            }
            throw error;
        }
    });

    test('GET /immediate-trip with pose on boundry should return a planned path', async () => {
        try {
            const res = await axios.get(`${API_URL}/immediate-trip`, {
                data: boundryImmediateTrip,
                headers: { authorization: authToken }
            });

            expect(res.status).toBe(200);
            expect(res.data.poses).toBeDefined();
            expect(Array.isArray(res.data.poses)).toBe(true);
            expect(res.data.poses.length).toBeGreaterThan(0);
        } catch (error) {
            if (error.response) {
                console.log("Error response body:", error.response.data);
                throw new Error(`GET /immediate-trip failed with status ${error.response.status}: ${JSON.stringify(error.response.data)}`);
            }
            throw error;
        }
    });
});