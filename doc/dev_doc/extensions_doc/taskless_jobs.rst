Taskless jobs
=======

INGInious can handle taskless jobs. That means jobs that are not linked to a task or course.
They can be used to run background jobs without needing to create a course.
You can run a taskless job by using the `new_job()` methode from the `Client` or `ClientSync` class, depending on if you
want to run the job asynchronously or synchronously (see :ref:`inginious.client.client` and :ref:`inginious.client.client_sync`
for usage). You can create and provide any environment based on the base environment.


Please be advised : The `/task` and `/course/common` paths are mounted during the container's creation. Therefore, any
runfile or ressource you put in these paths in your job's Docker image won't be accessible.