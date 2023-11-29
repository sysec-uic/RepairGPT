#include <stdlib.h>

void f() {
    int* ptr = malloc(sizeof(int));
    free(ptr);
    return;
}

int main() {
    f();
    return 0;
}