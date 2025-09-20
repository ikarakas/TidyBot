from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
requirements_path = "tidybot/ai_service/requirements.txt"
if os.path.exists(requirements_path):
    with open(requirements_path, "r", encoding="utf-8") as fh:
        requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
else:
    requirements = []

setup(
    name="tidybot",
    version="1.0.0",
    author="TidyBot Team",
    author_email="tidybot@example.com",
    description="AI-Powered Intelligent File Organization System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/tidybot",
    packages=find_packages(exclude=["tests", "tests.*", "scripts", "scripts.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Filesystems",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "docker": [
            "docker>=6.0.0",
            "docker-compose>=1.29.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "tidybot2=tidybot_cli_v2:main",
            "tidybot-server=tidybot.ai_service.app.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)