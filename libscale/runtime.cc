#include <stdint.h>
#include <stdio.h>
#include <string>

void fn_print_int(int32_t value) {
  printf("%d\n", value);
}

void fn_print_string(std::string value) {
  printf("%s\n", value.c_str());
}


void fn_main(void);

int main() {
  fn_main();
}
