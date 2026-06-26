# Jetson server

## Install

```bash
cd jetson
chmod +x scripts/*.sh
./scripts/install_jetson.sh
```

Log out and back in once, then run:

```bash
./scripts/run_jetson.sh
```

Open from any device on the same router:

```text
http://JETSON_IP:8000
```

Find the Jetson IP with:

```bash
hostname -I
```

## Main configuration

- `motus_nav/config/car.json`: pins, servo calibration and controller values.
- `motus_nav/config/map.json`: map image dimensions, resolution and origin.
- `motus_nav/config/graph.json`: waypoints, destinations and links.

The server falls back to simulation mode when GPIO initialization fails, but you should still set `hardware.enabled` to `false` explicitly while testing on Windows.
