INGInious
=========

This container is part of [INGInious](https://github.com/INGInious/INGInious), an intelligent grader that allows secured and automated testing of code made by students. 

Base container (ingi/inginious-c-base)
--------------------------------------

The base container image.

Contains basic INGInious commands, that are needed in order to grade tasks in INGInious.

All container images written for INGInious should inherit from this container image.

This container is not able to grade anything, as it lacks a name label. 
See documentation, or ingi/inginious-c-default, for an example.
