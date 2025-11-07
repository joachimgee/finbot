"""
FinBot v2.0 - Quantitative Trading Platform

A comprehensive quantitative trading platform integrating best-of-breed 
open-source tools for data acquisition, feature engineering, backtesting, 
portfolio optimization, and machine learning.
"""

from setuptools import setup, find_packages
import os

def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as fh:
            return fh.read()
    return __doc__

def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as fh:
            requirements = []
            for line in fh:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('='):
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    if line:
                        requirements.append(line)
            return requirements
    return []

setup(
    name="finbot",
    version="2.0.0",
    author="FinBot Team",
    author_email="team@finbot.io",
    description="Quantitative trading platform integrating best-of-breed open-source tools",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/joachimgee/finbot",
    project_urls={
        "Bug Tracker": "https://github.com/joachimgee/finbot/issues",
        "Documentation": "https://github.com/joachimgee/finbot/blob/main/docs/",
        "Source Code": "https://github.com/joachimgee/finbot",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Science/Research",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords=[
        "finance", "trading", "quantitative", "backtesting",
        "portfolio-optimization", "machine-learning",
    ],
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "black>=23.7.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
        "jupyter": [
            "jupyter>=1.0.0",
            "jupyterlab>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "finbot=financial_analyzer.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
