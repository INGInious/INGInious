""" Compatibility layer to allow frontend to retain some informations about who created a job"""

import backend.job_manager
from frontend.login import loginInstance

userJobDict = {}

def addJob(task, inputdata):
    """ Add a job in the queue and returns a job id.
        task is a Task instance and inputdata is the input as a dictionary """
    if not loginInstance.isLoggedIn():
        raise Exception("A user must be logged in to submit an object")
    
    username = loginInstance.getUsername()
    if username not in userJobDict:
        userJobDict[username] = []
    
    jobId = backend.job_manager.addJob(task, inputdata)
    userJobDict[username].append(jobId)
    return jobId

def isRunning(jobId):
    """ Tells if a job given by job id is running/in queue """
    return userIsJobOwner(jobId) and backend.job_manager.isRunning(jobId)
    

def isDone(jobId):
    """ Tells if a job given y job id is done and its result is available """
    return userIsJobOwner(jobId) and backend.job_manager.isDone(jobId)
    
def getResult(jobId):
    """ Returns the result of a job given by a job id or None if the job is not finished/in queue. If the job is finished, subsequent call to getResult will return None (job is deleted) """
    if not userIsJobOwner(jobId):
        return None
    if not isDone(jobId):
        return None
    result = backend.job_manager.getResult(jobId)
    userJobDict[loginInstance.getUsername()].remove(jobId)
    return result
    
def userIsJobOwner(jobId):
    """ Returns true if the current user is the owner of this jobId, false else """
    if not loginInstance.isLoggedIn():
        raise Exception("A user must be logged in to verify if he owns a jobId")
    return loginInstance.getUsername() in userJobDict and jobId in userJobDict[loginInstance.getUsername()]