// Bubble sort of uint16 array
//
// Demonstrates: global arrays, variable indices, expression indices (arr[j+1]),
// uint16 swap via local tmp, nested while loops.

uint16 arr[8];
uint8 arr_len;

void bubble_sort() {
    uint8 i = 0;
    while (i < arr_len - 1) {
        uint8 j = 0;
        while (j < arr_len - 1 - i) {
            if (arr[j] > arr[j + 1]) {
                uint16 tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
            j++;
        }
        i++;
    }
}

void main() {
    arr[0] = 300;
    arr[1] = 42;
    arr[2] = 1000;
    arr[3] = 7;
    arr[4] = 500;
    arr[5] = 128;
    arr[6] = 999;
    arr[7] = 1;
    arr_len = 8;

    bubble_sort();

    // After sorting arr[] = {1, 7, 42, 128, 300, 500, 999, 1000}
}
