#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <err.h>

#define BANNER "Welcome to CS487 hw1 Level1"

#ifndef BUF_SIZE
#define BUF_SIZE 32
#endif

int main(int argc, char **argv)
{
  struct {
    char buffer[BUF_SIZE];
    volatile int changeme;
  } locals;

  printf("%s\n", BANNER);
  if(argc == 1) {
      errx(1, "Please specify an argument.");
  }

  locals.changeme = 0;
  strcpy(locals.buffer, argv[1]);

  if(locals.changeme == 0x61626364) {
      printf("Congratulations, you've finished level 1:-) Well done!\n");
  } else {
      printf("Try again, you got 0x%08x\n", locals.changeme);
  }
}
