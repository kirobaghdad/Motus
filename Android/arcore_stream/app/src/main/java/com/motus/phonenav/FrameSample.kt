package com.motus.phonenav

data class FrameSample(
    val sequence: Long,
    val timestampNs: Long,
    val trackingCode: Int,
    val translation: FloatArray,
    val rotationQuaternion: FloatArray,
    val imageWidth: Int,
    val imageHeight: Int,
    val fx: Float,
    val fy: Float,
    val cx: Float,
    val cy: Float,
    val grayscale: ByteArray,
    // Raw data for background processing
    val depthData: ShortArray? = null,
    val depthWidth: Int = 0,
    val depthHeight: Int = 0,
    // For coordinate transformation mapping (cached in ArRenderer)
    val cpuCoords: FloatArray? = null,
    // Output points (if pre-calculated, which we will avoid on GL thread now)
    var pointsOptical: FloatArray = FloatArray(0)
)
