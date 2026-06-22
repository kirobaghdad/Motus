export const validTripBooking = {
    startLocation: "library",
    destination: "lab-3708",
    tripDateTime: new Date(Date.now() + 10 * 60 * 1000).toISOString() // 10 minutes from now
};

export const validImmediateTrip = {
    startLocation: { x: 27.5, y: 8.1 }, // Library entrance
    destination: { x: 11.5, y: 8.1 }    // lab-3708 entrance
};