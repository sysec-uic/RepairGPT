#include <stdlib.h>
 
void f()
{
    int* ptr = (int*)malloc(sizeof(int));
    return;
}

int main() {
    f();
    return 0;
}