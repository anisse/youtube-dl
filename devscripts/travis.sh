#!/bin/sh

if [ "$TESTS" = "regression" ]; then
	exec ./devscripts/regdetect.py
else
	exec nosetests test --verbose
fi
