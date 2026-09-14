# Contributing to Automated Desktop File Organizer

Thank you for your interest in contributing to **Automated Desktop File Organizer**! 🎉

This document outlines the guidelines and best practices for submitting issues, feature requests, and code contributions.

---

## Code of Conduct

Please help us keep this project welcoming, collaborative, and friendly for all contributors and users. Treat everyone with respect and empathy.

---

## How Can You Contribute?

### 1. Reporting Bugs
Before opening a new issue:
- Check the [Troubleshooting](#) section in the `README.md`.
- Search existing issues to ensure the bug hasn't already been reported.

When opening an issue, please include:
- **Operating System & Python version** (e.g. Windows 11, Python 3.13).
- **Steps to reproduce** the issue.
- **Expected behavior vs. Actual behavior**.
- **Log outputs** from `logs/organizer.log` (make sure to sanitize any personal paths or sensitive info).

---

### 2. Suggesting Enhancements & New Features
We welcome new ideas, such as:
- Support for additional file categories or archive formats.
- Date-based sorting options (e.g., sorting by Year/Month).
- Custom desktop notification integrations.

To propose a feature:
- Open a feature request issue describing the proposed functionality and why it would be beneficial.

---

### 3. Submitting Pull Requests (PRs)

Follow these steps to contribute code:

#### Step 1: Fork & Clone
```bash
git clone https://github.com/subediSanjok/Automated-Desktop-File-Organizer.git
cd Automated-Desktop-File-Organizer
```

#### Step 2: Create a Dedicated Branch
```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/issue-description
```

#### Step 3: Setup Local Development Environment
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

#### Step 4: Follow Coding Standards
- **Python Version**: Ensure code is compatible with Python 3.10+.
- **Type Annotations**: Use static typing everywhere with `typing` / `from __future__ import annotations`.
- **Code Style**: Follow PEP 8 guidelines.
- **Testing**: Add or update corresponding unit tests in `tests/` for any new functionality.

#### Step 5: Run Verification
Before pushing, run all tests and type checks:
```bash
# Run pytest test suite
pytest

# Run static type checker
npx pyright
```

#### Step 6: Commit and Push
```bash
git add .
git commit -m "Add descriptive commit message"
git push origin feature/your-feature-name
```

#### Step 7: Open a Pull Request
- Go to the GitHub repository and click **"Compare & pull request"**.
- Describe the changes made and link any related issues.

---

## Project Owner & Maintainer

- **Owner**: [Sanjok Subedi](https://github.com/subediSanjok)
- **Repository**: [Automated-Desktop-File-Organizer](https://github.com/subediSanjok/Automated-Desktop-File-Organizer)

Thank you for helping improve the project!
