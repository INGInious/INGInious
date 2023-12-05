# Setup

## Installation

There are three main ways to install INGInious:

- [Using pre-build containers and a Compose file](#containerized-deployement-with-pre-build-images)
- [Locally build containers and a Compose file](#containerized-deployment-with-locally-build-images)
- [Bare metal, manual installation](#manual-installation)

### Containerized deployement with pre-build images

!!! tip

    [Docker](https://docs.docker.com/engine/install/) and [Docker Compose](https://docs.docker.com/compose/install/) are pre-requisite for this type of installation.

!!! info

    While [Docker](https://www.docker.com/) is mainly used in INGInious deployements, other containers engines such as [Podman](https://podman.io/) should also work.
    If you are experimenting with another container engine, [your feedback is welcome](https://github.com/UCL-INGI/INGInious/discussions).

1. Create a folder in your home directory to place your courses and exercices.
  ```console
  mkdir -p inginious/{tasks,backups}
  ```
2. Get the [Compose file](https://github.com/UCL-INGI/INGInious/blob/docker-compose.yml) from the project page.
  ```console
  wget https://github.com/UCL-INGI/INGInious/blob/docker-compose.yml
  ```

  OR

  Copy and paste the following snippet in a file called `docker-compose.yml`.

  ```yaml
  services:

    base:
      image: ${REGISTRY}/inginious/core-base:${VERSION} # (1)
      build:
        dockerfile: deploy/inginious-base.containerfile
        args:
          - VERSION=${VERSION}
          - REGISTRY=${REGISTRY}
      command: /bin/true # (2)

    db:
      image: mongo:6.0.2
      networks:
        - inginious

    backend:
      image: ${REGISTRY}/inginious/core-backend:${VERSION}
      depends_on:
        - base
      build:
        dockerfile: deploy/backend.containerfile
        args:
          - VERSION=${VERSION}
          - REGISTRY=${REGISTRY}
      environment:
        AGENT: "tcp://0.0.0.0:2001" # (3)
        CLIENT: "tcp://0.0.0.0:2000" # (4)
      networks:
        - inginious

    agent-docker:
      image: ${REGISTRY}/inginious/core-agent_docker:${VERSION}
      depends_on:
        - backend
      deploy:
        replicas: 1 # (5)
      build:
        dockerfile: deploy/agent-docker.containerfile
        args:
          - VERSION=${VERSION}
          - REGISTRY=${REGISTRY}
      environment:
        BACKEND: "tcp://backend:2001" # (6)
      volumes: # (7)
       - /var/run/docker.sock:/var/run/docker.sock
       # See https://github.com/UCL-INGI/INGInious/issues/352
       - ./tasks/:/inginious/tasks
       - ./backups/:/inginious/backups
       # See https://github.com/UCL-INGI/INGInious/issues/799
       - /tmp/agent_data/:/tmp/agent_data/
      networks:
        - inginious

    agent-mcq:
      image: ${REGISTRY}/inginious/core-agent_mcq:${VERSION}
      depends_on:
        - backend
      deploy:
        replicas: 1 # (5)
      build:
        dockerfile: deploy/agent-mcq.containerfile
        args:
          - VERSION=${VERSION}
          - REGISTRY=${REGISTRY}
      environment:
        BACKEND: "tcp://backend:2001" # (6)
      volumes: # (7)
       # See https://github.com/UCL-INGI/INGInious/issues/352
       - ./tasks/:/inginious/tasks
       - ./backups/:/inginious/backups
       # See https://github.com/UCL-INGI/INGInious/issues/799
       - /tmp/agent_data/:/tmp/agent_data/
      networks:
        - inginious

    frontend:
      image: ${REGISTRY}/inginious/core-frontend:${VERSION}
      build:
        dockerfile: deploy/frontend.containerfile
        args:
          - VERSION=${VERSION}
          - REGISTRY=${REGISTRY}
      depends_on:
        - backend
        - agent-docker
        - agent-mcq
      environment:
        - INGINIOUS_WEBAPP_HOST=0.0.0.0
      volumes: # (7)
        - ./configuration.deploy.yaml:/inginious/configuration.yaml
        - ./tasks/:/inginious/tasks
        - ./backups/:/inginious/backups
      ports:
        - 9000:8080
      networks:
        - inginious

  networks:
    inginious:
  ```

  1. `REGISTRY` and `VERSION` variables control the source and the version of the core services
      of INGInious. They must be specified when the stack is built or deployed.
  2. Quick hack to force the build of the base core container before building the service containers.
  3. Address and port on which the backend will listen for [`Agents`]().
  4. Address and port on which the backend will listen for [`Clients`]().
  5. By tuning this parameter, one can deploy multiples [`Agents`]() in the same stack.
  6. Specify in the `BACKEND` variable the address of the backend listening for [`Agents`]().
  7. Update this volume according to your own deployement paths.

### Containerized deployement with locally build images

### Manual installation
