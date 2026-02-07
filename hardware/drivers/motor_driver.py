import Jetson.GPIO as GPIO
import time

class MotorDriver:
    def __init__(self, pwm_pin=33, dir_pin=29, frequency=1000):
        """
        Initialize the MotorDriver with PWM and Direction pins.
        
        Args:
            pwm_pin (int): The board pin number for PWM output (default: 33).
            dir_pin (int): The board pin number for Direction output (default: 29).
            frequency (int): The PWM frequency in Hz (default: 1000).
        """
        self.pwm_pin = pwm_pin
        self.dir_pin = dir_pin
        self.frequency = frequency

        # GPIO setup
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        
        # Setup Pins
        GPIO.setup(self.dir_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.pwm_pin, GPIO.OUT, initial=GPIO.LOW)
        
        # Setup PWM
        self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
        self.pwm.start(0)

    def set_speed(self, speed):
        """
        Set the motor speed and direction.
        
        Args:
            speed (float): Speed value between -100 and 100.
                           Positive values for forward, negative for backward.
        """
        # Clamp speed to -100 to 100
        speed = max(-100, min(100, speed))
        
        if speed > 0:
            GPIO.output(self.dir_pin, GPIO.HIGH)
            self.pwm.ChangeDutyCycle(abs(speed))
        elif speed < 0:
            GPIO.output(self.dir_pin, GPIO.LOW)
            self.pwm.ChangeDutyCycle(abs(speed))
        else:
            self.stop()

    def stop(self):
        """Stop the motor."""
        self.pwm.ChangeDutyCycle(0)
        GPIO.output(self.dir_pin, GPIO.LOW)

    def cleanup(self):
        """Cleanup GPIO resources."""
        self.stop()
        self.pwm.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    try:
        print("Initializing Motor Driver...")
        motor = MotorDriver(pwm_pin=33, dir_pin=29)
        
        print("Motor Forward 50%")
        motor.set_speed(50)
        time.sleep(2)
        
        print("Motor Stop")
        motor.stop()
        time.sleep(1)
        
        print("Motor Backward 50%")
        motor.set_speed(-50)
        time.sleep(2)
        
        print("Motor Stop")
        motor.stop()
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Cleaning up GPIO resources...")
        try:
            motor.cleanup()
        except NameError:
            pass # Motor not initialized
