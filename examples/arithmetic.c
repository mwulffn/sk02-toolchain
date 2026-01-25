// Arithmetic operations example

int result;
char a;
char b;

int add(char x, char y) {
    return x + y;
}

int subtract(char x, char y) {
    return x - y;
}

void main() {
    a = 10;
    b = 5;

    result = add(a, b);
    result = subtract(a, b);

    // Bitwise operations
    result = a & b;
    result = a | b;
    result = a ^ b;
    result = ~a;

    // Shifts
    result = a << 2;
    result = a >> 1;
}
