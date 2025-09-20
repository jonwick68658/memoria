import sys
sys.path.insert(0, '.')

from src.memoria.security.input_validator import InputValidator

validator = InputValidator()

# Test SQL injection
result = validator.validate("'; DROP TABLE users; --")
print('SQL Injection Test:', result.is_valid, result.reason)

# Test XSS
result = validator.validate("<script>alert('XSS')</script>")
print('XSS Test:', result.is_valid, result.reason)

# Test normal input
result = validator.validate("Hello world")
print('Normal Input Test:', result.is_valid, result.reason)