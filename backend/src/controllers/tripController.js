const tripSchema = require("../models/trip");

// Sample Controller for Trip Operations
const tripController = {
    bookTrip: async (req, res) => {
        console.log("Received trip request:", req.body);
        try {
            const { startLocation, destination, tripDateTime} = req.body;

            // Validation (Check if data exists)
            if (!destination || !startLocation || !tripDateTime) {
                return res.status(400).json({ message: "Missing destination or start location or date" });
            }

            let state;
            const now = new Date();
            if (tripDateTime >= new Date(now.getTime()- 15*60*1000)) {
                state = "active";
            } else {
                state = "past";
            }
            newtrip = new tripSchema({
                username: req.user.username,
                tripDateTime: tripDateTime,
                startLocation: startLocation,
                destination: destination,
                state: state
            });
            await newtrip.save();
            return res.status(200).json({
                message: "Trip received and sent to car",
            });
        } catch (error) {
            return res.status(500).json({ error: error.message });
        }
    },
    deleteTrip: async (req, res) => { 
        try {
            await tripSchema.findOneAndUpdate({username: req.user.username},{$set: {state: "deleted"}});
            return res.status(200).json({ message: "Trip deleted successfully" });
        } 
        catch (error) {
                return res.status(500).json({ error: error.message });
        }
    },
    getTrips: async (req, res) => {
        try {
            const trips = await tripSchema.find({username: req.user.username});
            return res.status(200).json({ trips });
        } 
        catch (error) {
                return res.status(500).json({ error: error.message });
        }
    }
};

module.exports = tripController;