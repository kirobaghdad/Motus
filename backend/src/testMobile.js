// testMobile.js
// Usage: node src/testMobile.js [serverUrl]
// Example: node src/testMobile.js http://localhost:3000

const io = require('socket.io-client');

const serverUrl = process.argv[2] || process.env.SERVER_URL || 'http://localhost:3000';
const socket = io(serverUrl);

socket.on('connect', () => {
  console.log('Mobile connected', socket.id);
});

socket.on('update-mobile-map', (data) => {
  console.log('Mobile received update:', data);
});

socket.on('disconnect', () => {
  console.log('Mobile disconnected');
});
