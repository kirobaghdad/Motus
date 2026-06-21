import { describe, test, expect, beforeAll, afterAll } from 'vitest';
import axios from 'axios';
import { io } from 'socket.io-client';
import { validTrips, invalidTrips } from './payloads';

const API_URL = 'http://localhost:5000/api';
const WS_URL = 'http://localhost:5000';

describe('Backend Integration & Socket Tests', () => {
    let clientSocket;

    // 1. Setup: Establish socket connection BEFORE running tests
    beforeAll(() => {
        return new Promise((resolve, reject) => {
            clientSocket = io(WS_URL, { transient: true, forceNew: true });
            clientSocket.on('connect', () => resolve());
            clientSocket.on('connect_error', (err) => reject(err));
        });
    });

    // 2. Teardown: Safely close socket AFTER tests complete so Vitest doesn't hang
    afterAll(() => {
        if (clientSocket && clientSocket.connected) {
            clientSocket.disconnect();
        }
    });

    // --- HTTP Endpoints Tests using loops ---
    test.each(validTrips)('should accept valid trip creation request', async (payload) => {
        const res = await axios.post(`${API_URL}/trips/create`, payload);
        expect(res.status).toBe(201);
        expect(res.data).toHaveProperty('tripId');
    });

    test.each(invalidTrips)('should reject bad trip payloads with 400 Bad Request', async (payload) => {
        try {
            await axios.post(`${API_URL}/trips/create`, payload);
        } catch (error) {
            expect(error.response.status).toBe(400);
        }
    });

    // --- WebSocket Test ---
    test('should broadcast "trip_started" to client when trip time triggers', () => {
        const sampleTrip = { tripId: 'TRIP-777', status: 'active' };

        return new Promise((resolve, reject) => {
            // Set up the listener FIRST to catch the backend's emission
            clientSocket.on('trip_started', (data) => {
                try {
                    expect(data.tripId).toBe('TRIP-777');
                    expect(data.status).toBe('active');
                    resolve(); // Success! Test passes.
                } catch (error) {
                    reject(error); // Assertion failed
                }
            });

            // Simulating a client or backend event action
            clientSocket.emit('initialize_trip', sampleTrip);
        });
    });
});