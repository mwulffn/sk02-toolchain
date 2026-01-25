// Control flow example

int counter;
char i;

void count_up() {
    for (i = 0; i < 10; i++) {
        counter++;
    }
}

void count_down() {
    char j;
    j = 10;

    while (j > 0) {
        counter--;
        j--;
    }
}

void main() {
    counter = 0;
    count_up();
    count_down();

    // Nested loop
    for (i = 0; i < 5; i++) {
        char k;
        for (k = 0; k < 3; k++) {
            counter++;
        }
    }
}
