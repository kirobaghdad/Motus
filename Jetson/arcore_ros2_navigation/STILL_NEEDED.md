# Still needed before reliable autonomous navigation

The encoder is no longer used. These physical values still need measurement or calibration:

1. **Wheelbase** - distance between front and rear axle centers. Current placeholder: `0.25 m`.
2. **Maximum road-wheel steering angle** - not the servo angle. Current placeholder: `0.45 rad` (25.8 degrees).
3. **PWM-to-speed calibration** - current speed values are open-loop estimates because there is no encoder.
4. **Minimum PWM that starts movement** - current placeholder: `0%`.
5. **Robot footprint or radius** - Nav2 currently uses `0.18 m`.
6. **Phone mounting transform** - current placeholder: 15 cm forward and 22 cm upward from `base_link`.
7. **Physical emergency-stop switch** - software stop alone cannot protect against operating-system or electrical faults.
8. **Motor-driver electrical limits** - verify logic voltage, current rating, braking behavior, and safe power wiring.

Without wheel feedback, floor friction, battery voltage, payload, and slopes can change the real speed. Keep the maximum speed low and tune using repeated short tests.
