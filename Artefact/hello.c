// Dashboard OTA Build Trigger: 2026-08-26T21:11:34.232236
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
// Trigger update check
void add(int argc, char *argv[]) {
    int test_count = 1;
    int count = 0;
    for (int i = 0; i < argc; i++) {
        int num = atoi(argv[i]);
        count += num;
        test_count += num;
    }

    printf("add:%d", count);
}

void minus(int argc, char *argv[]) {
    int result = atoi(argv[0]);

    for (int i = 1; i < argc; i++) {
        result -= atoi(argv[i]);
    }

    printf("minus:%d", result);


}
void multiply(int argc, char *argv[]) {
    int count = 1;
    for (int i = 0; i < argc; i++) {
        int num = atoi(argv[i]);
        count *= num;
    }
    printf("multiply:%d", count);
}

void crash(int argc, char *argv[]) {
    (void)argc;
    (void)argv;
    // Real CPU floating point exception
    // This is a test
    volatile int a = 1;
    volatile int b = 0;
    volatile int c = a / b;
    (void)c;
}

struct entry {
    const char *name;
    void (*fn)(int argc, char *argv[]);
};

struct entry table[] = {
    {"add", add},
    {"minus", minus},
    {"multiply",multiply},
    {"crash", crash},
};

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s <function> [args...]\n", argv[0]);
        return 1;
    }

    for (size_t i = 0; i < sizeof(table) / sizeof(table[0]); i++) {
        if (strcmp(argv[1], table[i].name) == 0) {
            /* pass remaining arguments to the function */
            table[i].fn(argc - 2, argv + 2);
            return 0;
        }
    }

    printf("Unknown function: %s\n", argv[1]);
    return 1;
}
