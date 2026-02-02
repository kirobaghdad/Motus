module.exports = (io) => {
    // Maintain a mapping of carId -> socketId for targeted emits
    io.carSockets = new Map();

    io.on("connection", (socket) => {
        console.log("a device connected:", socket.id);

        // Allow cars to explicitly register their id
        socket.on('register-car', (data) => {
            // data = { carId: "001" }
            if (data && data.carId) {
                io.carSockets.set(data.carId, socket.id);
                console.log(`Car registered: ${data.carId} -> ${socket.id}`);
            }
        });

        // 1. Receive position from Car
        socket.on('car-position', (data) => {
            // data = { carId: "001", lat: 12.34, lng: 56.78 }
            console.log("Car moved:", data);

            if (data && data.carId) {
                // keep mapping fresh when car sends position
                io.carSockets.set(data.carId, socket.id);
            }

            // 2. Send it immediately to the Mobile App
            io.emit('update-mobile-map', data);
        });

        socket.on('disconnect', () => {
            console.log('Device disconnected', socket.id);
            // Remove any car mappings for this socket
            for (const [carId, sId] of io.carSockets.entries()) {
                if (sId === socket.id) {
                    io.carSockets.delete(carId);
                    console.log(`Unregistered car ${carId} for socket ${socket.id}`);
                }
            }
        });
    });
};