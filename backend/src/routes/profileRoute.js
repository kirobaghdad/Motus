const express = require('express');
const router = express.Router();
const profileController = require('../controllers/profileController');
const authenticateJWT = require('../middleware/authentication');

router.get('/profile',authenticateJWT,profileController.getProfile);
router.update('/edit/profile',authenticateJWT,profileController.editProfile);

module.exports = router;