# Scripts

Use the helper scripts in this folder to run and stop the app locally.

- start.sh / start.ps1: build the Docker image and start the container
- stop.sh / stop.ps1: stop the running container

The app is served at http://localhost:8000 and is only reachable from this machine.

Board data is kept in the Docker volume `pm-mvp-data`, so it survives stop and start. To reset it, stop the app and run `docker volume rm pm-mvp-data`.
