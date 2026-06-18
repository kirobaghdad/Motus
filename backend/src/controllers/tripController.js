const tripSchema = require("../models/trip");
const userSchema = require("../models/user");
const hdmap = require("../globals/mapState");
const validator = require("../services/validation");
const parsePose = require("../utils/parser");
const {getPath, convertPosesTometers, convertPosesToPixels} = require("../services/pathPlanning");

const tripController = {
    bookTrip: async (req, res) => {
        expected_body = {
            startLocation: "string",
            destination: "string",
            tripDateTime: "string"
        };
        if(!validator(req.body, expected_body)){
            return res.status(400).json({message:"error in body format"});
        }
        console.log("Received trip request:", req.body);
        try {
            const { startLocation, destination, tripDateTime} = req.body;

            // Validation
            if (!destination || !startLocation || !tripDateTime) {
                return res.status(400).json({ message: "Missing destination or start location or date" });
            }
            startPlace = hdmap.getPlaceByName(startLocation);
            destPlace = hdmap.getPlaceByName(destination);
            if (!startPlace || !destPlace) {
                return res.status(400).json({message:"places not exist"});
            }
            let user = await userSchema.findOne({username:req.user.username});
            if (!user) {
                return res.status(404).json({message: 'User not found'});
            }
            currentPopularPlaces = user.popularPlaces;
            // Update popular places if not already in the list
            if (!currentPopularPlaces.includes(destination)) {
                currentPopularPlaces.push(destination);
                user.popularPlaces = currentPopularPlaces;
                await user.save();
            }
            let state;
            const now = new Date();
            const tripDateTimeConverted = new Date(tripDateTime)
            if (isNaN(tripDateTimeConverted.getTime())) {
                return res.status(400).json({ error: "Date time is not valid string" });
            }
            if (tripDateTimeConverted >= new Date(now.getTime() - 3*60*1000)) {
                state = "active";
            } else {
                state = "past";
                return res.status(400).json({
                message: "Trip date is in past"
                });
            }
            newtrip = new tripSchema({
                username: req.user.username,
                tripDateTime: tripDateTimeConverted,
                startLocation: startLocation,
                destination: destination,
                state: state
            });
            await newtrip.save();
            return res.status(201).json({
                message: "Trip received successfully"
            });
        } catch (error) {
            return res.status(500).json({ error: error.message });
        }
    },
    deleteTrip: async (req, res) => { 
        expected_body = {
            id: "string"
        };
        if(!validator(req.body, expected_body)){
            return res.status(400).json({message:"error in body format"});
        }
        try {
            await tripSchema.findByIdAndUpdate(req.body.id, {state: "deleted"});
            return res.status(201).json({ message: "Trip deleted successfully" });
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
    },
    executeTrip: (req, res) => {
        // validation first
        expected_body = {
            startLocation: "object",
            destination: "object"
        };
        if(!validator(req.body, expected_body)){
            return res.status(400).json({message:"error in body format"});
        }
        expected_body = {
            x: "number",
            y: "number"
        };
        if(!validator(req.body.startLocation, expected_body)){
            return res.status(400).json({message:"error in body format"});
        }
        if(!validator(req.body.destination, expected_body)){
            return res.status(400).json({message:"error in body format"});
        }
        // get path
        const { startLocation, destination} = req.body;
        startLocation = parsePose(startLocation);
        destination = parsePose(destination);
        poses = getPath(startLocation, destination);
        // Build payload to send to car
        const payload1 = {
            start: startLocation,
            destination: destination,
            poses: convertPosesTometers(poses)
        };
        // Build payload to send to mobile app
        const payload2 = {
            start: startLocation,
            destination: destination,
            poses: convertPosesToPixels(poses)
        };
        // send to car
        io = req.app.get('io');

        if (io) {
            io.to("only-car").emit("path",payload1);
            return res.status(200).json(payload2);
        }
        return res.status(500).json({error:"can not send trip to car"});
    }
};

module.exports = tripController;