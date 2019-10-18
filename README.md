# What is kpov\_judge
    
kpov\_judge is a system for the automated grading of assignments for
networking and system administration courses.

Each assignment is represented by a task which a student should perform.
Tasks are customised for each student by setting a number of parameters
for each task.

Typically, each task involves a number of interconnected computers, one 
of which contains the kpov\_judge testing program (test\_task.py). After
solving the task, a student runs the test\_task.py to check their solution.
The testing results are uploaded to a server for grading and feedback can
be provided immediately.

# Using kpov\_judge as a student

For each task, the student is supposed to set up some services or resources
on one or multiple computers. The services or resources are then checked to
see if the task has been performed successfully. The result of the test is 
reported back to the student.

The instructions for each task are included in the task itself. The
parameters for each task are either prepared for each student in advance or
generated the moment a student tries to check whether they have performed
the task successfully.

The computers for each task are typically set up by downloading a set of 
virtual disk images, creating a number of virtual machines using these 
disks and connecting these virtual machines using virtual or physical
networks. After the computers are set up, a student can set up the services
required by the instructions.

The checking is done by the program test\_task.py. This program can run in 
both an on-line mode where some of the testing is done by a remote server
or an off-line mode where all the testing is done locally. Since kpov\_judge
is expected to be mostly used by schools, usually the on-line mode will be
used by students for handing in graded assignments and for immediate 
feedback during practice.

# Using kpov\_judge as a teacher
   
Install kpov\_judge according to INSTALL.md. Read the "Preparing tasks" section
of this README. Contact the authors to gain access to an existing repository of
tasks or write your own.

# Preparing tasks

Within the kpov\_judge repository, tasks are stored under kpov\_judge/tasks.
New tasks should be added as sub-directories of tasks.

Each task is defined by a python file named task.py . The file task.py 
contains:
    - instructions - the task instructions in multiple languages,
    - computers - a dictionary describing the computers used for this task, 
    - networks - a dictionary describing the network links for this task, 
    - params\_meta - a dictionary with a description and other metadata for
        each parameter for this task
    - task(...) - a function for testing the student's solution of this task.
        All the arguments for this function should be described in
        params\_meta and should be public. This function is run by
        the student to test their task solution. The output of
        task(...) should be relatively hard to fake - for example,
        if the student had to set up the default route on one of
        the computers, this function could return a string
        containing the output of the 'netstat -r' command. The
        idea is to make it harder for the student to fake the
        correct output of task(...) than it would be to just
        solve the task.
    - task\_check(results, params) - check the output of task(...).
        The parameter results contains the return value of task(...).
        The parameter params contains a dictionary of values for each
        parameter used for this task
        This function is used for grading the task and should return
        a value between 0 and 10 with 0 representing the lowest and 10
        representing the highest number of points attainable for solving
        the task.
    - gen\_params(user\_id, params\_meta) - prepare all the parameters for 
        this task. For most tasks, most of the parameters will be randomly
        generated according to the metadata in params\_meta. A number of
        helper functions for generating the parameters are available in
        kpov\_util.py
    - prepare\_disks(templates, params) - prepare the disk images for this
        task. For some tasks it might be neccessarry to create or edit
        some files on the virtual disk images used by each student to set
        up the computers needed for this task. The parameter templates
        contains a dictionary of guestfs objects. Refer to the libguestfs
        documentation for more information.

Typically, a new task is created by the following steps:
    - prepare a (virtual) testing computer
    - checkout the kpov\_judge repository on the testing computer
    - create a copy of an existing task to use as reference
    - change the instructions in task.py
    - create the other computers and networks involved in this task
    - change the dictionaries computers and networks in task.py
    - change the params\_meta to correspond to the new instructions.
    - write a task(...) function which returns a simple string
    - write a task\_check function which simply prints out the parameter
        results
    - write a gen\_params(user\_id, params\_meta) function
    - run test\_task -g to test gen\_params and set the initial task parameters
    - debug everything you have created so far by performing the task
        and running test\_task.py as many times as needed
    - write the task\_check and gen\_params functions
    - write the prepare\_disks function
    - commit the new task to the repository
    - checkout the task on the web-based evaluation system
    - upload the clean virtual disk images, add the task to the web-based
        system
    - log in as a student, download the images, solve task, run task\_check
    - debug the task if needed

For each course taught using kpov\_judge, a directory should be created
under kpov\_judge/courses. Each course's directory can be arranged in any
way the lecturer sees fit. For fri\_kpov, the directory contains one 
sub-directory for each lesson. Each lesson consists of a task the student
should perform before attending class (preparation), the instructions
for that week's class (lecture) and a task the student will be graded on
after the class (evaluation).

