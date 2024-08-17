from setuptools import setup, find_packages

def read_version():
    with open("version.txt", "r") as file:
        return file.read().strip()

setup(
    name="odatix",
    version=read_version(),
    author="Jonathan Saussereau",
    author_email="jonathan.saussereau@ims-bordeaux.fr",
    description="A FPGA/ASIC toolbox for design space exploration",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/jsaussereau/Asterism",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0 License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
        'odatix=scripts.odatix:main',
        'odatix-explorer=scripts.odatix_explorer:main',
        ],
    },
)
