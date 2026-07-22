# coding=utf-8
""" Allow to resolve shells from file extension. """

run_types = {
    "py": ["/bin/inginious-ipython"],
    "py3": ["/bin/inginious-ipython"],
    "sh": ["/bin/bash"]
}

# Add here lines in the form
# run_types["cs"] = "/bin/mono"
# to add new types in your new container. To do that, you can simply put this inside your Dockerfile:
# RUN echo 'run_types["cs"] = "/bin/mono"' >> /usr/lib/python3.5/site-packages/inginious_container_api/run_types.py
