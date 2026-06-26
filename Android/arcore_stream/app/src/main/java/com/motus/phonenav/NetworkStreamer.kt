package com.motus.phonenav

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.LinkedBlockingDeque
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.Deflater
import kotlin.math.max

class NetworkStreamer(
    private val statusCallback: (String) -> Unit
) {
    companion object {
        private const val PROTOCOL_VERSION: Short = 1
        private const val FIXED_BODY_BYTES = 88
    }

    private val running = AtomicBoolean(false)
    private val queue = LinkedBlockingDeque<FrameSample>(1)
    private var worker: Thread? = null
    @Volatile private var activeSocket: Socket? = null
    private var lastStreamingStatusNs = 0L
    private var frameCount = 0
    private var lastFpsTimestampNs = 0L
    private var currentFps = 0.0
    private val deflater = Deflater(Deflater.BEST_SPEED)
    private val baos = ByteArrayOutputStream(1024 * 64)
    private val deflateBuffer = ByteArray(16 * 1024)
    private var pointBuffer = FloatArray(3600 * 3)

    fun isRunning(): Boolean = running.get()

    fun start(host: String, port: Int) {
        stop()
        val now = System.nanoTime()
        lastFpsTimestampNs = now
        lastStreamingStatusNs = now
        frameCount = 0
        currentFps = 0.0
        running.set(true)
        worker = Thread({ runLoop(host, port) }, "PhoneArNetworkStreamer").also { it.start() }
    }

    fun stop() {
        running.set(false)
        activeSocket?.runCatching { close() }
        activeSocket = null
        worker?.interrupt()
        worker = null
        queue.clear()
        deflater.reset()
        frameCount = 0
        currentFps = 0.0
        statusCallback("Network stopped")
    }

    fun offer(sample: FrameSample) {
        if (!running.get()) return
        if (!queue.offerLast(sample)) {
            queue.pollFirst()
            queue.offerLast(sample)
        }
    }

    private fun runLoop(host: String, port: Int) {
        while (running.get()) {
            try {
                statusCallback("Connecting to $host:$port ...")
                Socket().use { socket ->
                    socket.tcpNoDelay = true
                    socket.keepAlive = true
                    socket.sendBufferSize = 512 * 1024
                    socket.connect(InetSocketAddress(host, port), 3000)
                    activeSocket = socket
                    statusCallback("Connected to $host:$port")
                    val output = DataOutputStream(java.io.BufferedOutputStream(socket.getOutputStream(), 64 * 1024))
                    while (running.get() && !socket.isClosed) {
                        val sample = queue.takeLast()
                        queue.clear()
                        writePacket(output, sample)
                    }
                }
            } catch (interrupted: InterruptedException) {
                Thread.currentThread().interrupt()
                break
            } catch (error: Exception) {
                if (running.get()) {
                    statusCallback("Network error: ${error.message ?: error.javaClass.simpleName}; retrying")
                    try {
                        Thread.sleep(1000)
                    } catch (_: InterruptedException) {
                        Thread.currentThread().interrupt()
                        break
                    }
                }
            } finally {
                activeSocket = null
            }
        }
    }

    private fun writePacket(output: DataOutputStream, sample: FrameSample) {
        // Perform point cloud generation on the background thread
        val points = if (sample.depthData != null && sample.cpuCoords != null) {
            makePointCloudBackground(sample)
        } else {
            sample.pointsOptical
        }
        
        val compressedImage = deflate(sample.grayscale)
        val pointCount = points.size / 3
        val flags: Short = ((if (compressedImage.isNotEmpty()) 1 else 0) or
            (if (pointCount > 0) 2 else 0)).toShort()
        val bodySize = FIXED_BODY_BYTES + compressedImage.size + points.size * 4

        val header = ByteBuffer.allocate(8 + FIXED_BODY_BYTES).order(ByteOrder.LITTLE_ENDIAN)
        header.put(byteArrayOf('A'.code.toByte(), 'R'.code.toByte(), 'P'.code.toByte(), 'K'.code.toByte()))
        header.putInt(bodySize)
        header.putShort(PROTOCOL_VERSION)
        header.putShort(flags)
        header.putLong(sample.sequence)
        header.putLong(sample.timestampNs)
        header.put(sample.trackingCode.toByte())
        header.put(0)
        header.put(0)
        header.put(0)
        header.putFloat(sample.translation[0])
        header.putFloat(sample.translation[1])
        header.putFloat(sample.translation[2])
        header.putFloat(sample.rotationQuaternion[0])
        header.putFloat(sample.rotationQuaternion[1])
        header.putFloat(sample.rotationQuaternion[2])
        header.putFloat(sample.rotationQuaternion[3])
        header.putInt(sample.imageWidth)
        header.putInt(sample.imageHeight)
        header.putFloat(sample.fx)
        header.putFloat(sample.fy)
        header.putFloat(sample.cx)
        header.putFloat(sample.cy)
        header.putInt(sample.grayscale.size)
        header.putInt(compressedImage.size)
        header.putInt(pointCount)

        output.write(header.array())
        output.write(compressedImage)
        if (points.isNotEmpty()) {
            val pointBytes = ByteBuffer.allocate(points.size * 4).order(ByteOrder.LITTLE_ENDIAN)
            for (value in points) pointBytes.putFloat(value)
            output.write(pointBytes.array())
        }
        output.flush()
        
        frameCount++
        val now = System.nanoTime()
        val elapsedFps = now - lastFpsTimestampNs
        if (elapsedFps >= 1_000_000_000L) {
            currentFps = frameCount * 1_000_000_000.0 / elapsedFps
            frameCount = 0
            lastFpsTimestampNs = now
        }

        if (now - lastStreamingStatusNs >= 500_000_000L) {
            lastStreamingStatusNs = now
            val fpsStr = "%.1f".format(currentFps)
            statusCallback("Streaming: $fpsStr FPS, cloud $pointCount pts")
        }
    }

    private fun deflate(input: ByteArray): ByteArray {
        if (input.isEmpty()) return ByteArray(0)
        deflater.reset()
        deflater.setInput(input)
        deflater.finish()
        baos.reset()
        while (!deflater.finished()) {
            val count = deflater.deflate(deflateBuffer)
            if (count <= 0) break
            baos.write(deflateBuffer, 0, count)
        }
        return baos.toByteArray()
    }

    private fun makePointCloudBackground(sample: FrameSample): FloatArray {
        val depthData = sample.depthData ?: return FloatArray(0)
        val cpuCoords = sample.cpuCoords ?: return FloatArray(0)
        
        val dWidth = sample.depthWidth
        val dHeight = sample.depthHeight
        val sampleColumns = (dWidth + 4 - 1) / 4 // CLOUD_STRIDE = 4
        val sampleRows = (dHeight + 4 - 1) / 4
        val sampleCount = sampleColumns * sampleRows
        
        if (pointBuffer.size < sampleCount * 3) {
            pointBuffer = FloatArray(sampleCount * 3)
        }
        
        val invFx = 1.0f / sample.fx
        val invFy = 1.0f / sample.fy
        val cx = sample.cx
        val cy = sample.cy
        val cpuWidth = sample.imageWidth
        val cpuHeight = sample.imageHeight
        
        var pointIndex = 0
        var sampleIndex = 0
        
        // Depth data is raw ShortArray from depthImage.planes[0].buffer
        // We assume it's sampled with CLOUD_STRIDE=4 in ArRenderer before passing
        for (i in 0 until sample.depthData.size) {
            val millimeters = depthData[i].toInt() and 0xffff
            if (millimeters in 200..5000) { // MIN_DEPTH_MM..MAX_DEPTH_MM
                val pixelX = cpuCoords[sampleIndex * 2]
                val pixelY = cpuCoords[sampleIndex * 2 + 1]
                if (pixelX >= 0f && pixelX < cpuWidth && pixelY >= 0f && pixelY < cpuHeight) {
                    val z = millimeters * 0.001f
                    pointBuffer[pointIndex++] = (pixelX - cx) * z * invFx
                    pointBuffer[pointIndex++] = (pixelY - cy) * z * invFy
                    pointBuffer[pointIndex++] = z
                }
            }
            sampleIndex++
        }
        return pointBuffer.copyOf(pointIndex)
    }
}
