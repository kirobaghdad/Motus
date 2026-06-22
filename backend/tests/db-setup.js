// tests/db-setup.js
import { MongoMemoryServer } from 'mongodb-memory-server';
import mongoose from 'mongoose';

let mongoServer;

/**
 * Starts the in-memory MongoDB instance and connects Mongoose to it.
 */
export async function connectDB() {
    // 1. Spin up the background MongoDB binary in memory
    mongoServer = await MongoMemoryServer.create();
    const mongoUri = mongoServer.getUri();

    // 2. Connect Mongoose to this temporary URI
    await mongoose.connect(mongoUri);
}

/**
 * Disconnects Mongoose and cleanly shuts down the in-memory server.
 */
export async function disconnectDB() {
    await mongoose.disconnect();
    if (mongoServer) {
        await mongoServer.stop();
    }
}

/**
 * Clears out all collections (useful between tests to keep them isolated)
 */
export async function clearDB() {
    const collections = mongoose.connection.collections;
    for (const key in collections) {
        await collections[key].deleteMany({});
    }
}

/**
 * Seeds initial mock data into your database for testing
 * @param {import('mongoose').Model} model - Your Mongoose Model (e.g., Trip, User)
 * @param {Array} data - Array of mock documents to insert
 */
export async function seedInitialData(model, data) {
    await model.insertMany(data);
}