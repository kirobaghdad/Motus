const express = require('express');
const router = express.Router();
const loginController = require('../controllers/loginController');
const authenticateJWT = require('../middleware/authentication');

router.post('/login',authenticateJWT,loginController.loginHandler);
router.get('/logout',authenticateJWT,loginController.logoutHandler);

module.exports = router;