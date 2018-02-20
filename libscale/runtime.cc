#include <iostream>
#include <stdint.h>
#include <stdlib.h>
#include <string>

void fn_std_print_int(int32_t value) {
  std::cout << value << std::endl;
}

void fn_std_print_string(std::string value) {
  std::cout << value << std::endl;
}

void fn_std_assert(bool value) {
  if (!value) {
    std::cerr << "Assertion failed, aborting." << std::endl;
    abort();
  }
}

void run_all_tests(void);
void entrypoint(void);

int main() {
  run_all_tests();
  entrypoint();
}
