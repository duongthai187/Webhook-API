# PowerShell certificate generation script for mTLS setup
# This script creates a Certificate Authority (CA) and generates
# server and client certificates for mutual TLS authentication

param(
    [int]$DaysValid = 365,
    [int]$KeySize = 2048,
    [string]$CertDir = "certs"
)

# Create certs directory if it doesn't exist
if (!(Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force
    Write-Host "Created directory: $CertDir" -ForegroundColor Green
}

Write-Host "Creating SSL certificates for mTLS setup..." -ForegroundColor Green

try {
    # Generate CA private key
    Write-Host "Generating CA private key..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/ca.key" $KeySize
    
    # Generate CA certificate
    Write-Host "Generating CA certificate..." -ForegroundColor Yellow
    & openssl req -new -x509 -key "$CertDir/ca.key" -sha256 -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=WebhookAPI-CA" -days $DaysValid -out "$CertDir/ca.crt"
    
    # Generate server private key
    Write-Host "Generating server private key..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/server.key" $KeySize
    
    # Generate server certificate signing request
    Write-Host "Generating server certificate signing request..." -ForegroundColor Yellow
    & openssl req -new -key "$CertDir/server.key" -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=webhook-api.local" -out "$CertDir/server.csr"
    
    # Generate server certificate signed by CA
    Write-Host "Generating server certificate..." -ForegroundColor Yellow
    & openssl x509 -req -in "$CertDir/server.csr" -CA "$CertDir/ca.crt" -CAkey "$CertDir/ca.key" -CAcreateserial -out "$CertDir/server.crt" -days $DaysValid -sha256
    
    # Generate client private key
    Write-Host "Generating client private key..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/client.key" $KeySize
    
    # Generate client certificate signing request
    Write-Host "Generating client certificate signing request..." -ForegroundColor Yellow
    & openssl req -new -key "$CertDir/client.key" -subj "/C=VN/ST=HCM/L=HCMC/O=BankClient/CN=bank-client" -out "$CertDir/client.csr"
    
    # Generate client certificate signed by CA
    Write-Host "Generating client certificate..." -ForegroundColor Yellow
    & openssl x509 -req -in "$CertDir/client.csr" -CA "$CertDir/ca.crt" -CAkey "$CertDir/ca.key" -CAcreateserial -out "$CertDir/client.crt" -days $DaysValid -sha256
    
    # Generate example bank public key for signature verification
    Write-Host "Generating example bank public key for signature verification..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/bank_private.key" 2048
    & openssl rsa -in "$CertDir/bank_private.key" -pubout -out "$CertDir/bank_public.pem"
    
    # Clean up CSR files
    Remove-Item "$CertDir/*.csr" -ErrorAction SilentlyContinue
    
    Write-Host "Certificate generation completed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Generated files:" -ForegroundColor Yellow
    Write-Host "  CA Certificate: $CertDir/ca.crt"
    Write-Host "  CA Private Key: $CertDir/ca.key"
    Write-Host "  Server Certificate: $CertDir/server.crt"
    Write-Host "  Server Private Key: $CertDir/server.key"
    Write-Host "  Client Certificate: $CertDir/client.crt"
    Write-Host "  Client Private Key: $CertDir/client.key"
    Write-Host "  Bank Public Key: $CertDir/bank_public.pem"
    Write-Host "  Bank Private Key: $CertDir/bank_private.key"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Copy the CA certificate (ca.crt) to clients that need to verify the server"
    Write-Host "2. Configure clients to use client certificates for mTLS authentication"
    Write-Host "3. The bank should provide their actual public key for signature verification"
    Write-Host "4. Update the .env file with the correct certificate paths"
    Write-Host ""
    Write-Host "WARNING: These are self-signed certificates for development/testing only!" -ForegroundColor Red
    Write-Host "For production, use certificates from a trusted Certificate Authority." -ForegroundColor Red
    
} catch {
    Write-Host "Error generating certificates: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure OpenSSL is installed and available in PATH" -ForegroundColor Red
    exit 1
}