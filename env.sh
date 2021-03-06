#!/bin/sh
# Set up the environment needed for our build.  Tries to keep
# everything except pip3, python3, and virtualenv inside virutalenv.

# For EC2, follow: http://markus.com/install-theano-on-aws/
# Remember to pick .deb(network), not .deb(local)
# Before you run env.sh, also install:
# liblapack-dev
# libfreetype6-dev
# libpng12-dev
# libjpeg-dev

set -e
command -v python3 >/dev/null 2>&1 || { \
  echo >&2 "python3 is required"; sudo apt-get install python3; }
command -v pip3 >/dev/null 2>&1 || { \
  echo >&2 "pip3 is required"; sudo apt-get install python3-pip; }
python3 -c 'import ensurepip' >/dev/null 2>&1 || { \
  echo >&2 "python3-venv is required"; sudo apt-get install python3.4-venv; }

rm -rf env
python3 -m venv env
. env/bin/activate

# upgrade pip inside venv since Ubuntu 14.04 uses a really old one
python3 -m pip install --upgrade pip

# install wheel in venv so we get wheel caching
python3 -m pip install wheel

# numpy isn't listed as a dependency in scipy, so we need to do it by hand
python3 -m pip install numpy
python3 -m pip install scipy

# Use Theano from the latest on github.
if [ ! -d env/src/theano/.git ]; then
  git clone https://github.com/Theano/Theano.git env/src/theano
fi

# Update to latest; discard any local changes.
git -C env/src/theano fetch origin
git -C env/src/theano checkout master
git -C env/src/theano clean -d -f
git -C env/src/theano reset --hard origin/master
python3 -m pip install --upgrade env/src/theano

# Also use Lasagne from the latest on github, but also patch in batchnorm.
if [ ! -d env/src/lasagne/.git ]; then
  git clone https://github.com/Lasagne/Lasagne.git env/src/lasagne
fi

# Get latest lasagne and apply batcnnorm patch into local master branch.
git -C env/src/lasagne fetch origin
git -C env/src/lasagne checkout master
git -C env/src/lasagne clean -d -f
git -C env/src/lasagne reset --hard origin/master
# Merge pull 467.
# PULL467="https://patch-diff.githubusercontent.com/raw/Lasagne/Lasagne/pull/467.patch"
# curl $PULL467 | patch -Np 1 -d env/src/lasagne
python3 -m pip install --upgrade env/src/lasagne

# pip install -e works for everything else.
python3 -m pip install --upgrade -e .
# exit the venv
deactivate
