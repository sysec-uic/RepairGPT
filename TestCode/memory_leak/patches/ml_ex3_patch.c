#include <stdlib.h>

void func() {
    char *str = (char *)malloc(5);
    free(str);
}

int main() {
    func();
    return 0;
}