const express = require('express');
const router = express.Router();
const tripController = require('../controllers/tripController');
const authenticateJWT = require('../middleware/authentication');

// send trip request to car
router.post('/request', authenticateJWT, tripController);

module.exports = router;