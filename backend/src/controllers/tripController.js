const { aStarSearch } = require("../services/pathPlanning");

// Sample Controller for Trip Operations
const tripController = {
    // 1. Receive trip target from Mobile App
    requestTrip: async (req, res) => {
        console.log("Received trip request:", req.body);
        try {
            const { start, destination} = req.body;

            // Validation (Check if data exists)
            if (!destination || !start) {
                return res.status(400).json({ message: "Missing destination or start location" });
            }

            console.log(`Booking a trip from ${start} to ${destination}`);

            // TODO: Call your PathPlanning service here
            path = aStarSearch(start,destination)
            // TODO: Send command to car via Socket.io

            return res.status(200).json({
                message: "Trip received and sent to car",
            });
        } catch (error) {
            return res.status(500).json({ error: error.message });
        }
    }
};

module.exports = tripController;