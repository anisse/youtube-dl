#!/usr/bin/env python3

from __future__ import print_function

import subprocess
import sys
import os
import time


def process(test):
    # Parse nose output to get test statuses
    # Format: test_<test_name> (<test_path>) ... [multi-line-error-message?] {ok,ERROR,FAIL}
    if not test or len(test) == 0:
        print("Received empty line")
        return (None, None)
    s = test.split()
    if len(s) < 4:
        print("Bad line passed, not enough elements:", test)
    # We try to convert this nose output:
    #   test_opengraph (test.test_InfoExtractor.TestInfoExtractor) ... ok
    # into this test handle:
    #   test.test_InfoExtractor:TestInfoExtractor.test_opengraph
    testpath = s[1][1:-1].split('.')
    if len(testpath) != 3:
        print("Bad testpath passed, not enough elements:", testpath)
        return (None, None)
    fulltestname = "%s.%s:%s.%s"%(testpath[0], testpath[1], testpath[2], s[0])

    status = s[-1]
    if status not in ("ok", "FAIL", "ERROR"):
        print("Unknown test status", status)
        return (None, None)

    # we cannot assume that a test failing with a warning is ok (network error)
    if status == "ok" and test.find("WARNING") != -1:
        status = "WARNING"

    return (fulltestname, status)

def fill_results(res, results):
    if res[0] != None and res[1] != None:
        results[res[0]] = res[1]

def process_stream(f, verbose):
    results = {}
    buf = None
    for line in f:
        if verbose: print(line, end='')
        if line.startswith("===========") or line.startswith("--------------"):
            #this is the end
            break
        if line.startswith("test_"): #new test, process previous test
            if buf != None:
                fill_results(process(buf), results) # for every other element this signals the beginning of a new one
            buf = line
        else:
            if buf and len(buf) > 0: # some tests have multi-line outputs
                buf += line
    if verbose: # print the end of the file
        for line in f: # it might contain interesting info, like tracebacks
            print(line, end='')
    fill_results(process(buf), results) # process last line
    return results


def launch_nose(args=[], verbose=True):
    nose = subprocess.Popen(["nosetests", "-v"] + args, stderr=subprocess.PIPE, universal_newlines=True)
    results = process_stream(nose.stderr, verbose)
    nose.stderr.close()
    nose.wait()
    return results

def filter_bad(results):
    # Filter failing/error tests
    redo = {}
    for k in results.keys():
        if results[k] != "ok":
            redo[k] = results[k]
    return list(redo.keys())

def iterate_tests(testlist=[], iterations=16, cooldown=60):
    failed_tests=testlist # empty means run all tests
    # run tests passed in arguments (or all) and get list of failed tests
    # keep running those tests a few times to make sure the failure wasn't
    # temporary (bad connection, site error, ...)
    for i in range(iterations):
        results = launch_nose(failed_tests)
        failed_tests = filter_bad(results)
        print("Run %d done. Has %d out of %d non-ok tests"%(i, len(failed_tests), len(results.keys())))
        if len(failed_tests) == 0: # no failure. Awesome !
            break
        time.sleep(cooldown)
    return results # this will return a partial result list. It does not matter since ok-tests aren't that interesting

def git_checkout(arg):
    ret = subprocess.call(["git", "checkout", "--quiet", arg])
    if ret != 0:
        raise RuntimeError("git checkout failed")

    #results = launch_nose(["test.test_YoutubeDL:TestFormatSelection.test_youtube_format_selection"])
    #f = open("out2.txt", "r")
    #results = process_stream(f)
    #f.close()

def regressive_tests(refresults, testresults):
    regressive = []
    # Return list of tests that are ok in refsults but not in testresults
    for k in refresults:
        assert k in testresults, "New unknown test case"
        if refresults[k] == "ok" and refresults[k] != testresults[k]: #let's assume FAIL == ERROR
            regressive.append(k)

    return regressive

def list_nose_tests():
    tests = sorted(launch_nose(["--collect-only"], verbose=False).keys())
    return tests

def sub_tests():
    # See if we need to slice the work and do only one part
    slice_arg = os.getenv("TESTS")
    if slice_arg == None:
        return None

    test_slice = slice_arg.split('_')[1]
    slice_bounds = test_slice.split('-of-')
    current_slice = int(slice_bounds[0])
    nr_slices = int(slice_bounds[1])
    all_tests = list_nose_tests()
    length = len(all_tests)
    sub_test_list = all_tests[(current_slice-1)*length // nr_slices : \
                              current_slice*length // nr_slices]

    print("Running slice %d of %d; it has %d out of %d tests"%(current_slice,
            nr_slices, len(sub_test_list), length))

    return sub_test_list


def main():
    if len(sys.argv) < 3:
        commit_range = os.getenv("TRAVIS_COMMIT_RANGE")
        if commit_range != None:
            commits = commit_range.split("...")
            refcommit, testcommit = commits[0], commits[1]
        else:
            testcommit="master"
            refcommit="master^"
    else:
        testcommit=sys.argv[1]
        refcommit=sys.argv[2]

    print("Testing if commit-ish %s introduced regressions compared to %s"%(testcommit, refcommit))

    git_checkout(testcommit)

    sub_test_list = sub_tests()

    if sub_test_list != None:
        args = sub_test_list
    else:
        args = sys.argv[3:] # use remaining args to limit test selection (if there are any)

    results = launch_nose(args)

    failed_tests = filter_bad(results)
    if len(failed_tests) == 0:
        print("No failure, exiting")
        sys.exit(0)

    print("%d tests are failing at %s, now testing if they are regression from %s" %
            (len(failed_tests), testcommit, refcommit))

    git_checkout(refcommit)

    results_ref = launch_nose(failed_tests)
    print("Second run of %d tests done."%len(failed_tests))

    regressive = regressive_tests(results_ref, results)

    git_checkout(testcommit)

    if len(regressive) == 0:
        print("There was no detected regression")
        sys.exit(0)


    print("%d test(s) have a potential regression. Retrying them a few times to be sure"%len(regressive))

    results_retry = iterate_tests(regressive)

    failed_retry = filter_bad(results_retry)
    if len(failed_retry) == 0:
        print("All false alarms, exiting")
        sys.exit(0)

    print("We have %d regressions"%len(failed_retry))
    for k in failed_retry:
        print("Test %s was %s in %s, is now %s at %s"%(k, results_ref[k],
            refcommit, results_retry[k], testcommit))

    git_checkout(testcommit)

    sys.exit(-1)

if __name__ == "__main__":
    main()

