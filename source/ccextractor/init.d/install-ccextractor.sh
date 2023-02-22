#!/bin/bash
# -
# File: install-ccextractor.sh
# Project: plugins
# File Created: 17 Febuary 2023
# Author: chacawaca
# -----
# Last Modified: 17 Febuary 2023
# Modified By: chacawaca
# -

# Script is executed by the Unmanic container on startup to auto-install dependencies

if ! command -v ccextractor &> /dev/null; then
    echo "**** Installing ccextractor ****"
    apt-get update
    apt-get install -y ccextractor
else
    echo "**** ccextractor already installed ****"
fi
