# Deploy Go web app

This document explains how to create a web service using Nginx and Go to host it in Google Compute Engine.

## Prerequisites

- Update the SO
- Install Go 1.21
- Install Nginx

```bash
sudo apt update && sudo apt upgrade -y
wget https://go.dev/dl/go1.21.11.linux-amd64.tar.gz && sudo tar -C /usr/local -xzf go1.21.11.linux-amd64.tar.gz
sudo apt-get install nginx -y
```

Verify that Go works:

```bash
go version
```

## Configure the web server

We only want Nginx to work as a proxy for our application, so we will disable the default server page, and create a new one. 
For this, we will modify `/etc/nginx/sites-available/default` and add the following:

```bash
server {
    listen 80;
    server_name "";
    access_log /var/log/nginx/webapp.access.log;
    location / {
        proxy_pass http://127.0.0.1:8080;
    }       
}
```

Enable the site configuration by creating a symlink to it in `sites-enabled`, and telling Nginx to reload:

```bash
cd /etc/nginx/sites-enabled
sudo ln -s ../sites-available/default
sudo /etc/init.d/nginx reload
```

Now the Nginx proxy is created but nothing is listening on `http://127.0.0.1:8080`. Upload `webserver.go` to the VM and run the Go web server:

```bash
cd ~/
export PATH=$PATH:/usr/local/go/bin
go run webserver.go -http=127.0.0.1:8080
```

Now the server should be available and working.

## Automate startup

We’ve now accomplished what we set out to do. But what if the machine restarts? We need to configure the system to run the goto process on start-up.
Firt let's build the server and move it to a shared directory:

```bash
go build webserver.go
sudo mv webserver /usr/sbin/webserver
sudo chown root:root /usr/sbin/webserver
```

Now let's create a basic `init.d` script in `/etc/init.d/webserver`:

```bash
#!/bin/bash

NAME="webserver"
GO_BINARY_PATH="/usr/sbin/webserver"
PIDFILE="/var/run/webserver.pid"

start() {
  "$GO_BINARY_PATH"
}

stop() {
  pkill -f "^$GO_BINARY_PATH" -TERM
  sleep 10
  pkill -f "^$GO_BINARY_PATH" -KILL
}

case "$1" in
  start)
    echo -n "Starting $NAME server: "
    start-stop-daemon --start --make-pidfile --background --pidfile $PIDFILE --exec $GO_BINARY_PATH
    echo "started."
    ;;
  stop)
    echo -n "Stopping $NAME server: "
    start-stop-daemon --stop --quiet --pidfile $PIDFILE --exec $GO_BINARY_PATH
    rm -f $PIDFILE
    echo "stopped."
    ;;
  restart)
    echo -n "Restarting $NAME server: "
    stop
    start
    echo "restarted."
    ;;
  *)
    echo "Usage: $0 {start|stop|restart}"
    exit 1
    ;;
esac

exit 0
```

Now we can execute it:

```bash
sudo chmod +x /etc/init.d/webserver
sudo /etc/init.d/webserver start
```

And last add the service to `rc.d` so that it is launched on start-up:

```bash
sudo update-rc.d webserver defaults
```

Verify the link has been created, otherwise create it:

```bash
sudo ls -l /etc/rc[0-6].d/S*webserver
sudo ln -s /etc/init.d/webserver /etc/rc2.d/S02webserver
```

And that’s it. There is more you could do, but these are the bare essentials to reliably run a Go (or any other) web service behind Nginx under Debian.
