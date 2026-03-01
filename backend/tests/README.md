# Tests

This directory contains all tests for the AmneziaVPN Management API backend.

## Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_auth.py` - Unit tests for authentication utilities
- `test_auth_integration.py` - Integration tests for auth API
- `test_models.py` - Unit tests for database models
- `test_ssh_manager.py` - Unit tests for SSH manager
- `test_servers_integration.py` - Integration tests for servers API
- `test_users_integration.py` - Integration tests for users API
- `test_validation.py` - Tests for input validation

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run specific test file
```bash
pytest tests/test_auth.py
```

### Run specific test class
```bash
pytest tests/test_auth.py::TestPasswordHashing
```

### Run specific test
```bash
pytest tests/test_auth.py::TestPasswordHashing::test_password_hash_and_verify
```

## Test Coverage

Current test coverage includes:
- ✅ Authentication (login, logout, JWT tokens)
- ✅ User management CRUD
- ✅ Server management CRUD
- ✅ Password hashing and verification
- ✅ SSH password encryption/decryption
- ✅ SSH connection management
- ✅ Input validation
- ✅ Rate limiting
- ✅ Authorization checks

## Continuous Integration

Tests are automatically run on:
- Every commit (if CI/CD is configured)
- Pull requests
- Before deployment

## Writing New Tests

When adding new features, please add corresponding tests:
1. Unit tests for business logic
2. Integration tests for API endpoints
3. Validation tests for input schemas

Mark tests appropriately:
```python
@pytest.mark.unit  # For unit tests
@pytest.mark.integration  # For integration tests
@pytest.mark.slow  # For slow running tests
```
