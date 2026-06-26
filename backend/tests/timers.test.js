import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
// Import your actual backend logic function/class here
// import { startTripWhenTimeComes } from '../src/services/tripService'; 

describe('Time-Dependent Backend Logic', () => {

    beforeEach(() => {
        // Intercept native system time, setTimeout, and setInterval
        vi.useFakeTimers();
    });

    afterEach(() => {
        // Restore real system time so it doesn't break other files
        vi.useRealTimers();
    });

    test('should execute the trip starting sequence exactly when scheduled time arrives', () => {
        // Create a mock tracking function (Spy)
        const triggerBackendAction = vi.fn();

        const waitTime = 10 * 60 * 1000; // 10 minutes in milliseconds

        // Simulate scheduling a trip execution
        setTimeout(() => {
            triggerBackendAction();
        }, waitTime);

        // Assert: Right now, it shouldn't have run yet
        expect(triggerBackendAction).not.toHaveBeenCalled();

        // Fast forward exactly 10 minutes instantly without waiting in real life
        vi.advanceTimersByTime(waitTime);

        // Assert: Now the backend code should have executed successfully
        expect(triggerBackendAction).toHaveBeenCalledTimes(1);
    });
});