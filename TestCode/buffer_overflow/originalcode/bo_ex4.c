#include <err.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BANNER "Welcome to CS487 hw2 level1"

#ifndef BUF_SIZE
#define BUF_SIZE 64
#endif

int main(int argc, char **argv) {
  struct {
    char dest[BUF_SIZE];
    volatile int changeme;
  } locals;
  char buffer[16];

  printf("%s\n", BANNER);

  if (fgets(buffer, sizeof(buffer) - 1, stdin) == NULL) {
    errx(1, "Unable to get buffer");
  }
  buffer[15] = 0;

  locals.changeme = 0;

  // Format print string to buffer. More explanation: man sprintf
  sprintf(locals.dest, buffer);

  if (locals.changeme != 0) {
    puts("Congratulations, the 'changeme' variable has been changed!");
  } else {
    puts("'changeme' has not yet been changed. Would you like to try again?");
  }

  return 0;
}
