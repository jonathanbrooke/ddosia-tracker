# Contributing to DDoSia Tracker

Thank you for your interest in contributing to DDoSia Tracker! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Docker version, etc.)
- Relevant logs

### Suggesting Enhancements

Enhancement suggestions are welcome! Please open an issue with:
- Clear description of the feature
- Use case and benefits
- Proposed implementation (if applicable)

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/ddosia-tracker
   cd ddosia-tracker
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed
   - Ensure all tests pass

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```
   
   Use clear, descriptive commit messages:
   - `feat: Add new API endpoint for X`
   - `fix: Resolve database connection issue`
   - `docs: Update configuration guide`
   - `refactor: Improve processor performance`

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**
   - Provide a clear title and description
   - Reference any related issues
   - Explain what changed and why

## Development Guidelines

### Code Style

- **Python**: Follow PEP 8 guidelines
  - Maximum line length: 79 characters
  - Use meaningful variable names
  - Add docstrings for functions/classes
  - Use type hints where appropriate

- **SQL**: 
  - Uppercase keywords (SELECT, FROM, WHERE)
  - Meaningful table/column names
  - Add comments for complex queries

- **Docker**:
  - Minimize layers
  - Use specific version tags
  - Document exposed ports and volumes

### Testing

- Write unit tests for new functionality
- Ensure existing tests pass: `docker-compose run --rm processor pytest`
- Test with realistic data volumes
- Verify docker-compose builds successfully

### Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic
- Document new configuration options in .env.example
- Update API documentation for new endpoints

### Environment Variables

When adding new configuration:
1. Add to `.env.example` with description
2. Provide sensible default in code
3. Document in README.md
4. Update docker-compose.yml if needed

### Database Changes

For schema modifications:
1. Create a new migration file in `migrations/`
2. Use sequential numbering (e.g., `011_your_change.sql`)
3. Test migration on fresh database
4. Test migration on database with existing data
5. Document breaking changes

## Areas Needing Help

Current priorities:
- [ ] Improved test coverage
- [ ] Performance optimization for large datasets
- [ ] Additional data visualizations
- [ ] API authentication/rate limiting
- [ ] Kubernetes deployment manifests
- [ ] Additional data sources
- [ ] Mobile-responsive UI improvements

## Questions?

Open an issue labeled "question" or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
