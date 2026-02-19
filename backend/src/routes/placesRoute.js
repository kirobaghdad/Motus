const express = require('express');
const router = express.Router();
const placesController = require('../controllers/placesController');

router.get('/popular-destination',placesController.getPopularPlaces);
router.get('/places',placesController.getPlaces);
router.get('/map',placesController.getMap);


module.exports = router;