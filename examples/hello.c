// Simple LED blinker example for SK-02
// Demonstrates basic C features

char delay_count;

void delay(char loops) {
    while (loops > 0) {
        loops--;
    }
}

void main() {
    while (1) {
        // Turn LEDs on (assuming GPIO output)
        delay_count = 255;
        delay(100);

        // Turn LEDs off
        delay_count = 0;
        delay(100);
    }
}
