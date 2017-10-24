#!/usr/bin/env python3

from __future__ import print_function, unicode_literals

import subprocess
import sys
import os
import time

NOSECOMMAND="nosetests"
CORE_TESTS="age_restriction|download|subtitles|write_annotations|iqiyi_sdk_interpreter|youtube_lists"


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
    # or this:
    #   test_opengraph (test.test_InfoExtractor.TestInfoExtractor): ... ok
    # into this test handle:
    #   test.test_InfoExtractor:TestInfoExtractor.test_opengraph
    testpath = s[1].strip('():').split('.')
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

def process_stream(f, verbose_level):
    results = {}
    buf = None
    for line in f:
        if verbose_level >= 1: print(line, end='')
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
    if verbose_level >= 2: # print the end of the file
        for line in f: # it might contain interesting info, like tracebacks
            print(line, end='')
    fill_results(process(buf), results) # process last line
    return results


def launch_nose(args=[], verbose_level=2):
    nose = subprocess.Popen([NOSECOMMAND, "-v"] + args, stderr=subprocess.PIPE, universal_newlines=True)
    results = process_stream(nose.stderr, verbose_level)
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

def test_stability(refcommit, testcommit, failed_tests):
    git_checkout(refcommit)
    print("Testing at commit " + refcommit)
    refresults = launch_nose(failed_tests)
    stable_tests = []
    for k in refresults:
        if refresults[k] != "ok":
            print("Test %s is unreliable !"%(k))
        else:
            stable_tests.append(k)
    git_checkout(testcommit)
    print("Back to commit " + testcommit)
    return stable_tests

def iterate_tests(refcommit, testcommit, testlist=[], iterations=9, cooldown=60):
    failed_tests=testlist # empty means run all tests
    # run tests passed in arguments (or all) and get list of failed tests
    # keep running those tests a few times to make sure the failure wasn't
    # temporary (bad connection, site error, ...)
    for i in range(iterations):
        if i > 3 and len(failed_tests) < 5:
            # We have reduced the number of tests, we now test them for stability
            print("We only have %d tests at iteration %d, testing for reliablity"%(len(failed_tests), i))
            failed_tests = test_stability(refcommit, testcommit, failed_tests)
            if len(failed_tests) == 0: # no more stable tests
                return {}
            time.sleep(cooldown)
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

def regressive_tests(refresults, testresults):
    regressive = []
    # Return list of tests that are ok in refresults but not in testresults
    for k in refresults:
        assert k in testresults, "New unknown test case %s, not in:\n%s\nbut in:\n%s"%(k, testresults, refresults)
        if refresults[k] == "ok" and refresults[k] != testresults[k]: #let's assume FAIL == ERROR
            regressive.append(k)

    return regressive

def list_nose_tests(opts):
    tests = list(launch_nose(["--collect-only"] + opts, verbose_level=0).keys())
    return tests

def test_subset():

    # See if we need to slice the work and do only one part
    slice_arg = os.getenv("TESTS")
    if slice_arg == None:
        return None

    return slice_arg.split('_')[1]

def sub_tests(subset):
    if subset == "core":
        nose_opt = ["-I", "test_(" + CORE_TESTS + ")\.py"]
    elif subset == "download":
        nose_opt = ["-I", "test_(?!" + CORE_TESTS + ")\.py"]
    else:
        raise RuntimeError("Unknown test subset " + subset)
    all_tests = list_nose_tests(nose_opt)

    print("Running %s test subset ; it has %d tests"%(subset, len(all_tests)))

    return all_tests

def bisect(good, bad, test):
    def git_bisect(args):
        ret = subprocess.call(["git", "bisect"] + args)
        if ret != 0:
            raise RuntimeError("git bisect failed with " + " ".join(args))
    print("Bisecting %s between %s and %s"%(test, good, bad))
    git_bisect(["start", bad, good])
    git_bisect(["run", NOSECOMMAND, "--verbose", "--detailed-errors", test])
    git_bisect(["reset"])
    print("Bisect done")

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

    parallel_nose_opts=[]
    subset = test_subset()
    if subset == "download":
        parallel_nose_opts=["--processes=4",  "--process-timeout=540"]

    sub_test_list = sub_tests(subset)
    if sub_test_list != None:
        args = sub_test_list
    else:
        args = sys.argv[3:] # use remaining args to limit test selection (if there are any)

    results = launch_nose(parallel_nose_opts + args, verbose_level=1)

    failed_tests = filter_bad(results)
    if len(failed_tests) == 0:
        print("No failure, exiting")
        sys.exit(0)

    print("%d tests are failing at %s, now testing if they are regression from %s" %
            (len(failed_tests), testcommit, refcommit))

    git_checkout(refcommit)

    results_ref = launch_nose(parallel_nose_opts + failed_tests, verbose_level=1)
    print("Second run of %d tests done."%len(failed_tests))

    regressive = regressive_tests(results_ref, results)

    git_checkout(testcommit)

    if len(regressive) == 0:
        print("There was no detected regression")
        sys.exit(0)


    print("%d test(s) have a potential regression. Retrying them a few times to be sure"%len(regressive))

    results_retry = iterate_tests(refcommit, testcommit, regressive)

    failed_retry = filter_bad(results_retry)
    if len(failed_retry) == 0:
        print("All false alarms, exiting")
        sys.exit(0)

    print("We have %d regressions"%len(failed_retry))
    for k in failed_retry:
        print("Test %s was %s in %s, is now %s at %s"%(k, results_ref[k],
            refcommit, results_retry[k], testcommit))
        bisect(refcommit, testcommit, k)

    git_checkout(testcommit)

    sys.exit(-1)

if __name__ == "__main__":
    main()

