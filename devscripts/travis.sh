#!/bin/sh

if [ "$TESTS" = "complete" ]; then
	exec ./devscripts/run_tests.sh
else
	exec ./devscripts/regdetect.py
fi
