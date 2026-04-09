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
export PATH=$PATH:/usr/local/go/bin
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
PORT=8080 go run webserver.go
```

Now the server should be available and working.

### Available endpoints

| Path | Description |
|------|-------------|
| `/` | Hostname, remote addr, user-agent, and GCP env vars (`PROJECT_ID`, `ZONE`, `INSTANCE_ID`) |
| `/headers` | All request headers as JSON |
| `/env` | All environment variables as JSON |
| `/info` | Live GCP instance metadata (hostname, zone, machine-type, id) |
| `/healthz` | Health check — returns `{"status":"ok"}` |

Logs are emitted as structured JSON to stdout, compatible with Google Cloud Logging.

## Automate startup

We’ve now accomplished what we set out to do. But what if the machine restarts? We need to configure the system to run the Go process on start-up.
First let’s build the server and move it to a shared directory:

```bash
go build webserver.go
sudo mv webserver /usr/sbin/webserver
sudo chown root:root /usr/sbin/webserver
```

Create a systemd unit file at `/etc/systemd/system/webserver.service`:

```ini
[Unit]
Description=Go Web Server
After=network.target

[Service]
ExecStart=/usr/sbin/webserver
Restart=always
RestartSec=5
User=www-data
Environment=PORT=8080
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Reload systemd, enable the service to start on boot, and start it now:

```bash
sudo systemctl daemon-reload
sudo systemctl enable webserver
sudo systemctl start webserver
```

Check the service status and logs:

```bash
sudo systemctl status webserver
sudo journalctl -u webserver -f
```

And that’s it. systemd handles restarts automatically and integrates with `journald` for log collection.
