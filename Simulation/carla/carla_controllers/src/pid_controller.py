from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, lower: float, upper: float) -> float:
    """limit a value to a closed numeric range."""
    return max(lower, min(value, upper))


@dataclass
class LongitudinalPID:
    """pid controller that returns one signed throttle/brake command."""

    kp: float
    ki: float
    kd: float
    integral_limit: float = 10.0
    derivative_smoothing: float = 0.5
    output_limit: float = 1.0

    def __post_init__(self) -> None:
        if min(self.kp, self.ki, self.kd, self.integral_limit) < 0:
            raise ValueError("PID gains and integral limit cannot be negative")
        if not 0.0 <= self.derivative_smoothing < 1.0:
            raise ValueError("derivative_smoothing must be in [0, 1)")
        if self.output_limit <= 0:
            raise ValueError("output_limit must be positive")
        self.reset()

    def reset(self) -> None:
        """clear stored integral and derivative state."""
        self.integral = 0.0
        self.previous_error: float | None = None
        self.filtered_derivative = 0.0

    def update(self, target_kmh: float, current_kmh: float, dt: float) -> float:
        """compute the next signed control command."""
        if dt <= 0:
            raise ValueError("dt must be positive")

        error = target_kmh - current_kmh
        if self.previous_error is None:
            raw_derivative = 0.0
        else:
            raw_derivative = (error - self.previous_error) / dt

        # smooth the derivative term so small speed jitter does not dominate.
        keep = self.derivative_smoothing
        self.filtered_derivative = (
            keep * self.filtered_derivative + (1.0 - keep) * raw_derivative
        )

        candidate_integral = clamp(
            self.integral + error * dt,
            -self.integral_limit,
            self.integral_limit,
        )
        candidate_output = self._raw_output(error, candidate_integral)

        saturated_high = candidate_output > self.output_limit
        saturated_low = candidate_output < -self.output_limit
        reduces_saturation = (saturated_high and error < 0) or (
            saturated_low and error > 0
        )
        # only integrate when it will not push a saturated output farther.
        if not saturated_high and not saturated_low or reduces_saturation:
            self.integral = candidate_integral

        output = self._raw_output(error, self.integral)
        self.previous_error = error
        return clamp(output, -self.output_limit, self.output_limit)

    def _raw_output(self, error: float, integral: float) -> float:
        """combine pid terms before output limiting."""
        return (
            self.kp * error
            + self.ki * integral
            + self.kd * self.filtered_derivative
        )


def command_to_actuation(
    command: float,
    max_throttle: float,
    max_brake: float,
) -> tuple[float, float]:
    """split a signed command into throttle and brake values."""
    command = clamp(command, -1.0, 1.0)
    # positive pid output accelerates; negative output brakes.
    if command >= 0:
        return command * max_throttle, 0.0
    return 0.0, -command * max_brake
