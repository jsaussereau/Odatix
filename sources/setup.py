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
    url="https://github.com/jsaussereau/Asterism",
    packages=package_list,
    package_data={
        'odatix': [
            'version.txt',
            'explorer/**/*',
            'gui/**/*',
            'init/**/*',
            'eda_tools/**/*',
        ],
        'odatix_examples': [
            '**/*'
        ],
        'odatix_eda_tools': [
            '**/*'
        ],
        'odatix_init': [
            '**/*'
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX",
    ],
    python_requires=">=3.6",
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "odatix=odatix.odatix_main:main",
            "odatix-explorer=odatix.odatix_explorer:main",
            "odatix-gui=odatix.odatix_gui:main",
        ],
    },
)
