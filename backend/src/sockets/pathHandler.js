const tripSchema = require("../models/trip");
const { updateCarState, getCarState } = require("../globals/carState");
const { tripPlanning, convertPosesToPixels, convertPosesToMeters } = require("../services/pathPlanning");
const cron = require('node-cron');
const hdmap = require("../globals/mapState");



// This runs every 1 minute
// schedule: ( minute hour monthDay month weekDay) * means every value
module.exports = async (io) => {
    cron.schedule('* * * * *', async () => {
        const now = Date.now();

        // Find trips where time is NOW (or slightly past) and status is 'pending'
        const dueTrips = await tripSchema.find({
            tripDateTime: {
                $lte: now
            },
            state: 'active'
        });

        for (let trip of dueTrips) {
            if (trip.tripDateTime.getTime() < new Date(now - 5 * 60 * 1000)) {
                // trip time has passed the tolerance time for delay
                cancelTrip(trip, io);
                continue;
            }
            if (!getCarState()) {
                continue;
            }
            console.log(`Trip ${trip._id} is starting now!`);

            // Call PathPlanning service here
            const poses = tripPlanning(trip.startLocation, trip.destination);

            if (poses === null || poses === undefined) {
                cancelTrip(trip, io);
                continue;
            }

            startPosition = hdmap.getPlaceByName(trip.startLocation).entrance_position;
            convertedStartPosition = convertPosesToMeters([startPosition])[0];

            // Build payload to send to car
            const payload1 = {
                tripId: trip._id,
                start: convertedStartPosition,
                username: trip.username,
                poses: convertPosesToMeters(poses)
            };
            // Build payload to send to mobile app
            const payload2 = {
                tripId: trip._id,
                start: trip.startLocation,
                destination: trip.destination,
                poses: convertPosesToPixels(poses)
            };

            if (io) {
                io.to('only-car').emit('path', payload1);
                io.to(`exact-${trip.username}`).emit('path-display', payload2)
                console.log('send sub-goals to car and mobile app');
            } else {
                console.warn('Socket.io not available on app; cannot send sub-goals');
                cancelTrip(trip, io);
                continue;
            }

            // update trip state to live
            trip.state = 'live';
            try {
                await trip.save();
            } catch (error) {
                console.error("can not update canceled trip", error);
            }
            updateCarState(false);

        }
    });

};

async function cancelTrip(trip, io) {
    trip.state = 'past';
    try {
        await trip.save();
    } catch (error) {
        console.error("can not update canceled trip", error);
    }
    io.to(`exact-${trip.username}`).emit('canceled', { tripId: trip._id })
};

