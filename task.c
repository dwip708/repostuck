// task.c
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define N 500

int main() {
    int i, j, k;
    int **A = malloc(N * sizeof(int*));
    int **B = malloc(N * sizeof(int*));
    int **C = malloc(N * sizeof(int*));

    for (i = 0; i < N; ++i) {
        A[i] = malloc(N * sizeof(int));
        B[i] = malloc(N * sizeof(int));
        C[i] = malloc(N * sizeof(int));
        for (j = 0; j < N; ++j) {
            A[i][j] = rand() % 10;
            B[i][j] = rand() % 10;
            C[i][j] = 0;
        }
    }

    clock_t start = clock();
    for (i = 0; i < N; ++i)
        for (j = 0; j < N; ++j)
            for (k = 0; k < N; ++k)
                C[i][j] += A[i][k] * B[k][j];
    clock_t end = clock();

    double elapsed = (double)(end - start) / CLOCKS_PER_SEC;
    printf("Elapsed time: %.4f\n", elapsed);
    return 0;
}