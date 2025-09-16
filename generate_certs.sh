#!/bin/bash

# Certificate generation script for mTLS setup
# This script creates a Certificate Authority (CA) and generates
# server and client certificates for mutual TLS authentication

set -e

CERT_DIR="certs"
DAYS_VALID=365
KEY_SIZE=2048

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating SSL certificates for mTLS setup...${NC}"

# Create certs directory if it doesn't exist
mkdir -p $CERT_DIR

# Generate CA private key
echo -e "${YELLOW}Generating CA private key...${NC}"
openssl genrsa -out $CERT_DIR/ca.key $KEY_SIZE

# Generate CA certificate
echo -e "${YELLOW}Generating CA certificate...${NC}"
openssl req -new -x509 -key $CERT_DIR/ca.key -sha256 -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=WebhookAPI-CA" -days $DAYS_VALID -out $CERT_DIR/ca.crt

# Generate server private key
echo -e "${YELLOW}Generating server private key...${NC}"
openssl genrsa -out $CERT_DIR/server.key $KEY_SIZE

# Generate server certificate signing request
echo -e "${YELLOW}Generating server certificate signing request...${NC}"
openssl req -new -key $CERT_DIR/server.key -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=webhook-api.local" -out $CERT_DIR/server.csr

# Generate server certificate signed by CA
echo -e "${YELLOW}Generating server certificate...${NC}"
openssl x509 -req -in $CERT_DIR/server.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key -CAcreateserial -out $CERT_DIR/server.crt -days $DAYS_VALID -sha256

# Generate client private key
echo -e "${YELLOW}Generating client private key...${NC}"
openssl genrsa -out $CERT_DIR/client.key $KEY_SIZE

# Generate client certificate signing request
echo -e "${YELLOW}Generating client certificate signing request...${NC}"
openssl req -new -key $CERT_DIR/client.key -subj "/C=VN/ST=HCM/L=HCMC/O=BankClient/CN=bank-client" -out $CERT_DIR/client.csr

# Generate client certificate signed by CA
echo -e "${YELLOW}Generating client certificate...${NC}"
openssl x509 -req -in $CERT_DIR/client.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key -CAcreateserial -out $CERT_DIR/client.crt -days $DAYS_VALID -sha256

# Generate example bank public key for signature verification
echo -e "${YELLOW}Generating example bank public key for signature verification...${NC}"
openssl genrsa -out $CERT_DIR/bank_private.key 2048
openssl rsa -in $CERT_DIR/bank_private.key -pubout -out $CERT_DIR/bank_public.pem

# Set proper permissions
chmod 600 $CERT_DIR/*.key
chmod 644 $CERT_DIR/*.crt $CERT_DIR/*.pem

# Clean up CSR files
rm -f $CERT_DIR/*.csr

echo -e "${GREEN}Certificate generation completed!${NC}"
echo ""
echo -e "${YELLOW}Generated files:${NC}"
echo -e "  CA Certificate: $CERT_DIR/ca.crt"
echo -e "  CA Private Key: $CERT_DIR/ca.key"
echo -e "  Server Certificate: $CERT_DIR/server.crt"
echo -e "  Server Private Key: $CERT_DIR/server.key"
echo -e "  Client Certificate: $CERT_DIR/client.crt"
echo -e "  Client Private Key: $CERT_DIR/client.key"
echo -e "  Bank Public Key: $CERT_DIR/bank_public.pem"
echo -e "  Bank Private Key: $CERT_DIR/bank_private.key"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Copy the CA certificate (ca.crt) to clients that need to verify the server"
echo -e "2. Configure clients to use client certificates for mTLS authentication"
echo -e "3. The bank should provide their actual public key for signature verification"
echo -e "4. Update the .env file with the correct certificate paths"
echo ""
echo -e "${RED}WARNING: These are self-signed certificates for development/testing only!${NC}"
echo -e "${RED}For production, use certificates from a trusted Certificate Authority.${NC}"