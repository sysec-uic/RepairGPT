#include <stdlib.h>

void func() {
    int* ptr; // move the declaration outside the loop
    for (int i = 0; i < 5; i++) {
        ptr = (int*)malloc(sizeof(int)); // assign to the same pointer variable
    }
    free(ptr); // free the allocated memory outside the loop
}

int main() {
    func();
    return 0;
}