package com.example.phonesensorsender

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.params.OutputConfiguration
import android.hardware.camera2.params.SessionConfiguration
import android.media.Image
import android.media.ImageReader
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.PowerManager
import android.util.Size
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import java.io.BufferedOutputStream
import java.io.DataOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.Executor
import kotlin.math.abs

class MainActivity : Activity(), SensorEventListener {

    companion object {
        private const val CAMERA_PERMISSION_REQUEST = 10
        private const val SENSOR_PERIOD_US = 20_000 // 50 Hz
    }

    private lateinit var ipInput: EditText
    private lateinit var portInput: EditText
    private lateinit var statusText: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button

    private lateinit var sensorManager: SensorManager
    private var rotationSensor: Sensor? = null
    private var gyroscope: Sensor? = null
    private var accelerometer: Sensor? = null

    private val sender = PacketSender()
    private var cameraThread: HandlerThread? = null
    private var cameraHandler: Handler? = null
    private var cameraDevice: CameraDevice? = null
    private var captureSession: CameraCaptureSession? = null
    private var imageReader: ImageReader? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var streaming = false

    private val lastSensorTimestamp = mutableMapOf<Int, Long>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildUi())

        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)
            ?: sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        startButton.setOnClickListener { begin() }
        stopButton.setOnClickListener { stopAll("Stopped") }
    }

    private fun buildUi(): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(32, 24, 32, 24)
        }

        ipInput = EditText(this).apply {
            hint = getString(R.string.jetson_ip_hint)
            setText(getString(R.string.default_jetson_ip))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
        portInput = EditText(this).apply {
            hint = getString(R.string.port_hint)
            setText(getString(R.string.default_port))
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
        startButton = Button(this).apply { text = getString(R.string.start_stream) }
        stopButton = Button(this).apply {
            text = getString(R.string.stop)
            isEnabled = false
        }
        statusText = TextView(this).apply {
            text = getString(R.string.initial_status)
            textSize = 16f
            setPadding(0, 20, 0, 0)
        }

        root.addView(ipInput)
        root.addView(portInput)
        root.addView(startButton)
        root.addView(stopButton)
        root.addView(statusText)
        return root
    }

    private fun begin() {
        if (streaming) return
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST)
            return
        }

        val host = ipInput.text.toString().trim()
        if (host.isBlank()) {
            statusText.text = getString(R.string.invalid_ip)
            return
        }

        val port = portInput.text.toString().toIntOrNull()
        if (port == null || port !in 1..65_535) {
            statusText.text = getString(R.string.invalid_port)
            return
        }

        statusText.text = getString(R.string.connecting_status, host, port)
        startButton.isEnabled = false
        stopButton.isEnabled = false

        sender.connect(
            host,
            port,
            onConnected = {
                runOnUiThread {
                    streaming = true
                    statusText.text = getString(R.string.streaming_status)
                    stopButton.isEnabled = true
                    acquireWakeLock()
                    startSensors()
                    startCamera()
                }
            },
            onError = { message ->
                runOnUiThread { stopAll("Connection error: $message") }
            }
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION_REQUEST &&
            grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
        ) {
            begin()
        } else {
            statusText.text = getString(R.string.camera_permission_required)
        }
    }

    private fun startSensors() {
        val missingSensors = mutableListOf<String>()
        rotationSensor?.let {
            sensorManager.registerListener(this, it, SENSOR_PERIOD_US)
        } ?: missingSensors.add("orientation")
        gyroscope?.let {
            sensorManager.registerListener(this, it, SENSOR_PERIOD_US)
        } ?: missingSensors.add("gyroscope")
        accelerometer?.let {
            sensorManager.registerListener(this, it, SENSOR_PERIOD_US)
        } ?: missingSensors.add("accelerometer")

        if (missingSensors.isNotEmpty()) {
            statusText.text = getString(
                R.string.missing_sensors_status,
                missingSensors.joinToString()
            )
        }
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (!streaming) return

        // Limit every sensor type to about 50 Hz.
        val previous = lastSensorTimestamp[event.sensor.type] ?: 0L
        if (event.timestamp - previous < 18_000_000L) return
        lastSensorTimestamp[event.sensor.type] = event.timestamp

        when (event.sensor.type) {
            Sensor.TYPE_GAME_ROTATION_VECTOR, Sensor.TYPE_ROTATION_VECTOR -> {
                val q = FloatArray(4) // Android order: w, x, y, z
                SensorManager.getQuaternionFromVector(q, event.values)
                sender.sendFloats(PacketSender.TYPE_ORIENTATION, event.timestamp,
                    floatArrayOf(q[1], q[2], q[3], q[0])) // x, y, z, w
            }
            Sensor.TYPE_GYROSCOPE -> sender.sendFloats(
                PacketSender.TYPE_GYRO,
                event.timestamp,
                event.values.copyOf(3)
            )
            Sensor.TYPE_ACCELEROMETER -> sender.sendFloats(
                PacketSender.TYPE_ACCEL,
                event.timestamp,
                event.values.copyOf(3)
            )
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    @SuppressLint("MissingPermission")
    private fun startCamera() {
        try {
            cameraThread = HandlerThread("CameraThread").also { it.start() }
            cameraHandler = Handler(cameraThread!!.looper)

            val manager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraIds = manager.cameraIdList
            if (cameraIds.isEmpty()) {
                stopAll("No camera found on this device.")
                return
            }

            val cameraId = cameraIds.firstOrNull { id ->
                manager.getCameraCharacteristics(id)
                    .get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
            } ?: cameraIds.first()

            val characteristics = manager.getCameraCharacteristics(cameraId)
            val sizes = characteristics
                .get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
                ?.getOutputSizes(ImageFormat.YUV_420_888)
                ?.takeIf { it.isNotEmpty() }
                ?: arrayOf(Size(640, 480))
            val chosenSize = chooseClosestSize(sizes, 640, 480)

            imageReader = ImageReader.newInstance(
                chosenSize.width,
                chosenSize.height,
                ImageFormat.YUV_420_888,
                2
            ).apply {
                setOnImageAvailableListener({ reader ->
                    val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                    image.use {
                        val gray = copyYPlane(it)
                        sender.sendImage(it.timestamp, it.width, it.height, gray)
                    }
                }, cameraHandler)
            }

            manager.openCamera(cameraId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    cameraDevice = camera
                    createCameraSession(camera)
                }

                override fun onDisconnected(camera: CameraDevice) {
                    camera.close()
                    runOnUiThread { stopAll("Camera disconnected") }
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    camera.close()
                    runOnUiThread { stopAll("Camera error: $error") }
                }
            }, cameraHandler)
        } catch (e: Exception) {
            stopAll("Camera start error: ${e.message ?: e.javaClass.simpleName}")
        }
    }

    private fun createCameraSession(camera: CameraDevice) {
        val surface = imageReader?.surface ?: run {
            runOnUiThread { stopAll("Camera image reader is unavailable.") }
            return
        }
        try {
            val callback = object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    captureSession = session
                    try {
                        val request = camera.createCaptureRequest(CameraDevice.TEMPLATE_RECORD).apply {
                            addTarget(surface)
                            set(CaptureRequest.CONTROL_AF_MODE,
                                CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_VIDEO)
                            set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                        }.build()
                        session.setRepeatingRequest(request, null, cameraHandler)
                    } catch (e: Exception) {
                        runOnUiThread {
                            stopAll("Camera capture error: ${e.message ?: e.javaClass.simpleName}")
                        }
                    }
                }

                override fun onConfigureFailed(session: CameraCaptureSession) {
                    runOnUiThread { stopAll("Could not configure camera") }
                }
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val handler = cameraHandler
                val executor = Executor { command ->
                    if (handler != null) handler.post(command) else command.run()
                }
                val configuration = SessionConfiguration(
                    SessionConfiguration.SESSION_REGULAR,
                    listOf(OutputConfiguration(surface)),
                    executor,
                    callback
                )
                camera.createCaptureSession(configuration)
            } else {
                @Suppress("DEPRECATION")
                camera.createCaptureSession(listOf(surface), callback, cameraHandler)
            }
        } catch (e: Exception) {
            runOnUiThread {
                stopAll("Camera session error: ${e.message ?: e.javaClass.simpleName}")
            }
        }
    }

    private fun chooseClosestSize(sizes: Array<Size>, targetW: Int, targetH: Int): Size {
        return sizes.minByOrNull {
            abs(it.width - targetW) + abs(it.height - targetH)
        } ?: sizes.first()
    }

    private fun copyYPlane(image: Image): ByteArray {
        val width = image.width
        val height = image.height
        val plane = image.planes[0]
        val buffer = plane.buffer
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        val output = ByteArray(width * height)

        var outIndex = 0
        for (row in 0 until height) {
            val rowStart = row * rowStride
            for (col in 0 until width) {
                output[outIndex++] = buffer.get(rowStart + col * pixelStride)
            }
        }
        return output
    }

    private fun acquireWakeLock() {
        val power = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PhoneSensorSender:Stream")
        wakeLock?.acquire(60 * 60 * 1000L)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun stopAll(message: String) {
        streaming = false
        sensorManager.unregisterListener(this)
        lastSensorTimestamp.clear()

        captureSession?.close()
        captureSession = null
        cameraDevice?.close()
        cameraDevice = null
        imageReader?.close()
        imageReader = null
        cameraThread?.quitSafely()
        cameraThread = null
        cameraHandler = null

        sender.close()
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        startButton.isEnabled = true
        stopButton.isEnabled = false
        statusText.text = message
    }

    override fun onDestroy() {
        stopAll("Stopped")
        super.onDestroy()
    }
}

private class PacketSender {
    companion object {
        const val MAGIC = 0x52425431 // ASCII: RBT1
        const val TYPE_IMAGE: Byte = 1
        const val TYPE_ORIENTATION: Byte = 2
        const val TYPE_GYRO: Byte = 3
        const val TYPE_ACCEL: Byte = 4
    }

    private val queue = ArrayBlockingQueue<ByteArray>(16)
    @Volatile private var running = false
    private var socket: Socket? = null
    private var writerThread: Thread? = null

    fun connect(host: String, port: Int, onConnected: () -> Unit, onError: (String) -> Unit) {
        close()
        Thread {
            try {
                val newSocket = Socket()
                newSocket.connect(InetSocketAddress(host, port), 5000)
                newSocket.tcpNoDelay = true
                socket = newSocket
                running = true

                val output = DataOutputStream(BufferedOutputStream(newSocket.getOutputStream(), 1 shl 20))
                writerThread = Thread {
                    try {
                        while (running) {
                            output.write(queue.take())
                            output.flush()
                        }
                    } catch (_: InterruptedException) {
                        // Normal shutdown.
                    } catch (e: Exception) {
                        if (running) onError(e.message ?: "Socket writer failed")
                    }
                }.also { it.start() }
                onConnected()
            } catch (e: Exception) {
                onError(e.message ?: "Could not connect")
            }
        }.start()
    }

    fun sendImage(timestampNs: Long, width: Int, height: Int, gray: ByteArray) {
        if (!running || queue.size > 4) return // Drop old frames rather than add lag.
        val payload = ByteBuffer.allocate(8 + gray.size).order(ByteOrder.BIG_ENDIAN)
            .putInt(width)
            .putInt(height)
            .put(gray)
            .array()
        enqueue(buildPacket(TYPE_IMAGE, timestampNs, payload))
    }

    fun sendFloats(type: Byte, timestampNs: Long, values: FloatArray) {
        if (!running) return
        val payloadBuffer = ByteBuffer.allocate(values.size * 4).order(ByteOrder.BIG_ENDIAN)
        values.forEach { payloadBuffer.putFloat(it) }
        enqueue(buildPacket(type, timestampNs, payloadBuffer.array()))
    }

    private fun buildPacket(type: Byte, timestampNs: Long, payload: ByteArray): ByteArray {
        return ByteBuffer.allocate(4 + 1 + 8 + 4 + payload.size)
            .order(ByteOrder.BIG_ENDIAN)
            .putInt(MAGIC)
            .put(type)
            .putLong(timestampNs)
            .putInt(payload.size)
            .put(payload)
            .array()
    }

    private fun enqueue(packet: ByteArray) {
        if (!queue.offer(packet)) {
            queue.poll()
            queue.offer(packet)
        }
    }

    fun close() {
        running = false
        writerThread?.interrupt()
        writerThread = null
        queue.clear()
        try { socket?.close() } catch (_: Exception) {}
        socket = null
    }
}
