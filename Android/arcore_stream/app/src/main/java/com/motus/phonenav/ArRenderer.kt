package com.motus.phonenav

import android.app.Activity
import android.media.Image
import android.opengl.GLES20
import android.opengl.GLSurfaceView
import android.view.Surface
import com.google.ar.core.Coordinates2d
import com.google.ar.core.Frame
import com.google.ar.core.Session
import com.google.ar.core.TrackingState
import com.google.ar.core.exceptions.CameraNotAvailableException
import com.google.ar.core.exceptions.NotYetAvailableException
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicLong
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10

class ArRenderer(
    private val activity: Activity,
    private val statusCallback: (String) -> Unit
) : GLSurfaceView.Renderer {
    companion object {
        private const val MIN_DEPTH_MM = 200
        private const val MAX_DEPTH_MM = 5000
        private const val CLOUD_STRIDE = 4
    }

    private val backgroundRenderer = BackgroundRenderer()
    private val sequence = AtomicLong(0)
    @Volatile private var session: Session? = null
    @Volatile var networkStreamer: NetworkStreamer? = null
    @Volatile var streamingEnabled: Boolean = false
    @Volatile var targetHz: Double = 5.0
    private var width = 1
    private var height = 1
    private var textureAttachedSession: Session? = null
    private var nextCaptureTimestampNs = 0L
    private var lastStatusTimestampNs = 0L

    // Cache for point cloud generation to avoid allocations and redundant transforms
    private var cachedTextureCoords: FloatArray? = null
    private var cachedCpuCoords: FloatArray? = null
    private var cachedPoints: FloatArray? = null
    private var lastDepthWidth = -1
    private var lastDepthHeight = -1
    private var depthSampleBuffer: ShortArray? = null

    fun setSession(newSession: Session?) {
        session = newSession
        textureAttachedSession = null
    }

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES20.glClearColor(0f, 0f, 0f, 1f)
        backgroundRenderer.createOnGlThread()
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        this.width = width
        this.height = height
        GLES20.glViewport(0, 0, width, height)
        updateDisplayGeometry()
    }

    override fun onDrawFrame(gl: GL10?) {
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT or GLES20.GL_DEPTH_BUFFER_BIT)
        val activeSession = session ?: return
        try {
            if (textureAttachedSession !== activeSession && backgroundRenderer.textureId >= 0) {
                activeSession.setCameraTextureNames(intArrayOf(backgroundRenderer.textureId))
                textureAttachedSession = activeSession
                updateDisplayGeometry()
            }
            val frame = activeSession.update()
            backgroundRenderer.draw(frame)
            publishStatusOccasionally(frame)
            maybeCapture(frame)
        } catch (error: CameraNotAvailableException) {
            statusCallback("Camera unavailable: ${error.message}")
        } catch (error: Exception) {
            statusCallback("AR frame error: ${error.message ?: error.javaClass.simpleName}")
        }
    }

    private fun updateDisplayGeometry() {
        val rotation = if (android.os.Build.VERSION.SDK_INT >= 30) {
            activity.display?.rotation ?: Surface.ROTATION_0
        } else {
            @Suppress("DEPRECATION")
            activity.windowManager.defaultDisplay.rotation
        }
        session?.setDisplayGeometry(rotation, width, height)
    }

    private fun publishStatusOccasionally(frame: Frame) {
        val now = System.nanoTime()
        if (now - lastStatusTimestampNs < 500_000_000L) return
        lastStatusTimestampNs = now
        val camera = frame.camera
        val failure = camera.trackingFailureReason
        val suffix = if (camera.trackingState == TrackingState.TRACKING) "" else " ($failure)"
        statusCallback("ARCore: ${camera.trackingState}$suffix")
    }

    private fun maybeCapture(frame: Frame) {
        if (!streamingEnabled || networkStreamer?.isRunning() != true) return
        if (frame.camera.trackingState != TrackingState.TRACKING) return
        if (frame.timestamp == 0L) return
        val period = (1_000_000_000.0 / targetHz.coerceIn(1.0, 30.0)).toLong()
        if (nextCaptureTimestampNs == 0L || frame.timestamp - nextCaptureTimestampNs > period) {
            nextCaptureTimestampNs = frame.timestamp
        }
        if (frame.timestamp < nextCaptureTimestampNs) return

        var cameraImage: Image? = null
        var depthImage: Image? = null
        try {
            cameraImage = frame.acquireCameraImage()
            try {
                depthImage = frame.acquireDepthImage16Bits()
            } catch (_: NotYetAvailableException) {
                depthImage = null
            }

            val camera = frame.camera
            val pose = camera.pose
            val intrinsics = camera.imageIntrinsics
            val focal = intrinsics.focalLength
            val principal = intrinsics.principalPoint
            val luma = copyLuma(cameraImage)
            
            // Capture depth data for background processing
            val depthData = depthImage?.let { sampleDepth(it) }
            val cpuCoords = cachedCpuCoords // Use cached coordinates from last successful makePointCloud call
            
            val trackingCode = when (camera.trackingState) {
                TrackingState.TRACKING -> 2
                TrackingState.PAUSED -> 1
                else -> 0
            }

            val sample = FrameSample(
                sequence = sequence.incrementAndGet(),
                timestampNs = frame.timestamp,
                trackingCode = trackingCode,
                translation = pose.translation,
                rotationQuaternion = pose.rotationQuaternion,
                imageWidth = cameraImage.width,
                imageHeight = cameraImage.height,
                fx = focal[0],
                fy = focal[1],
                cx = principal[0],
                cy = principal[1],
                grayscale = luma,
                depthData = depthData,
                depthWidth = depthImage?.width ?: 0,
                depthHeight = depthImage?.height ?: 0,
                cpuCoords = cpuCoords
            )
            
            // We still need to call makePointCloud occasionally to refresh cachedCpuCoords if needed
            // But we can skip it on most frames if we have valid cache
            if (depthImage != null && (cachedCpuCoords == null || frame.hasDisplayGeometryChanged())) {
                makePointCloud(frame, depthImage, cameraImage.width, cameraImage.height, 
                               focal[0], focal[1], principal[0], principal[1])
            }

            networkStreamer?.offer(sample)
            nextCaptureTimestampNs += period
        } catch (_: NotYetAvailableException) {
            // ARCore has not delivered a CPU camera image for this frame yet.
        } catch (error: Exception) {
            statusCallback("Capture error: ${error.message ?: error.javaClass.simpleName}")
        } finally {
            depthImage?.close()
            cameraImage?.close()
        }
    }

    private fun copyLuma(image: Image): ByteArray {
        val plane = image.planes[0]
        val buffer = plane.buffer.duplicate()
        val output = ByteArray(image.width * image.height)
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        if (pixelStride == 1 && rowStride == image.width) {
            buffer.get(output)
            return output
        }
        var out = 0
        for (row in 0 until image.height) {
            if (pixelStride == 1) {
                // Bulk copy row, then flip it in-place to save time
                buffer.position(row * rowStride)
                buffer.get(output, out, image.width)
                val rowEnd = out + image.width - 1
                for (i in 0 until image.width / 2) {
                    val tmp = output[out + i]
                    output[out + i] = output[rowEnd - i]
                    output[rowEnd - i] = tmp
                }
                out += image.width
            } else {
                // Manual flip while copying
                for (col in image.width - 1 downTo 0) {
                    output[out++] = buffer.get(row * rowStride + col * pixelStride)
                }
            }
        }
        return output
    }

    private fun sampleDepth(depthImage: Image): ShortArray {
        val dWidth = depthImage.width
        val dHeight = depthImage.height
        val sampleColumns = (dWidth + CLOUD_STRIDE - 1) / CLOUD_STRIDE
        val sampleRows = (dHeight + CLOUD_STRIDE - 1) / CLOUD_STRIDE
        val sampleCount = sampleColumns * sampleRows
        
        if (depthSampleBuffer == null || depthSampleBuffer!!.size != sampleCount) {
            depthSampleBuffer = ShortArray(sampleCount)
        }
        val output = depthSampleBuffer!!
        
        val plane = depthImage.planes[0]
        val buffer = plane.buffer.duplicate().order(ByteOrder.nativeOrder())
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        
        var outIndex = 0
        for (v in 0 until dHeight step CLOUD_STRIDE) {
            val rowOffset = v * rowStride
            for (u in 0 until dWidth step CLOUD_STRIDE) {
                output[outIndex++] = buffer.getShort(rowOffset + u * pixelStride)
            }
        }
        return output.copyOf() // Return a copy for the background thread
    }

    private fun makePointCloud(
        frame: Frame,
        depthImage: Image,
        cpuWidth: Int,
        cpuHeight: Int,
        fx: Float,
        fy: Float,
        cx: Float,
        cy: Float
    ): FloatArray {
        if (fx <= 0f || fy <= 0f || depthImage.width <= 0 || depthImage.height <= 0) {
            return FloatArray(0)
        }

        val dWidth = depthImage.width
        val dHeight = depthImage.height
        val sampleColumns = (dWidth + CLOUD_STRIDE - 1) / CLOUD_STRIDE
        val sampleRows = (dHeight + CLOUD_STRIDE - 1) / CLOUD_STRIDE
        val sampleCount = sampleColumns * sampleRows

        // 1. Update coordinate grids only if resolution or display geometry changed
        if (cachedTextureCoords == null || dWidth != lastDepthWidth || dHeight != lastDepthHeight ||
            frame.hasDisplayGeometryChanged()) {

            val texCoords = FloatArray(sampleCount * 2)
            var coordinateIndex = 0
            for (v in 0 until dHeight step CLOUD_STRIDE) {
                val vCoord = (v + 0.5f) / dHeight.toFloat()
                for (u in 0 until dWidth step CLOUD_STRIDE) {
                    texCoords[coordinateIndex++] = (u + 0.5f) / dWidth.toFloat()
                    texCoords[coordinateIndex++] = vCoord
                }
            }
            cachedTextureCoords = texCoords

            val cpuCoords = FloatArray(sampleCount * 2)
            frame.transformCoordinates2d(
                Coordinates2d.TEXTURE_NORMALIZED,
                texCoords,
                Coordinates2d.IMAGE_PIXELS,
                cpuCoords
            )
            cachedCpuCoords = cpuCoords
            cachedPoints = FloatArray(sampleCount * 3)
            lastDepthWidth = dWidth
            lastDepthHeight = dHeight
        }

        val cpuCoords = cachedCpuCoords!!
        val points = cachedPoints!!
        val plane = depthImage.planes[0]
        val depthBuffer = plane.buffer.duplicate().order(ByteOrder.nativeOrder())
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        val invFx = 1.0f / fx
        val invFy = 1.0f / fy

        var pointIndex = 0
        var sampleIndex = 0
        for (v in 0 until dHeight step CLOUD_STRIDE) {
            val rowOffset = v * rowStride
            for (u in 0 until dWidth step CLOUD_STRIDE) {
                val byteIndex = rowOffset + u * pixelStride
                val millimeters = depthBuffer.getShort(byteIndex).toInt() and 0xffff
                if (millimeters in MIN_DEPTH_MM..MAX_DEPTH_MM) {
                    val pixelX = cpuCoords[sampleIndex * 2]
                    val pixelY = cpuCoords[sampleIndex * 2 + 1]
                    if (pixelX >= 0f && pixelX < cpuWidth && pixelY >= 0f && pixelY < cpuHeight) {
                        val z = millimeters * 0.001f
                        points[pointIndex++] = (cx - pixelX) * z * invFx
                        points[pointIndex++] = (pixelY - cy) * z * invFy
                        points[pointIndex++] = z
                    }
                }
                sampleIndex++
            }
        }
        return points.copyOf(pointIndex)
    }
}
