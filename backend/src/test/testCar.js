// testCar.js
// Usage: node src/testCar.js [serverUrl] [carId]
// Example: node src/testCar.js http://localhost:3000 001

const io = require('socket.io-client');

const socket = io('http://localhost:3000');

socket.on('connect', () => {
  console.log('Car connected', socket.id);

  let lat = parseFloat(process.env.INIT_LAT) || 12.34;
  let lng = parseFloat(process.env.INIT_LNG) || 56.78;

  // Listen for path/sub-goals from the server
  socket.on('path', (payload) => {
    console.log('Car received sub-goals:', payload);
    if (payload && Array.isArray(payload.poses)) {
      console.log('Path poses:');
      payload.poses.forEach((p, idx) => {
        console.log(`  ${idx}: lat=${p.lat}, lng=${p.lng}`);
      });
    }
  });

  setInterval(() => {
    // simulate small movement
    lat += (Math.random() - 0.5) * 0.0005;
    lng += (Math.random() - 0.5) * 0.0005;
    const pos = { lat: parseFloat(lat.toFixed(6)), lng: parseFloat(lng.toFixed(6)), ts: Date.now() };
    socket.emit('car-position', pos);
    console.log('sent', pos);
  }, 1000);
});