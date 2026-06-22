const { MongoMemoryServer } = require('mongodb-memory-server');
const mongoose = require('mongoose');

async function start() {
    const mongoServer = await MongoMemoryServer.create();
    const mongoUri = mongoServer.getUri();
    process.env.MONGO_URI = mongoUri;
    process.env.JWT_SECRET_KEY = 'test-secret';
    process.env.CAR_USERNAME = 'car1';
    
    console.log("Memory DB started at", mongoUri);
    
    // Require the app
    require('../src/app.js');
}

start().catch(console.error);
