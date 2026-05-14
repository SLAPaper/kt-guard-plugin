# Contributing to kt-guard-plugin

Thanks for your interest in contributing! Here's how to get started.

## Setting Up Development Environment

```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
pip install -e ".[dev]"
```

## Making Changes

1. Create a new branch: `git checkout -b feature/your-feature`
2. Make your changes in the appropriate files
3. Ensure code follows the project style
4. Add tests if applicable (in `tests/unit/`)
5. Run tests: `pytest tests/unit/ -v`

## Code Style

- Follow PEP 8
- Use type hints
- Keep functions focused and well-documented
- Run `black` and `ruff` before committing

## Testing

```bash
pytest tests/unit/ -v
```

## Submitting a PR

1. Push your branch to GitHub
2. Open a Pull Request with a clear description
3. Ensure all tests pass
4. Address any review feedback

## Questions?

Open an issue on GitHub or reach out to the maintainers.
