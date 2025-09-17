# Script PowerShell để tạo certificate cho cài đặt mTLS
# Script này tạo một Certificate Authority (CA) và sinh ra
# các certificate server và client cho xác thực mutual TLS

param(
    [int]$DaysValid = 365,
    [int]$KeySize = 2048,
    [string]$CertDir = "certs"
)

# Tạo thư mục certs nếu chưa tồn tại
if (!(Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force
    Write-Host "Đã tạo thư mục: $CertDir" -ForegroundColor Green
}

Write-Host "Đang tạo certificate SSL cho cài đặt mTLS..." -ForegroundColor Green

try {
    # Tạo private key cho CA
    Write-Host "Đang tạo private key cho CA..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/ca.key" $KeySize
    
    # Tạo certificate cho CA
    Write-Host "Đang tạo certificate cho CA..." -ForegroundColor Yellow
    & openssl req -new -x509 -key "$CertDir/ca.key" -sha256 -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=WebhookAPI-CA" -days $DaysValid -out "$CertDir/ca.crt"
    
    # Tạo private key cho server
    Write-Host "Đang tạo private key cho server..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/server.key" $KeySize
    
    # Tạo certificate signing request cho server
    Write-Host "Đang tạo certificate signing request cho server..." -ForegroundColor Yellow
    & openssl req -new -key "$CertDir/server.key" -subj "/C=VN/ST=HCM/L=HCMC/O=WebhookAPI/CN=webhook-api.local" -out "$CertDir/server.csr"
    
    # Tạo certificate server được ký bởi CA
    Write-Host "Đang tạo certificate cho server..." -ForegroundColor Yellow
    & openssl x509 -req -in "$CertDir/server.csr" -CA "$CertDir/ca.crt" -CAkey "$CertDir/ca.key" -CAcreateserial -out "$CertDir/server.crt" -days $DaysValid -sha256
    
    # Tạo private key cho client
    Write-Host "Đang tạo private key cho client..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/client.key" $KeySize
    
    # Tạo certificate signing request cho client
    Write-Host "Đang tạo certificate signing request cho client..." -ForegroundColor Yellow
    & openssl req -new -key "$CertDir/client.key" -subj "/C=VN/ST=HCM/L=HCMC/O=BankClient/CN=bank-client" -out "$CertDir/client.csr"
    
    # Tạo certificate client được ký bởi CA
    Write-Host "Đang tạo certificate cho client..." -ForegroundColor Yellow
    & openssl x509 -req -in "$CertDir/client.csr" -CA "$CertDir/ca.crt" -CAkey "$CertDir/ca.key" -CAcreateserial -out "$CertDir/client.crt" -days $DaysValid -sha256
    
    # Tạo public key mẫu của bank để xác minh chữ ký
    Write-Host "Đang tạo public key mẫu của bank để xác minh chữ ký..." -ForegroundColor Yellow
    & openssl genrsa -out "$CertDir/bank_private.key" 2048
    & openssl rsa -in "$CertDir/bank_private.key" -pubout -out "$CertDir/bank_public.pem"
    
    # Xóa các file CSR tạm thời
    Remove-Item "$CertDir/*.csr" -ErrorAction SilentlyContinue
    
    Write-Host "Tạo certificate hoàn tất!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Các file đã tạo:" -ForegroundColor Yellow
    Write-Host "  Certificate CA: $CertDir/ca.crt"
    Write-Host "  Private Key CA: $CertDir/ca.key"
    Write-Host "  Certificate Server: $CertDir/server.crt"
    Write-Host "  Private Key Server: $CertDir/server.key"
    Write-Host "  Certificate Client: $CertDir/client.crt"
    Write-Host "  Private Key Client: $CertDir/client.key"
    Write-Host "  Public Key Bank: $CertDir/bank_public.pem"
    Write-Host "  Private Key Bank: $CertDir/bank_private.key"
    Write-Host ""
    Write-Host "Các bước tiếp theo:" -ForegroundColor Yellow
    Write-Host "1. Sao chép certificate CA (ca.crt) cho các client cần xác minh server"
    Write-Host "2. Cấu hình client sử dụng certificate client cho xác thực mTLS"
    Write-Host "3. Bank cần cung cấp public key thật để xác minh chữ ký"
    Write-Host "4. Cập nhật file .env với đường dẫn certificate chính xác"
    Write-Host ""
    Write-Host "CẢNH BÁO: Đây là certificate tự ký chỉ dùng cho development/testing!" -ForegroundColor Red
    Write-Host "Đối với production, hãy sử dụng certificate từ Certificate Authority đáng tin cậy." -ForegroundColor Red
    
} catch {
    Write-Host "Lỗi khi tạo certificate: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Hãy chắc chắn OpenSSL đã được cài đặt và có trong PATH" -ForegroundColor Red
    exit 1
}