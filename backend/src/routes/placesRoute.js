const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');

router.get('/popular-destination',authController);
router.get('/places',authController);
router.get('/map',authController);

module.exports = router;