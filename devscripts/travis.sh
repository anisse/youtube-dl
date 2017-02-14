#!/bin/sh

if [ -n "$YTDL_TEST_SET" ]; then
	exec ./devscripts/run_tests.sh
else
	exec ./devscripts/regdetect.py
fi
