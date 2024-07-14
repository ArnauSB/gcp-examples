# Cloud SQL

To deploy a To Do simple app which will use PostgreSQL, we need to create a Cloud SQL instance with private IP, Private Services Access and private path enabled. Then enable the SQL Admin API and create the data base:

```bash
gcloud sql databases create todo --instance ${CloudSQL-instance}
gcloud services enable sqladmin.googleapis.com
```

Once we have the Cloud SQL instance created, copy the "Instance connection name". Now we need to create a GCE instance in the same VPC and region, with access to the Cloud SQL API in the scopes. Then we need to install the following:

```bash
sudo apt update && sudo apt upgrade -y
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.9.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy 
./cloud-sql-proxy --private-ip <Instance-connection-name> &
```

Above commands will download and execute the Cloud SQL proxy to be able to connect with the Cloud SQL instance. Now, let's download the packages to install the web server to host the To Do app and psql:

```bash
sudo apt install postgresql-client-15 python3 python3-pip python3-flask python3-psycopg2
```

Now we have to connect from the GCE instance to the Cloud SQL instance using `psql` and create a table called `tasks` with the following values:

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d todo
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL
);
```

Once this is done, leave from `psql` and create a folder called `app` and another folder inside `app` called `templates` where you will need to copy the files `main.py` and `index.html`. Change the variables to connect with your DB from `main.py`. Once this is done, you can run `main.py`:

```bash
mkdir app
mkdir app/templates/
mv index.html app/templates/
mv main.py app/
cd app/
sudo python3 main.py &
```

Now you can connect to the public IP of the GCE instance and interact with the To Do app.
