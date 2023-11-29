#include <stdlib.h>

void func() {
    for (int i = 0; i < 5; i++) {
        int* ptr = (int*)malloc(sizeof(int));
    }
}

int main() {
    func();
    return 0;
}
