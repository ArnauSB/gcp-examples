#!/bin/bash
# Generates a self-signed Root CA and a Server Certificate signed by it.

SERVICE_HOST=$1

if [ -z "$SERVICE_HOST" ]; then
    echo "ERROR: Please provide the hostname or Kubernetes service name (FQDN) as the first argument."
    echo "Example: ./ssl_setup.sh my-secure-service.default.svc.cluster.local"
    exit 1
fi

echo "--- 1. Creating Root CA ---"
openssl genrsa -out ca.key 2048
openssl req -new -x509 -key ca.key -out ca.crt -days 365 -subj "/CN=Arnau Test CA/O=Immune Institute Test/C=ES"

echo "--- 2. Creating Server Key and CSR ---"
openssl genrsa -out server.key 2048

cat > server.csr.conf <<-EOF
[ req ]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn

[ dn ]
C = ES
O = LoadGen Test
CN = ${SERVICE_HOST}

[ san ]
subjectAltName = DNS:${SERVICE_HOST}
EOF

openssl req -new -key server.key -out server.csr -config server.csr.conf

echo "--- 3. Signing Server Certificate ---"
EXT_CONFIG=$(mktemp)
cat > "$EXT_CONFIG" <<-EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:${SERVICE_HOST}
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 -sha256 \
    -extfile "$EXT_CONFIG"

echo "--- Setup Complete ---"
echo "Certificate CN/SAN set for: ${SERVICE_HOST}"
echo "Files created: ca.crt, ca.key, server.crt, server.key"

# Clean up temporary files
rm "$EXT_CONFIG"
rm server.csr server.csr.conf v3.ext
