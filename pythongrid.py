#! /usr/bin/env python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Written (W) 2008-2010 Christian Widmer
# Written (W) 2008-2010 Cheng Soon Ong
# Copyright (C) 2008-2010 Max-Planck-Society


"""
pythongrid provides a high level front-end to DRMAA-python.
This module provides wrappers that simplify submission and collection of jobs,
in a more 'pythonic' fashion.
"""

import sys
import os
import os.path
import subprocess
import bz2
import cPickle
import getopt
import time
import random
import traceback


#paths on cluster file system
# TODO set this in configuration file
PYTHONPATH = os.environ['PYTHONPATH'] 

# location of pythongrid.py on cluster file system
# TODO set this in configuration file
PYGRID = "~/svn/tools/python/pythongrid/pythongrid.py"

# define temp directories for the input and output variables
# (must be writable from cluster)
# TODO define separate client/server TEMPDIR
TEMPDIR = "~/tmp/"


# used for generating random filenames
alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

#PPATH = reduce(lambda x,y: x+':'+y, PYTHONPATH)
#print PPATH
#os.environ['PYTHONPATH'] = PPATH
#sys.path.extend(PYTHONPATH)


print "sys.path=" + str(sys.path) ;

jp = os.path.join

drmaa_present=True
multiprocessing_present=True

try:
    import drmaa
except ImportError, detail:
    print "Error importing drmaa. Only local multi-threading supported."
    print "Please check your installation."
    print detail
    drmaa_present = False

try:
    import multiprocessing
except ImportError, detail:
    print "Error importing multiprocessing. Local computing limited to one CPU."
    print "Please install python2.6 or the backport of the multiprocessing package"
    print detail
    multiprocessing_present = False

class Job(object):
    """
    Central entity that wraps a function and its data. Basically,
    a job consists of a function, its argument list, its
    keyword list and a field "ret" which is filled, when
    the execute method gets called
    """

    def __init__(self, f, args, kwlist={}, param=None, cleanup=True):
        """
        constructor of Job

        @param f: a function, which should be executed.
        @type f: function
        @param args: argument list of function f
        @type args: list
        @param kwlist: dictionary of keyword arguments
        @type kwlist: dict
        @param cleanup: flag that determines the cleanup of input and log file
        @type cleanup: boolean
        """
        self.f = f
        self.args = args
        self.kwlist = kwlist
        self.cleanup = cleanup
        self.ret = None
        self.inputfile = ""
        self.outputfile = ""
        self.nativeSpecification = ""
        self.exception = None
        self.environment = None
        self.replace_env = False

        if param!=None:
            self.__set_parameters(param)

        outdir = os.path.expanduser(TEMPDIR)
        if not os.path.isdir(outdir):
            print '%s does not exist. Please create a directory' % outdir
            raise Exception()

        # TODO: ensure uniqueness of file names
        self.name = 'pg'+''.join([random.choice(alphabet) for a in xrange(8)])
        self.inputfile = jp(outdir,self.name + "_in.bz2")
        self.outputfile = jp(outdir,self.name + "_out.bz2")
        self.jobid = ""


    def __set_parameters(self, param):
        """
        method to set parameters from dict
        """

        assert(param!=None)

        for (key, value) in param.items():
            setattr(self, key, value)

        return self


    def __repr_broken__(self):
        #TODO: fix representation
        retstr1 = ('%s\nargs=%s\nkwlist=%s\nret=%s\ncleanup=%s' %
                   self.f, self.args, self.kwlist, self.ret, self.cleanup)
        retstr2 = ('\nnativeSpecification=%s\ninputfile=%s\noutputfile=%s\n' %
                   self.nativeSpecification, self.inputfile, self.outputfile)
        return retstr1 + retstr2

    def execute(self):
        """
        Executes function f with given arguments
        and writes return value to field ret.
        If an exception is encountered during execution, ret will
        remain empty and the exception will be written
        to the exception field of the Job object.
        Input data is removed after execution to save space.
        """
        try:
            self.ret = apply(self.f, self.args, self.kwlist)

        except Exception, e:

            print "exception encountered"
            print "type:", str(type(e))
            print "line number:", sys.exc_info()[2].tb_lineno
            print e
            traceback.print_exc(file=sys.stdout)
            print "========="
            self.exception = e


class KybJob(Job):
    """
    Specialization of generic Job that provides an interface to
    the system at MPI Biol. Cyber. Tuebingen.
    """

    def __init__(self, f, args, kwlist={}, param=None, cleanup=True):
        """
        constructor of KybJob
        """
        Job.__init__(self, f, args, kwlist, param=param, cleanup=cleanup)
        self.h_vmem = ""
        self.arch = ""
        self.tmpfree = ""
        self.h_cpu = ""
        self.h_rt = ""
        self.express = ""
        self.matlab = ""
        self.simulink = ""
        self.compiler = ""
        self.imagetb = ""
        self.opttb = ""
        self.stattb = ""
        self.sigtb = ""
        self.cplex = ""
        self.nicetohave = ""


    def getNativeSpecification(self):
        """
        define python-style getter
        """

        ret = ""

        if (self.name != ""):
            ret = ret + " -N " + str(self.name)
        if (self.h_vmem != ""):
            ret = ret + " -l " + "h_vmem" + "=" + str(self.h_vmem)
        if (self.arch != ""):
            ret = ret + " -l " + "arch" + "=" + str(self.arch)
        if (self.tmpfree != ""):
            ret = ret + " -l " + "tmpfree" + "=" + str(self.tmpfree)
        if (self.h_cpu != ""):
            ret = ret + " -l " + "h_cpu" + "=" + str(self.h_cpu)
        if (self.h_rt != ""):
            ret = ret + " -l " + "h_rt" + "=" + str(self.h_rt)
        if (self.express != ""):
            ret = ret + " -l " + "express" + "=" + str(self.express)
        if (self.matlab != ""):
            ret = ret + " -l " + "matlab" + "=" + str(self.matlab)
        if (self.simulink != ""):
            ret = ret + " -l " + "simulink" + "=" + str(self.simulink)
        if (self.compiler != ""):
            ret = ret + " -l " + "compiler" + "=" + str(self.compiler)
        if (self.imagetb != ""):
            ret = ret + " -l " + "imagetb" + "=" + str(self.imagetb)
        if (self.opttb != ""):
            ret = ret + " -l " + "opttb" + "=" + str(self.opttb)
        if (self.stattb != ""):
            ret = ret + " -l " + "stattb" + "=" + str(self.stattb)
        if (self.sigtb != ""):
            ret = ret + " -l " + "sigtb" + "=" + str(self.sigtb)
        if (self.cplex != ""):
            ret = ret + " -l " + "cplex" + "=" + str(self.cplex)
        if (self.nicetohave != ""):
            ret = ret + " -l " + "nicetohave" + "=" + str(self.nicetohave)

        return ret


    def setNativeSpecification(self, x):
        """
        define python-style setter
        @param x: nativeSpecification string to be set
        @type x: string
        """

        self.__nativeSpecification = x

    nativeSpecification = property(getNativeSpecification,
                                   setNativeSpecification)



#only define this class if the multiprocessing module is present
if multiprocessing_present:

    class JobsProcess(multiprocessing.Process):
        """
        In case jobs are to be computed locally, a number of Jobs (possibly one)
        are assinged to one thread.
        """

        def __init__(self, jobs):
            """
            Constructor
            @param jobs: list of jobs
            @type jobs: list of Job objects
            """

            self.jobs = jobs
            multiprocessing.Process.__init__(self)

        def run(self):
            """
            Executes each job in job list
            """
            for job in self.jobs:
                job.execute()


def _execute(job):
    """Cannot pickle method instances, so fake a function.
    Used by _process_jobs_locally"""
    
    return apply(job.f, job.args, job.kwlist)



def _process_jobs_locally(jobs, maxNumThreads=1):
    """
    Local execution using the package multiprocessing, if present
    
    @param jobs: jobs to be executed
    @type jobs: list<Job>
    @param maxNumThreads: maximal number of threads
    @type maxNumThreads: int
    
    @return: list of jobs, each with return in job.ret
    @rtype: list<Job>
    """
   
    print "using %i threads" % (maxNumThreads)
    
    if (not multiprocessing_present or maxNumThreads == 1):
        #perform sequential computation
        for job in jobs:
            job.execute()
    else:
        po = multiprocessing.Pool(maxNumThreads)
        result = po.map(_execute, jobs)
        for ix,job in enumerate(jobs):
            job.ret = result[ix]
            
    return jobs


def submit_jobs(jobs):
    """
    Method used to send a list of jobs onto the cluster.
    @param jobs: list of jobs to be executed
    @type jobs: list<Job>
    """

    s = drmaa.Session()
    s.initialize()
    jobids = []

    for job in jobs:
        jt = s.createJobTemplate()

        #fetch only specific env vars from shell
        #shell_env = {"LD_LIBRARY_PATH": os.getenv("LD_LIBRARY_PATH"),
        #             "PYTHONPATH": os.getenv("PYTHONPATH"),
        #             "MOSEKLM_LICENSE_FILE": os.getenv("MOSEKLM_LICENSE_FILE"),
        #             }

        # fetch env vars from shell        
        shell_env = os.environ

        if job.environment and job.replace_env:
            # only consider defined env vars
            jt.jobEnvironment = job.environment

        elif job.environment and not job.replace_env:
            # replace env var from shell with defined env vars
            env = shell_env
            env.update(job.environment)
            jt.jobEnvironment = env

        else:
            # only consider env vars from shell
            jt.jobEnvironment = shell_env
            

        jt.remoteCommand = os.path.expanduser(PYGRID)
        jt.args = [job.inputfile]
        jt.joinFiles = True
        jt.nativeSpecification = job.nativeSpecification
        jt.outputPath = ":" + os.path.expanduser(TEMPDIR)
        jt.errorPath = ":" + os.path.expanduser(TEMPDIR)

        jobid = s.runJob(jt)

        # set job fields that depend on the jobid assigned by grid engine
        job.jobid = jobid
        job.log_stdout_fn = (os.path.expanduser(TEMPDIR) + job.name + '.o' + jobid)
        job.log_stderr_fn = (os.path.expanduser(TEMPDIR) + job.name + '.e' + jobid)

        print 'Your job %s has been submitted with id %s' % (job.name, jobid)
        print "stdout:", job.log_stdout_fn
        print "stderr:", job.log_stderr_fn
        print ""

        #display tmp file size
        # print os.system("du -h " + invars)

        jobids.append(jobid)
        s.deleteJobTemplate(jt)

        # finally save job object to file system
        save(job.inputfile, job)

    sid = s.contact
    s.exit()

    return (sid, jobids)


def collect_jobs(sid, jobids, joblist, wait=False):
    """
    Collect the results from the jobids, returns a list of Jobs

    @param sid: session identifier
    @type sid: string returned by cluster
    @param jobids: list of job identifiers returned by the cluster
    @type jobids: list of strings
    @param wait: Wait for jobs to finish?
    @type wait: Boolean, defaults to False
    """

    for ix in xrange(len(jobids)):
        assert(jobids[ix] == joblist[ix].jobid)

    s = drmaa.Session()
    s.initialize(sid)

    if wait:
        drmaaWait = drmaa.Session.TIMEOUT_WAIT_FOREVER
    else:
        drmaaWait = drmaa.Session.TIMEOUT_NO_WAIT

    s.synchronize(jobids, drmaaWait, True)
    print "success: all jobs finished"
    s.exit()

    #attempt to collect results
    retJobs = []
    for ix, job in enumerate(joblist):
        
        log_stdout_fn = (os.path.expanduser(TEMPDIR) + job.name + '.o' + jobids[ix])
        log_stderr_fn = (os.path.expanduser(TEMPDIR) + job.name + '.e' + jobids[ix])
        
        try:
            retJob = load(job.outputfile)
            assert(retJob.name == job.name)
            retJobs.append(retJob)

            #print exceptions
            if retJob.exception != None:
                print str(type(retJob.exception))
                print "Exception encountered in job with log file:"
                print log_stdout_fn
                print retJob.exception

            #remove files
            elif retJob.cleanup:

                print "cleaning up:", job.outputfile
                os.remove(job.outputfile)

                if retJob != None:

                    print "cleaning up:", log_stdout_fn
                    os.remove(log_stdout_fn)

                    print "cleaning up:", log_stderr_fn
                    #os.remove(log_stderr_fn)


        except Exception, detail:
            print "error while unpickling file: " + job.outputfile
            print "this could caused by a problem with the cluster environment, imports or environment variables"
            print "check log files for more information: "
            print "stdout:", log_stdout_fn
            print "stderr:", log_stderr_fn
            
            print detail



    return retJobs


def process_jobs(jobs, local=False, maxNumThreads=1):
    """
    Director function to decide whether to run on the cluster or locally
    """
    
    if (not local and drmaa_present):
        # Use submit_jobs and collect_jobs to run jobs and wait for the results.
        # jobid field is attached to each job object
        (sid, jobids) = submit_jobs(jobs)

        print 'checking whether finished'

        checker = StatusChecker(sid, jobs)
        while not checker.check():
            time.sleep(5)
        return collect_jobs(sid, jobids, jobs, wait=True)

    elif (not local and not drmaa_present):
        print 'Warning: import drmaa failed, computing locally'
        return  _process_jobs_locally(jobs, maxNumThreads=maxNumThreads)

    else:
        return  _process_jobs_locally(jobs, maxNumThreads=maxNumThreads)



def get_status(sid, jobids):
    """
    Get the status of all jobs in jobids.
    Returns True if all jobs are finished.

    Using the state-aware StatusChecker now, this
    function maintains the previous
    interface.
    """

    checker = StatusChecker(sid, jobids)
    return checker.check()



class StatusChecker(object):
    """
    To deal with the fact that grid engine seems
    to forget about finished jobs after a little while,
    we need to keep track of finished jobs manually
    and count a out-of-synch job as finished, if it has
    previously had the status "finished"
    """ 

    def __init__(self, sid, jobs):
        """
        we keep a memory of job ids
        """
        
        self.jobs = jobs
        self.jobids = [job.jobid for job in jobs]
        self.sid = sid
        self.jobid_to_status = {}.fromkeys(self.jobids, 0)

        self._decodestatus = {
            -42: 'sge and drmaa not in sync',
            "undetermined": 'process status cannot be determined',
            "queued_active": 'job is queued and active',
            "system_on_hold": 'job is queued and in system hold',
            "user_on_hold": 'job is queued and in user hold',
            "user_system_on_hold": 'job is in user and system hold',
            "running": 'job is running',
            "system_suspended": 'job is system suspended',
            "user_suspended": 'job is user suspended',
            "done": 'job finished normally',
            "failed": 'job finished, but failed',
        }
            

    def check(self):
        """
        Get the status of all jobs.
        Returns True if all jobs are finished.
        """
                
        s = drmaa.Session()
        s.initialize(self.sid)

        status_summary = {}.fromkeys(self._decodestatus, 0)
        status_changed = False

        for job in self.jobs:

            jobid = job.jobid
            old_status = self.jobid_to_status[jobid]
            
            try:
                curstat = s.jobStatus(jobid)

            except Exception, message:
                # handle case where already finished job
                # is now out-of-synch with grid engine
                if old_status == "done":
                    curstat = "done"
                else:
                    curstat = -42

                    # check if output file is empty, if yes output job.args
                    if os.path.exists(job.log_stdout_fn) and os.path.isfile(job.log_stdout_fn):
                        tmp_file = file(job.log_stdout_fn)
                        if tmp_file.read() == "":
                            print "serious error [empty log] encountered for job", jobid, ", arguments:", job.args, "on", job.node_name
                        tmp_file.close()

            # print job status updates
            if curstat != old_status:

                # set flag
                status_changed = True

                # parse qstat output for node name
                command = "qstat | grep %s" % (jobid)
                process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
                os.waitpid(process.pid, 0)
                output = process.stdout.read().strip()
                at_pos = output.find("@")

                if at_pos == -1:
                    node_name = "unscheduled"
                else:
                    node_name = output[at_pos+1:at_pos+10]
                
                # save node name
                job.node_name = node_name

                print "status update for job", jobid, "from", old_status, "to", curstat, "log at", job.log_stdout_fn, "on", node_name

            # remember current status
            self.jobid_to_status[jobid] = curstat
            status_summary[curstat] += 1


        # print status summary
        if status_changed:
            print 'Status of %s at %s' % (self.sid, time.strftime('%d/%m/%Y - %H.%M:%S'))
            for curkey in status_summary.keys():
                if status_summary[curkey]>0:
                    print '%s: %d' % (self._decodestatus[curkey], status_summary[curkey])
            print "##############################################"
            status_changed = False

        s.exit()

        return (status_summary["done"] + status_summary[-42]==len(self.jobs))
                

#####################################################################
# MapReduce Interface
#####################################################################



def map(f, input_list, param=None, local=False, maxNumThreads=1, mem="5G"):
    """
    provides a generic map function
    """

    jobs=[]

    # construct jobs
    for input in input_list:
        job = KybJob(f, [input], param=param)
        job.key = input
        job.h_vmem = mem

        jobs.append(job)
        

    # process jobs
    processed_jobs = process_jobs(jobs, local=local, maxNumThreads=maxNumThreads)


    # store results
    results = {}
    for job in processed_jobs:
        results[job.key] = job.ret
    
    return results



class MapReduce(object):
    """
    convenient high-level API for map-reduce interface
    """

    def __init__(self, fun_map, fun_reduce, input_list, param=None, name=None):
        """
        combines all that is needed for map-reduce
        """

        self.fun_map = fun_map
        self.fun_reduce = fun_reduce
        self.input_list = input_list
        self.param = param
        self.name = name

    def wait(self, local=True, max_num_threads=1):
        """
        wait for jobs to finish
        """

        intermediate_results = map(self.fun_map, self.input_list, self.param, local, max_num_threads)

        # apply user-defined reduce function to intermediate result
        result = self.fun_reduce(intermediate_results)

        return result


#####################################################################
# Data persistence
#####################################################################


def save(filename, myobj):
    """
    Save myobj to filename using pickle
    """
    try:
        f = bz2.BZ2File(filename, 'wb')
    except IOError, details:
        sys.stderr.write('File ' + filename + ' cannot be written\n')
        sys.stderr.write(details)
        return

    cPickle.dump(myobj, f, protocol=2)
    f.close()


def load(filename):
    """
    Load from filename using pickle
    """
    try:
        f = bz2.BZ2File(filename, 'rb')
    except IOError, details:
        sys.stderr.write('File ' + filename + ' cannot be read\n')
        sys.stderr.write(details)
        return

    myobj = cPickle.load(f)
    f.close()
    return myobj


################################################################
#      The following code will be executed on the cluster      #
################################################################


def run_job(pickleFileName):
    """
    This is the code that is executed on the cluster side.
    Runs job which was pickled to a file called pickledFileName.

    @param pickleFileName: filename of pickled Job object
    @type pickleFileName: string
    """


    inPath = pickleFileName
    job = load(inPath)

    job.execute()

    #remove input file
    if job.cleanup:
        os.remove(job.inputfile)

    save(job.outputfile, job)


class Usage(Exception):
    """
    Simple Exception for cmd-line user-interface.
    """

    def __init__(self, msg):
        """
        Constructor of simple Exception.

        @param msg: exception message
        @type msg: string
        """

        self.msg = msg


def main(argv=None):
    """
    Parse the command line inputs and call run_job

    @param argv: list of arguments
    @type argv: list of strings
    """


    if argv is None:
        argv = sys.argv

    try:
        try:
            opts, args = getopt.getopt(argv[1:], "h", ["help"])
            run_job(args[0])
        except getopt.error, msg:
            raise Usage(msg)


    except Usage, err:
        print >>sys.stderr, err.msg
        print >>sys.stderr, "for help use --help"

        return 2

if __name__ == "__main__":
    main(sys.argv)
