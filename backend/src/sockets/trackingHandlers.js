module.exports = (io) => {
    io.on("connection", (socket) => {
        console.log("a device connected:", socket.id);

        // 1. Receive position from Car
        socket.on('car-position', (data) => {
            // data = { carId: "001", lat: 12.34, lng: 56.78 }
            console.log("Car moved:", data);

            // 2. Send it immediately to the Mobile App
            io.emit('update-mobile-map', data);
        });

        socket.on('disconnect', () => {
            console.log('Device disconnected', socket.id);
        });
    });
};