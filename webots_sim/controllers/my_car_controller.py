from vehicle import Driver
import csv
import os
import math

# Car controller that follows a yellow line and avoids obstacles using lidar data. and logs sensor data to a CSV file


driver = Driver()
timestep = int(driver.getBasicTimeStep())

camera = driver.getDevice("camera")
camera.enable(timestep)

lidar = driver.getDevice("Sick LMS 291")
lidar.enable(timestep)

gps = driver.getDevice("gps")
gps.enable(timestep)

gyro = driver.getDevice("gyro")
gyro.enable(timestep)

accelerometer = driver.getDevice("accelerometer")
accelerometer.enable(timestep)

display = driver.getDevice("display")
display_w = display.getWidth()
display_h = display.getHeight()

cam_w = camera.getWidth()
cam_h = camera.getHeight()

# --- CSV ---
csv_path = os.path.join(os.path.dirname(__file__), "sensor_readings.csv")
csv_file = open(csv_path, "w", newline="")
writer = csv.writer(csv_file)
writer.writerow([
    "Time (s)",
    "GPS X", "GPS Y", "GPS Z", "GPS Speed (km/h)",
    "Gyro X", "Gyro Y", "Gyro Z",
    "Accel X", "Accel Y", "Accel Z",
    "Lidar Min Dist (m)"
])

TARGET_SPEED = 50.0  # km/h
time_elapsed = 0.0

def find_yellow_line(image_bytes):
    """
    Returns a normalized line position in [-1, +1]
    -1 => line is left, +1 => line is right, 0 => centered
    """
    if image_bytes is None:
        return 0.0

    # Yellow road line reference (BGR). If it doesn’t detect well, loosen the threshold.
    ref_b, ref_g, ref_r = 95, 187, 203

    sum_x = 0
    count = 0

    # Scan only bottom half (road area)
    for y in range(cam_h // 2, cam_h):
        row_base = y * cam_w * 4
        for x in range(cam_w):
            idx = row_base + x * 4  # BGRA
            b = image_bytes[idx]
            g = image_bytes[idx + 1]
            r = image_bytes[idx + 2]

            diff = abs(int(b) - ref_b) + abs(int(g) - ref_g) + abs(int(r) - ref_r)
            if diff < 30:
                sum_x += x
                count += 1

    if count == 0:
        return 0.0

    return (sum_x / count / cam_w - 0.5) * 2.0

driver.setCruisingSpeed(TARGET_SPEED)

while driver.step() != -1:
    # --- Reading sensors ---
    gps_coords = gps.getValues()              # meters
    gps_speed = gps.getSpeed() * 3.6          # m/s -> km/h
    gyro_vals = gyro.getValues()              # rad/s
    accel_vals = accelerometer.getValues()    # m/s^2 (includes gravity)

    # Lidar range image: distances in meters (one per ray)
    lidar_range = lidar.getRangeImage()
    valid_ranges = [d for d in lidar_range if (d is not None and d > 0.0 and math.isfinite(d))]
    min_lidar = min(valid_ranges) if valid_ranges else float("inf")

    # --- Steering (camera line following) ---
    image = camera.getImage()
    line_pos = find_yellow_line(image)
    steering = max(-0.5, min(0.5, line_pos * 0.4))
    driver.setSteeringAngle(steering)

    # --- Simple obstacle-based speed control ---
    if 0.0 < min_lidar < 15.0:
        driver.setCruisingSpeed(TARGET_SPEED * (min_lidar / 15.0))
    else:
        driver.setCruisingSpeed(TARGET_SPEED)

    # --- Display ---
    display.setColor(0x000000)
    display.fillRectangle(0, 0, display_w, display_h)
    display.setColor(0xFFFFFF)

    display.drawText(f"Speed: {gps_speed:.1f} km/h", 5, 15)
    display.drawText(f"GPS XY: ({gps_coords[0]:.1f}, {gps_coords[1]:.1f})", 5, 35)
    display.drawText(f"Height: {gps_coords[2]:.2f} m", 5, 55)
    display.drawText(f"Accel: ({accel_vals[0]:.2f}, {accel_vals[1]:.2f}, {accel_vals[2]:.2f})", 5, 75)
    display.drawText(f"Gyro:  ({gyro_vals[0]:.3f}, {gyro_vals[1]:.3f}, {gyro_vals[2]:.3f})", 5, 95)

    lidar_text = f"{min_lidar:.2f} m" if math.isfinite(min_lidar) else "inf"
    display.drawText(f"Lidar min(closest obstacle): {lidar_text}", 5, 115)

    # --- Console + CSV ---
    writer.writerow([
        round(time_elapsed, 2),
        round(gps_coords[0], 3), round(gps_coords[1], 3), round(gps_coords[2], 3), round(gps_speed, 2),
        round(gyro_vals[0], 4), round(gyro_vals[1], 4), round(gyro_vals[2], 4),
        round(accel_vals[0], 4), round(accel_vals[1], 4), round(accel_vals[2], 4),
        round(min_lidar, 3) if math.isfinite(min_lidar) else ""
    ])
    csv_file.flush()

    time_elapsed += timestep / 1000.0
