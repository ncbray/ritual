#include <iostream>
#include <stdint.h>
#include <stdlib.h>
#include <string>

std::string m_builtin_string_to_string(std::string& self) {
  return self;
}

std::string m_builtin_bool_to_string(bool& self) {
  return std::to_string(self);
}

std::string m_builtin_i8_to_string(int8_t& self) {
  return std::to_string(self);
}

std::string m_builtin_u8_to_string(uint8_t& self) {
  return std::to_string(self);
}

std::string m_builtin_i16_to_string(int16_t& self) {
  return std::to_string(self);
}

std::string m_builtin_u16_to_string(uint16_t& self) {
  return std::to_string(self);
}

std::string m_builtin_i32_to_string(int32_t& self) {
  return std::to_string(self);
}

std::string m_builtin_u32_to_string(uint32_t& self)  {
  return std::to_string(self);
}

std::string m_builtin_i64_to_string(int64_t& self) {
  return std::to_string(self);
}

std::string m_builtin_u64_to_string(uint64_t& self) {
  return std::to_string(self);
}

std::string m_builtin_f32_to_string(float& self) {
  return std::to_string(self);
}

std::string m_builtin_f64_to_string(double& self) {
  return std::to_string(self);
}

void f_std_print(std::string value) {
  std::cout << value;
}

void f_std_abort() {
  abort();
}
