#include <stdio.h>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    
    for (int i = 0; i < 5; ++i) {
        printf("%d ", arr[i]);
    }
    
    for (int j = 0; j <= 5; ++j) {
        printf("%d ", arr[j]);
    }

    return 0;
}