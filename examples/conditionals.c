// Conditional statements example

int value;
char flag;

char max(char a, char b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}

char min(char a, char b) {
    if (a < b) {
        return a;
    }
    return b;
}

void main() {
    char x;
    char y;

    x = 42;
    y = 17;

    value = max(x, y);
    value = min(x, y);

    // Nested if
    if (x > 40) {
        if (y < 20) {
            flag = 1;
        } else {
            flag = 0;
        }
    }

    // Equality tests
    if (x == y) {
        flag = 1;
    }

    if (x != y) {
        flag = 0;
    }
}
