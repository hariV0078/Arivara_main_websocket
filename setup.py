from setuptools import find_packages, setup

LATEST_VERSION = "0.14.0"

exclude_packages = [
    "selenium",
    "webdriver",
    "fastapi",
    "fastapi.*",
    "uvicorn",
    "jinja2",
    "gpt-researcher",
    "langgraph"
]

with open(r"README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    reqs = [line.strip() for line in f if not any(pkg in line for pkg in exclude_packages)]
