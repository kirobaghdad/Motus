const express = require('express');
const router = express.Router();
const tripController = require('../controllers/tripController');
const authenticateJWT = require('../middleware/authentication');

router.post('/book-trip', authenticateJWT, tripController.bookTrip);
router.delete('/delete-trip', authenticateJWT, tripController.deleteTrip);
router.get('/trips', authenticateJWT, tripController.getTrips);

module.exports = router;