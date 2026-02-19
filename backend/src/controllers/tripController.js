const { tripPlanning } = require("../services/pathPlanning");
const tripSchema = require("../models/trip");
const trip = require("../models/trip");

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
            /*
            console.log(`Booking a trip from ${JSON.stringify(start)} to ${JSON.stringify(destination)}`);

            // Call PathPlanning service here
            //const poses = tripPlanning(start, destination);

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
                io.emit('path', payload);
                console.log('send sub-goals to car');
            } else {
                console.warn('Socket.io not available on app; cannot send sub-goals');
            }
            */
            let state;
            if (tripDateTime >= new Date()) {
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