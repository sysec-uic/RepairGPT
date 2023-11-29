#include <err.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BANNER "Welcome to CS487 hw1 Level3"

#ifndef BUF_SIZE
#define BUF_SIZE 64
#endif

char *gets(char *);

void complete_level() {
  printf("Congratulations, you've finished level 3:-) Well done!\n");
  exit(0);
}

void start_level() {
  char buffer[BUF_SIZE];
  void *ret;

  gets(buffer);

  ret = __builtin_return_address(0);
  printf("and will be returning to %p\n", ret);
}

int main(int argc, char **argv) {
  printf("%s\n", BANNER);
  start_level();
}
