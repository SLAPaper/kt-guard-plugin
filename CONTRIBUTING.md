# Contributing to kt-guard-plugin

Thanks for your interest in contributing! Here's how to get started.

## Setting Up Development Environment

```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
pip install -e .
```

## Making Changes

1. Create a new branch: `git checkout -b feature/your-feature`
2. Make your changes in the appropriate files
3. Ensure code follows the project style
4. Add tests if applicable (in `tests/unit/`)
5. Run the relevant verification commands

## Code Style

- Follow PEP 8
- Use type hints
- Keep functions focused and well-documented
- Run `ruff` and `black` on changed Python files before committing

## Testing

```bash
uv run --with pytest pytest
uv run ruff check kt_guard_plugin tests
uv run --with black black --check --target-version py313 tests
uv run python tests/verification/verify_enhancements.py
uv run python tests/verification/verify_installation.py
```

## Submitting a PR

1. Push your branch to GitHub
2. Open a Pull Request with a clear description
3. Ensure all tests pass
4. Address any review feedback

## Questions?

Open an issue on GitHub or reach out to the maintainers.
