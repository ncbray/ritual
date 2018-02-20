#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>

void fn_std_print_int(int32_t value) {
  printf("%d\n", value);
}

void fn_std_print_string(std::string value) {
  printf("%s\n", value.c_str());
}

void fn_std_assert(bool value) {
  if (!value) {
    printf("Assertion failed, aborting.\n");
    abort();
  }
}

void run_all_tests(void);
void entrypoint(void);

int main() {
  run_all_tests();
  entrypoint();
}
