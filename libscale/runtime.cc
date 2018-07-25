#include <iostream>
#include <stdint.h>
#include <stdlib.h>
#include <string>

void fn_std_print_int(int32_t value) {
  std::cout << value;
}

void fn_std_print_string(std::string value) {
  std::cout << value;
}

void fn_std_abort() {
  abort();
}
