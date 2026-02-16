from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent

# Read requirements (ignore comments and recursive -r entries)
req_path = ROOT / "requirements.txt"
requirements = []
if req_path.exists():
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        requirements.append(line)

# Exclude strict platform-specific markers from base install_requires
core_requirements = [
    r for r in requirements if not any(marker in r for marker in ["; platform_system==", "; platform_machine=="])
]

readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""

setup(
    name="sysgrow-smart-agriculture",
    version="3.0.0",
    description="SYSGrow Smart Agriculture IoT System",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Sebastian Gomez",
    author_email="patoruzuy@tutanota.com",
    url="https://github.com/sysgrow",
    packages=find_packages(exclude=("tests", "docs")),
    python_requires=">=3.8,<4",
    install_requires=core_requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-flask>=1.2.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "hardware": [
            "RPi.GPIO>=0.7.1",
            "gpiozero>=1.6.0",
            "adafruit-circuitpython-ads1x15>=2.2.21",
        ],
        "ai": ["tensorflow>=2.13.0", "torch>=2.0.0", "torchvision>=0.15.0"],
        "complete": [
            "tensorflow>=2.13.0",
            "torch>=2.0.0",
            "RPi.GPIO>=0.7.1",
            "adafruit-circuitpython-ads1x15>=2.2.21",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Agriculture",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    keywords="iot agriculture smart-farming esp32 sensors automation machine-learning",
    entry_points={
        "console_scripts": [
            "sysgrow-backend=smart_agriculture_app:main",
            "sysgrow-scheduler=app.workers.scheduler_cli:main",
            "sysgrow-ml-trainer=ai.enhanced_ml_trainer:main",
        ]
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml", "*.md", "*.txt"],
        "templates": ["*.html"],
        "static": [
            "css/*.css",
            "css/components/*.css",
            "css/sensor-analytics/*.css",
            "js/*.js",
            "js/components/*.js",
            "js/dashboard/*.js",
            "js/devices/*.js",
            "js/plants/*.js",
            "js/sensor-analytics/*.js",
            "js/settings/*.js",
            "js/utils/*.js",
            "images/*",
        ],
        "config": ["*.json", "*.yaml"],
    },
)
