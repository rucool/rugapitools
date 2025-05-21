# Rutgers University Gliders API Tools
Collection of python classes, functions and scripts for interacting with the 
[RU-COOL Gliders API](https://marine.rutgers.edu/cool/data/gliders/api/).

# Contents

- [Background](#background)
- [Installation](#installation)

## Background

This package provides classes, functions and scripts for querying the [RU-COOL Gliders API](https://marine.rutgers.edu/cool/data/gliders/api/)
to get information on all RU-COOL Glider deployments, create kml track files and cartopy maps of tracks as well as hexbin maps of glider
coverage.

## Installation
Conda:

    > git clone https://github.com/rucool/rugapitools.git
    > cd ./rugapitools
    > conda env create -f environment.yml

Since this toolbox is not (yet) a package installable via conda, pip, etc., you'll need to add this path to your 
PYTHONPATH in order import the package from within python.  While a bit tedious, this does provide the user with the 
ability to modify the source code and immediately see the changes. Conda provides 
[instructions on how to do this](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#saving-environment-variables).

Following the instructions above, the repo includes an [env_vars.sh](https://github.com/rucool/rugapitools/blob/main/env_vars.sh)
that can be dropped into:

    ${HOME}/miniconda/envs/gliders/etc/conda/activate.d

to provide access to the package locations.
