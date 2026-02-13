const { tripPlanning } = require("../services/pathPlanning");

// Sample Controller for Trip Operations
const tripController = async (req, res) => {

    console.log("Received trip request:", req.body);
    try {
        const { start, destination} = req.body;

        // Validation (Check if data exists)
        if (!destination || !start) {
            return res.status(400).json({ message: "Missing destination or start location" });
        }

        console.log(`Booking a trip from ${JSON.stringify(start)} to ${JSON.stringify(destination)}`);

        // Call PathPlanning service here
        const poses = tripPlanning(start, destination);

        if (poses === null || poses === undefined){
            return res.status(500).json({message: "trip canceled can not find path"});
        }

        // Build payload to send to car(s)
        const payload = {
            tripId: Date.now().toString(),
            start,
            destination,
            poses
        };

        // Get io from express app and send to target car if known
        const io = req.app.get('io');
        if (io) {
            // broadcast if no specific carId provided or not connected
            io.emit('sub-goals', payload);
            console.log('send sub-goals to car');
        } else {
            console.warn('Socket.io not available on app; cannot send sub-goals');
        }

        return res.status(200).json({
            message: "Trip received and sent to car",
            tripId: payload.tripId
        });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
};

module.exports = tripController;