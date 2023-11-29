#include <err.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BANNER "Welcome to CS487 hw1 Level2"

#ifndef BUF_SIZE
#define BUF_SIZE 32
#endif

char *gets(char *);

void complete_level() {
  printf("Congratulations, you've finished level 2:-) Well done!\n");
  exit(0);
}

int main(int argc, char **argv) {
  struct {
    char buffer[BUF_SIZE];
    volatile int (*fp)();
  } locals;

  printf("%s\n", BANNER);

  locals.fp = NULL;
  gets(locals.buffer);

  if (locals.fp) {
    printf("calling function pointer @ %p\n", locals.fp);
    fflush(stdout);
    locals.fp();
  } else {
    printf("function pointer remains unmodified :~( better luck next time!\n");
  }

  return 0;
}
