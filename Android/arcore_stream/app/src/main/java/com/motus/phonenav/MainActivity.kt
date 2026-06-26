package com.motus.phonenav

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.opengl.GLSurfaceView
import android.os.BatteryManager
import android.os.Bundle
import android.os.PowerManager
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.ar.core.ArCoreApk
import com.google.ar.core.CameraConfig
import com.google.ar.core.CameraConfigFilter
import com.google.ar.core.Config
import com.google.ar.core.Session
import com.google.ar.core.exceptions.CameraNotAvailableException
import java.util.EnumSet

class MainActivity : AppCompatActivity() {
    companion object {
        private const val CAMERA_PERMISSION_CODE = 1001
    }

    private lateinit var surfaceView: GLSurfaceView
    private lateinit var renderer: ArRenderer
    private lateinit var networkStreamer: NetworkStreamer
    private lateinit var hostField: EditText
    private lateinit var portField: EditText
    private lateinit var rateField: EditText
    private lateinit var streamButton: Button
    private lateinit var flashButton: Button
    private lateinit var arStatus: TextView
    private lateinit var networkStatus: TextView
    private lateinit var temperatureStatus: TextView
    private var session: Session? = null
    private var installRequested = false
    private var wakeLock: PowerManager.WakeLock? = null

    private val thermalReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_BATTERY_CHANGED) {
                val temp = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)
                val celsius = temp / 10f
                temperatureStatus.text = "Temp: %.1f°C".format(celsius)
                if (celsius > 45.0) {
                    showError("Device too hot ($celsius°C). Closing app for safety.")
                    finishAffinity()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        networkStreamer = NetworkStreamer { text -> runOnUiThread { networkStatus.text = text } }
        renderer = ArRenderer(this) { text -> runOnUiThread { arStatus.text = text } }
        renderer.networkStreamer = networkStreamer
        setContentView(buildUi())
    }

    override fun onResume() {
        super.onResume()
        registerReceiver(thermalReceiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        if (!hasCameraPermission()) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.CAMERA),
                CAMERA_PERMISSION_CODE
            )
            return
        }
        if (!ensureSession()) return
        try {
            session?.resume()
            surfaceView.onResume()
            renderer.setSession(session)
            acquireWakeLock()
        } catch (error: CameraNotAvailableException) {
            showError("Camera is not available. Close other camera apps and reopen this app.")
            session = null
        }
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(thermalReceiver)
        renderer.streamingEnabled = false
        networkStreamer.stop()
        streamButton.text = "Start streaming"
        surfaceView.onPause()
        session?.pause()
        releaseWakeLock()
    }

    override fun onDestroy() {
        networkStreamer.stop()
        val oldSession = session
        session = null
        renderer.setSession(null)
        Thread { oldSession?.close() }.start()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION_CODE && grantResults.firstOrNull() != PackageManager.PERMISSION_GRANTED) {
            showError("Camera permission is required.")
        }
    }

    private fun ensureSession(): Boolean {
        if (session != null) return true
        try {
            when (ArCoreApk.getInstance().requestInstall(this, !installRequested)) {
                ArCoreApk.InstallStatus.INSTALL_REQUESTED -> {
                    installRequested = true
                    return false
                }
                ArCoreApk.InstallStatus.INSTALLED -> Unit
            }
            val newSession = Session(this)
            chooseCameraConfig(newSession)
            val config = Config(newSession).apply {
                updateMode = Config.UpdateMode.LATEST_CAMERA_IMAGE
                focusMode = Config.FocusMode.AUTO
                planeFindingMode = Config.PlaneFindingMode.DISABLED
                lightEstimationMode = Config.LightEstimationMode.DISABLED
                depthMode = if (newSession.isDepthModeSupported(Config.DepthMode.AUTOMATIC)) {
                    Config.DepthMode.AUTOMATIC
                } else {
                    Config.DepthMode.DISABLED
                }
            }
            newSession.configure(config)
            session = newSession
            arStatus.text = "ARCore configured; depth mode: ${config.depthMode}"
            return true
        } catch (error: Exception) {
            showError("Cannot start ARCore: ${error.message ?: error.javaClass.simpleName}")
            return false
        }
    }

    private fun chooseCameraConfig(arSession: Session) {
        val depthFilter = CameraConfigFilter(arSession).apply {
            targetFps = EnumSet.of(CameraConfig.TargetFps.TARGET_FPS_30)
            depthSensorUsage = EnumSet.of(CameraConfig.DepthSensorUsage.REQUIRE_AND_USE)
        }
        var configs = arSession.getSupportedCameraConfigs(depthFilter)
        if (configs.isEmpty()) {
            val fallback = CameraConfigFilter(arSession).apply {
                targetFps = EnumSet.of(CameraConfig.TargetFps.TARGET_FPS_30)
            }
            configs = arSession.getSupportedCameraConfigs(fallback)
        }
        if (configs.isNotEmpty()) {
            arSession.cameraConfig = configs.minByOrNull {
                it.imageSize.width.toLong() * it.imageSize.height.toLong()
            } ?: configs[0]
        }
    }

    private fun buildUi(): FrameLayout {
        val root = FrameLayout(this)
        surfaceView = GLSurfaceView(this).apply {
            preserveEGLContextOnPause = true
            setEGLContextClientVersion(2)
            setRenderer(renderer)
            renderMode = GLSurfaceView.RENDERMODE_CONTINUOUSLY
        }
        root.addView(surfaceView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ))

        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.START
            setPadding(dp(12), dp(10), dp(12), dp(10))
            setBackgroundColor(Color.argb(190, 0, 0, 0))
        }
        val panelParams = FrameLayout.LayoutParams(dp(360), ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            gravity = Gravity.TOP or Gravity.START
            setMargins(dp(10), dp(10), 0, 0)
        }

        panel.addView(label("Jetson IP or 127.0.0.1 with adb reverse"))
        hostField = editText("127.0.0.1", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        panel.addView(hostField)
        panel.addView(label("TCP port"))
        portField = editText("5000", InputType.TYPE_CLASS_NUMBER)
        panel.addView(portField)
        panel.addView(label("Stream rate (1-30 Hz)"))
        rateField = editText("5", InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL)
        panel.addView(rateField)

        streamButton = Button(this).apply {
            text = "Start streaming"
            setOnClickListener { toggleStreaming() }
        }
        panel.addView(streamButton)

        flashButton = Button(this).apply {
            text = "Flash: OFF"
            setOnClickListener { toggleFlash() }
        }
        panel.addView(flashButton)

        arStatus = label("ARCore: starting")
        networkStatus = label("Network stopped")
        temperatureStatus = label("Temp: --°C")
        panel.addView(arStatus)
        panel.addView(networkStatus)
        panel.addView(temperatureStatus)
        panel.addView(label("Keep the rear camera unobstructed. Move gently for the first few seconds so depth and tracking initialize."))
        root.addView(panel, panelParams)
        return root
    }

    private fun toggleStreaming() {
        if (networkStreamer.isRunning()) {
            renderer.streamingEnabled = false
            networkStreamer.stop()
            streamButton.text = "Start streaming"
            return
        }
        val host = hostField.text.toString().trim()
        val port = portField.text.toString().toIntOrNull()
        val rate = rateField.text.toString().toDoubleOrNull()
        if (host.isBlank() || port == null || port !in 1..65535 || rate == null) {
            showError("Enter a valid Jetson IP, port, and stream rate.")
            return
        }
        renderer.targetHz = rate.coerceIn(1.0, 30.0)
        renderer.streamingEnabled = true
        networkStreamer.start(host, port)
        streamButton.text = "Stop streaming"
    }

    private fun toggleFlash() {
        val activeSession = session ?: return
        try {
            val config = activeSession.config
            val isCurrentlyOn = config.flashMode == Config.FlashMode.TORCH
            config.flashMode = if (isCurrentlyOn) Config.FlashMode.OFF else Config.FlashMode.TORCH
            activeSession.configure(config)
            flashButton.text = if (isCurrentlyOn) "Flash: OFF" else "Flash: ON"
        } catch (e: Exception) {
            showError("Failed to toggle flash: ${e.message}")
        }
    }

    private fun label(textValue: String) = TextView(this).apply {
        text = textValue
        setTextColor(Color.WHITE)
        textSize = 14f
        setPadding(0, dp(3), 0, dp(3))
    }

    private fun editText(initial: String, type: Int) = EditText(this).apply {
        setText(initial)
        inputType = type
        setTextColor(Color.WHITE)
        setHintTextColor(Color.LTGRAY)
        setSingleLine(true)
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun showError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        arStatus.text = message
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val manager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PhoneNav:stream").apply {
            acquire(10 * 60 * 60 * 1000L)
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
