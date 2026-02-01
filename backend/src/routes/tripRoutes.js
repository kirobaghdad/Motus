const express = require('express');
const router = express.Router();
const tripController = require('../controllers/tripController');

// send trip request to car
router.post('/request', tripController.requestTrip);

module.exports = router;