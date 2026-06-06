const tripSchema = require("../models/trip"); 
const { tripPlanning} = require("../services/pathPlanning");
const cron = require('node-cron');




// This runs every 1 minute
cron.schedule('* * * * *', async () => {
    const now = new Date();
    
    // Find trips where time is NOW (or slightly past) and status is 'pending'
    const dueTrips = await tripSchema.find({
        tripDateTime: { $lte: now },
        state: 'active'
    });

    for (let trip of dueTrips) {
        console.log(`Trip ${trip._id} is starting now!`);
        
        // 1. Update trip status so we don't process it again
        trip.status = 'live';
        await trip.save();
        // Call PathPlanning service here
        const poses = tripPlanning(trip.startLocation, trip.destination);

        if (poses === null || poses === undefined){
            return res.status(500).json({message: "trip canceled can not find path"});
        }

        // Build payload to send to car(s)
        const payload = {
            tripId: trip._id,
            start: trip.startLocation,
            destination: trip.destination,
            poses: poses
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
        
    }
});
