import urllib
import traceback

import classad
import htcondor

import HTCondorLocator
import HTCondorUtils

from ServerUtilities import FEEDBACKMAIL
import TaskWorker.Actions.TaskAction as TaskAction
from TaskWorker.WorkerExceptions import TaskWorkerException

from httplib import HTTPException

class DagmanResubmitter(TaskAction.TaskAction):
    """
    Given a task name, resubmit failed tasks.

    Internally, we simply release the failed DAG.
    """

    def executeInternal(self, *args, **kwargs):
        #Marco: I guess these value errors only happens for development instances
        if 'task' not in kwargs:
            raise ValueError("No task specified.")
        task = kwargs['task']
        if 'tm_taskname' not in task:
            raise ValueError("No taskname specified.")
        workflow = str(task['tm_taskname'])
        if 'user_proxy' not in task:
            raise ValueError("No proxy provided")
        proxy = task['user_proxy']

        self.logger.info("About to resubmit workflow: %s." % workflow)
        self.logger.info("Task info: %s" % str(task))

        if task['tm_collector']:
            self.backendurls['htcondorPool'] = task['tm_collector']
        loc = HTCondorLocator.HTCondorLocator(self.backendurls)

        schedd = ""
        address = ""
        try:
            schedd, address = loc.getScheddObjNew(task['tm_schedd'])
        except Exception as exp:
            msg  = "The CRAB server backend was not able to contact the Grid scheduler."
            msg += " Please try again later."
            msg += " If the error persists send an e-mail to %s." % (FEEDBACKMAIL)
            msg += " Message from the scheduler: %s" % (str(exp))
            self.logger.exception("%s: %s" % (workflow, msg))
            raise TaskWorkerException(msg)

        # Check memory and walltime
        stdmaxjobruntime = 2800
        stdmaxmemory = 2500
        if task['resubmit_maxjobruntime'] is not None and task['resubmit_maxjobruntime'] > stdmaxjobruntime:
            msg  = "Task requests %s minutes of walltime, but only %s are guaranteed to be available." % (task['resubmit_maxjobruntime'], stdmaxjobruntime)
            msg += " Jobs may not find a site where to run."
            msg += " CRAB has changed this value to %s minutes." % (stdmaxjobruntime)
            self.logger.warning(msg)
            task['resubmit_maxjobruntime'] = str(stdmaxjobruntime)
            self.uploadWarning(msg, kwargs['task']['user_proxy'], kwargs['task']['tm_taskname'])
        if task['resubmit_maxmemory'] is not None and task['resubmit_maxmemory'] > stdmaxmemory:
            msg  = "Task requests %s bytes of memory, but only %s are guaranteed to be available." % (task['resubmit_maxmemory'], stdmaxmemory)
            msg += " Jobs may not find a site where to run and stay idle forever."
            self.logger.warning(msg)
            self.uploadWarning(msg, kwargs['task']['user_proxy'], kwargs['task']['tm_taskname'])

        # Release the DAG
        rootConst = "TaskType =?= \"ROOT\" && CRAB_ReqName =?= %s" % HTCondorUtils.quote(workflow)

        ## Calculate new parameters for resubmited jobs. These parameters will
        ## be (re)written in the _CONDOR_JOB_AD when we do schedd.edit() below.
        ad = classad.ClassAd()
        params = {'CRAB_ResubmitList'  : 'jobids',
                  'CRAB_SiteBlacklist' : 'site_blacklist',
                  'CRAB_SiteWhitelist' : 'site_whitelist',
                  'MaxWallTimeMins'    : 'maxjobruntime',
                  'RequestMemory'      : 'maxmemory',
                  'RequestCpus'        : 'numcores',
                  'JobPrio'            : 'priority'
                 }
        overwrite = False
        for taskparam in params.values():
            if ('resubmit_'+taskparam in task) and task['resubmit_'+taskparam] != None:
                if isinstance(task['resubmit_'+taskparam], list):
                    ad[taskparam] = task['resubmit_'+taskparam]
                if taskparam != 'jobids':
                    overwrite = True

        if ('resubmit_jobids' in task) and task['resubmit_jobids']:
            with HTCondorUtils.AuthenticatedSubprocess(proxy) as (parent, rpipe):
                if not parent:
                    schedd.edit(rootConst, "HoldKillSig", 'SIGKILL')
                    ## Overwrite parameters in the os.environ[_CONDOR_JOB_AD] file. This will affect
                    ## all the jobs, not only the ones we want to resubmit. That's why the pre-job
                    ## is saving the values of the parameters for each job retry in text files (the
                    ## files are in the directory resubmit_info in the schedd).
                    for adparam, taskparam in params.iteritems():
                        if taskparam in ad:
                            schedd.edit(rootConst, adparam, ad[taskparam])
                        elif task['resubmit_'+taskparam] != None:
                            schedd.edit(rootConst, adparam, str(task['resubmit_'+taskparam]))
                    schedd.act(htcondor.JobAction.Hold, rootConst)
                    schedd.edit(rootConst, "HoldKillSig", 'SIGUSR1')
                    schedd.act(htcondor.JobAction.Release, rootConst)
        elif overwrite:
            with HTCondorUtils.AuthenticatedSubprocess(proxy) as (parent, rpipe):
                if not parent:
                    self.logger.debug("Resubmitting under condition overwrite = True")
                    for adparam, taskparam in params.iteritems():
                        if taskparam in ad:
                            if taskparam == 'jobids' and len(list(ad[taskparam])) == 0:
                                self.logger.debug("Setting %s = True in the task ad." % (adparam))
                                schedd.edit(rootConst, adparam, classad.ExprTree("true"))
                            else:
                                schedd.edit(rootConst, adparam, ad[taskparam])
                        elif task['resubmit_'+taskparam] != None:
                            schedd.edit(rootConst, adparam, str(task['resubmit_'+taskparam]))
                    schedd.act(htcondor.JobAction.Release, rootConst)
        else:
            ## This should actually not occur anymore in CRAB 3.3.16 or above, because
            ## starting from CRAB 3.3.16 the resubmission parameters are written to the
            ## Task DB with value != None, so the overwrite variable should never be False.
            with HTCondorUtils.AuthenticatedSubprocess(proxy) as (parent, rpipe):
                if not parent:
                    self.logger.debug("Resubmitting under condition overwrite = False")
                    schedd.edit(rootConst, "HoldKillSig", 'SIGKILL')
                    schedd.edit(rootConst, "CRAB_ResubmitList", classad.ExprTree("true"))
                    schedd.act(htcondor.JobAction.Hold, rootConst)
                    schedd.edit(rootConst, "HoldKillSig", 'SIGUSR1')
                    schedd.act(htcondor.JobAction.Release, rootConst)

        results = rpipe.read()
        if results != "OK":
            msg  = "The CRAB server backend was not able to resubmit the task,"
            msg += " because the Grid scheduler answered with an error."
            msg += " This is probably a temporary glitch. Please try again later."
            msg += " If the error persists send an e-mail to %s." % (FEEDBACKMAIL)
            msg += " Error reason: %s" % (results)
            raise TaskWorkerException(msg)


    def execute(self, *args, **kwargs):
        """
        The execute method of the DagmanResubmitter class.
        """
        self.executeInternal(*args, **kwargs)
        try:
            configreq = {'subresource': 'state',
                         'workflow': kwargs['task']['tm_taskname'],
                         'status': 'SUBMITTED'}
            self.logger.debug("Setting the task as successfully resubmitted with %s" % (str(configreq)))
            self.server.post(self.resturi, data = urllib.urlencode(configreq))
        except HTTPException as hte:
            self.logger.error(hte.headers)
            msg  = "The CRAB server successfully resubmitted the task to the Grid scheduler,"
            msg += " but was unable to update the task status to %s in the database." % (configreq['status'])
            msg += " This should be a harmless (temporary) error."
            raise TaskWorkerException(msg)


if __name__ == "__main__":
    import os
    import logging
    from RESTInteractions import HTTPRequests
    from WMCore.Configuration import Configuration

    logging.basicConfig(level = logging.DEBUG)
    config = Configuration()

    config.section_("TaskWorker")
    #will use X509_USER_PROXY var for this test
    config.TaskWorker.cmscert = os.environ["X509_USER_PROXY"]
    config.TaskWorker.cmskey = os.environ["X509_USER_PROXY"]

    server = HTTPRequests('vmatanasi2.cern.ch', config.TaskWorker.cmscert, config.TaskWorker.cmskey)
    resubmitter = DagmanResubmitter(config, server, '/crabserver/dev/workflowdb')
    resubmitter.execute(task={'tm_taskname':'141129_110306_crab3test-5:atanasi_crab_test_resubmit', 'user_proxy' : os.environ["X509_USER_PROXY"],
                              'resubmit_site_whitelist' : ['T2_IT_Bari'], 'resubmit_site_blacklist' : ['T2_IT_Legnaro'], 'resubmit_priority' : 2,
                              'resubmit_numcores' : 1, 'resubmit_maxjobruntime' : 1000, 'resubmit_maxmemory' : 1000
                             })
