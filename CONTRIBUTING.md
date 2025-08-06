# Contributing to SyncZ

Thank you for your interest in contributing to SyncZ! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/jorgemunozl/syncZ.git`
3. Create a feature branch: `git checkout -b feature-name`
4. Make your changes
5. Test your changes
6. Commit with a descriptive message
7. Push to your fork and create a pull request

## Development Setup

### Prerequisites
- Python 3.6+
- `requests` library

### Setup
```bash
# Clone the repository
git clone https://github.com/jorgemunozl/syncFilesDevicesLocal.git
cd syncFilesDevicesLocal

# Install dependencies
pip install -r requirements.txt

# Test the setup
python configure.py
```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and small

## Testing

Before submitting a pull request:

1. Test both server and client components
2. Test with different file types and sizes
3. Verify sync behavior with various scenarios:
   - New files
   - Modified files
   - Deleted files
   - Network interruptions

### Manual Testing Checklist

- [ ] Server starts without errors
- [ ] Client connects to server successfully
- [ ] Files sync in both directions
- [ ] Metadata is generated correctly
- [ ] File integrity is maintained (SHA256 verification)
- [ ] Modification times are preserved
- [ ] Deleted files are cleaned up

## Submitting Changes

### Pull Request Process

1. Update documentation if needed
2. Add/update tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md with your changes
5. Create a pull request with:
   - Clear description of changes
   - References to related issues
   - Testing performed

### Commit Messages

Use clear, descriptive commit messages:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 50 characters
- Reference issues and pull requests when applicable

Examples:
```
Add support for custom server ports
Fix file deletion sync bug
Update Termux installation instructions
```

## Reporting Issues

When reporting bugs or requesting features:

1. Search existing issues first
2. Use issue templates when available
3. Provide clear steps to reproduce
4. Include system information:
   - OS and version
   - Python version
   - Network configuration
   - Error messages

## Feature Requests

We welcome feature requests! Please:

1. Check if the feature already exists
2. Explain the use case
3. Describe the expected behavior
4. Consider implementation complexity

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers get started
- Maintain a welcoming environment

## Questions?

Feel free to open an issue for questions about:
- Using SyncZ
- Development setup
- Contributing process
- Technical details

Thank you for contributing to SyncZ!
