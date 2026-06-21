import { defineConfig } from 'vitest';

export default defineConfig({
    test: {
        environment: 'node',
        // This ensures tests run sequentially if they share a local test database or port
        threads: false,
    },
});