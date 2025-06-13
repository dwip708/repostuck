#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

int is_prime(long long n) {
    if (n < 2) return 0;
    for (long long i = 2; i * i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}

int main() {
    const long long start = 90000000000LL;
    const long long end   = 90000100000LL;
    int count = 0;

    clock_t begin = clock();

    for (long long i = start; i <= end; i++) {
        if (is_prime(i)) {
            count++;
        }
    }

    clock_t finish = clock();
    double elapsed = (double)(finish - begin) / CLOCKS_PER_SEC;

    printf("Found %d primes in %.3f seconds\n", count, elapsed);
    return 0;
}