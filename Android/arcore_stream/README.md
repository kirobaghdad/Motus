# Phone Nav app

Open this folder in Android Studio on Windows.

The app sends ARCore pose, a grayscale camera image, camera calibration, and a sampled depth point cloud to the Jetson over TCP.

## Build from Windows

Double-click:

```text
build.bat
```

Then install with:

```text
install.bat
```

Use either:

- The Jetson USB-tethering IP, or
- `127.0.0.1` after running `adb reverse tcp:5000 tcp:5000` on Windows.

The default port is `5000`. Start at `5 Hz`.
