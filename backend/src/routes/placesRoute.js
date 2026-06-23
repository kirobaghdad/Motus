const express = require('express');
const router = express.Router();
const placesController = require('../controllers/placesController');
const authenticateJWT = require('../middleware/authentication');

router.get('/popular-destination', authenticateJWT, placesController.getPopularPlaces);
router.get('/places', authenticateJWT, placesController.getPlaces);
router.get('/map', authenticateJWT, placesController.getMap);


module.exports = router;