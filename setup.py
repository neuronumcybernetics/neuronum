from setuptools import setup, find_packages

setup(
    name='neuronum',
    version='12.3.0',
    author='Neuronum Cybernetics',
    author_email='welcome@neuronum.net',
    description='Neuronum SDK',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://neuronum.net",
    project_urls={
        "GitHub": "https://github.com/neuronumcybernetics/cell-sdk-python",
    },
    packages=find_packages(include=["neuronum", "cli"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'aiohttp',
        'aiofiles',
        'websockets',
        'click',
        'questionary',
        'python-dotenv',
        'requests',
        'cryptography',
        'bip_utils'
    ],
    entry_points={
        "console_scripts": [
            "neuronum=cli.main:cli"
        ]
    },
    python_requires='>=3.8', 
)
