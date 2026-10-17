# -*- coding: utf-8 -*-
import os
import sys
from setuptools import setup, find_packages

def read_version():
    with open("odatix/version.txt", "r") as file:
        return file.read().strip()

def read_requirements():
    with open("requirements.txt") as f:
        requirements = [line.strip() for line in f if line.strip()]
    if sys.platform == "win32":
        with open("requirements_win32.txt") as f_win:
            win_requirements = [line.strip() for line in f_win if line.strip()]
        requirements.extend(win_requirements)
    return requirements

def package_files(package, subdirectory=""):
    """
    Every file under a directory of a package, relative to the package.

    A "**" pattern in package_data only recurses from setuptools 62.3 on, which
    no longer runs on Python 3.6: listing the files keeps every version of
    setuptools from leaving the deeper ones out of the wheel.
    """
    files = []
    for root, dirs, names in os.walk(os.path.join(package, subdirectory)):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if not name.endswith((".pyc", ".pyo")):
                files.append(os.path.relpath(os.path.join(root, name), package))
    return files

package_list = find_packages()
package_list.append('odatix_examples')
package_list.append('odatix_eda_tools')
package_list.append('odatix_init')

setup(
    name="odatix",
    version=read_version(),
    author="Jonathan Saussereau",
    author_email="jonathan.saussereau@ims-bordeaux.fr",
    description="A FPGA/ASIC toolbox for design space exploration",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/jsaussereau/Odatix",
    packages=package_list,
    package_data={
        # gui/pages holds no __init__.py: Dash loads its modules by path.
        'odatix': ['version.txt'] + package_files('odatix', 'gui/assets') + package_files('odatix', 'gui/pages'),
        'odatix_examples': package_files('odatix_examples'),
        'odatix_eda_tools': package_files('odatix_eda_tools'),
        'odatix_init': package_files('odatix_init'),
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX",
    ],
    python_requires=">=3.6",
    install_requires=read_requirements(),
    extras_require={
        "test": ["pytest>=7", "pytest-cov>=4"],
    },
    entry_points={
        "console_scripts": [
            "odatix=odatix.odatix_main:main",
            "odatix-explorer=odatix.odatix_explorer:main",
            "odatix-gui=odatix.odatix_gui:main",
        ],
    },
)
