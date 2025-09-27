from setuptools import setup, find_packages

setup(
    name='neuronum',
    version='8.3.0',
    author='Neuronum Cybernetics',
    author_email='welcome@neuronum.net',
    description='The E2E Web Engine',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://neuronum.net",
    project_urls={
        "GitHub": "https://github.com/neuronumcybernetics/neuronum",
    },
    packages=find_packages(include=["neuronum", "cli"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'aiohttp',
        'websockets',
        'click',
        'questionary',
        'python-dotenv',
        'requests',
        'psutil',
        'jinja2',
        'cryptography',
    ],
    entry_points={
        "console_scripts": [
            "neuronum=cli.main:cli"
        ]
    },
    python_requires='>=3.8', 
)
