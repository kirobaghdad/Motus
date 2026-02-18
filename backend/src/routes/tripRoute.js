const express = require('express');
const router = express.Router();
const tripController = require('../controllers/tripController');
const authenticateJWT = require('../middleware/authentication');

router.post('/book-trip', authenticateJWT, tripController);
router.delete('/delete-trip', authenticateJWT, tripController);
router.get('/trips', authenticateJWT, tripController);

module.exports = router;