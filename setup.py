import os
from setuptools import setup, find_packages

# Read requirements from requirements.txt
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.startswith('-r')]

# Filter out platform-specific requirements for basic setup
core_requirements = [
    req for req in requirements 
    if not any(marker in req for marker in ['; platform_system==', '; platform_machine=='])
]

setup(
    name="sysgrow-smart-agriculture",
    version="3.0.0",
    description="SYSGrow Smart Agriculture IoT System",
    long_description=open('README.md').read() if os.path.exists('README.md') else "",
    long_description_content_type="text/markdown",
    author="Sebastian Gomez",
    author_email="patoruzuy@tutanota.com",
    url="https://github.com/sysgrow",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=core_requirements,
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-flask>=1.2.0',
            'pytest-cov>=4.1.0',
            'black>=23.7.0',
            'flake8>=6.0.0',
            'mypy>=1.5.0',
        ],
        'hardware': [
            'RPi.GPIO>=0.7.1',
            'gpiozero>=1.6.0',
            'adafruit-circuitpython-ads1x15>=2.2.21',
        ],
        'ai': [
            'tensorflow>=2.13.0',
            'torch>=2.0.0',
            'torchvision>=0.15.0',
        ],
        'complete': [
            'tensorflow>=2.13.0',
            'torch>=2.0.0',
            'RPi.GPIO>=0.7.1',
            'adafruit-circuitpython-ads1x15>=2.2.21',
        ]
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
        'console_scripts': [
            'sysgrow-backend=smart_agriculture_app:main',
            'sysgrow-scheduler=app.workers.scheduler_cli:main',
            'sysgrow-ml-trainer=ai.enhanced_ml_trainer:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.json', '*.yaml', '*.yml', '*.md', '*.txt'],
        'templates': ['*.html'],
        'static': [
            'css/*.css',
            'css/components/*.css',
            'css/sensor-analytics/*.css',
            'js/*.js',
            'js/components/*.js',
            'js/dashboard/*.js',
            'js/devices/*.js',
            'js/plants/*.js',
            'js/sensor-analytics/*.js',
            'js/settings/*.js',
            'js/utils/*.js',
            'images/*',
        ],
        'config': ['*.json', '*.yaml'],
    },
)
