#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_FILE="${PID_FILE:-/tmp/marker_imu_robot.pid}"
LOG_FILE="${LOG_FILE:-/tmp/marker_imu_robot.log}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

CONFIG="${CONFIG:-config.json}"
ROUTE="${ROUTE:-route.json}"
HEADLESS="${HEADLESS:-1}"
GPIO="${GPIO:-0}"
AUTO_START="${AUTO_START:-$HEADLESS}"

build_command() {
    local command=("$PYTHON_BIN" "navigation.py" "--config" "$CONFIG" "--route" "$ROUTE")

    if [[ "$GPIO" == "1" ]]; then
        command+=("--gpio")
    fi

    if [[ "$HEADLESS" == "1" ]]; then
        command+=("--headless")
    fi

    if [[ "$AUTO_START" == "1" ]]; then
        command+=("--autostart")
    fi

    printf '%q ' "${command[@]}"
}

print_mode() {
    if [[ "$GPIO" == "1" ]]; then
        echo "GPIO: enabled (hardware motor output)"
    else
        echo "GPIO: disabled (dry run; car will not move)"
    fi

    if [[ "$AUTO_START" == "1" ]]; then
        echo "Autostart: enabled"
    else
        echo "Autostart: disabled"
    fi
}

is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(<"$PID_FILE")"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

start_robot() {
    if is_running; then
        echo "Already running with PID $(<"$PID_FILE")"
        return 0
    fi

    local command
    command="$(build_command)"
    echo "Starting: $command"
    print_mode
    nohup bash -c "$command" >>"$LOG_FILE" 2>&1 &
    echo "$!" >"$PID_FILE"
    sleep 0.3

    if is_running; then
        echo "Started with PID $(<"$PID_FILE")"
        echo "Log: $LOG_FILE"
    else
        echo "Failed to start. Last log lines:"
        tail -n 40 "$LOG_FILE" 2>/dev/null || true
        return 1
    fi
}

stop_robot() {
    if ! is_running; then
        echo "Not running"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid
    pid="$(<"$PID_FILE")"
    echo "Stopping PID $pid"
    kill "$pid"

    for _ in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo "Stopped"
            return 0
        fi
        sleep 0.2
    done

    echo "Process did not stop after SIGTERM; sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Stopped"
}

status_robot() {
    if is_running; then
        echo "Running with PID $(<"$PID_FILE")"
    else
        echo "Not running"
    fi
    print_mode
    echo "Log: $LOG_FILE"
}

case "${1:-status}" in
    start|s)
        start_robot
        ;;
    stop|x)
        stop_robot
        ;;
    restart|r)
        stop_robot
        start_robot
        ;;
    status|t)
        status_robot
        ;;
    logs)
        tail -n "${2:-80}" "$LOG_FILE"
        ;;
    follow)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {start|s|stop|x|restart|r|status|t|logs|follow}"
        echo "Options via environment: GPIO=1 AUTO_START=0 HEADLESS=0 CONFIG=... ROUTE=..."
        exit 2
        ;;
esac
