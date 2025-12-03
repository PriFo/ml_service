"""Script to generate self-signed SSL certificate for HTTPS support"""
import subprocess
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def generate_ssl_certificate(hostname: str = "localhost", days: int = 365):
    """Generate self-signed SSL certificate"""
    # Determine project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    ssl_dir = project_root / "ssl"
    
    # Create ssl directory if it doesn't exist
    ssl_dir.mkdir(exist_ok=True)
    
    cert_file = ssl_dir / "cert.pem"
    key_file = ssl_dir / "key.pem"
    
    # Check if openssl is available
    try:
        subprocess.run(
            ["openssl", "version"],
            capture_output=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: OpenSSL is not installed or not found in PATH")
        print("Please install OpenSSL to generate SSL certificates:")
        print("  Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("  Linux: sudo apt-get install openssl (Debian/Ubuntu) or sudo yum install openssl (RHEL/CentOS)")
        print("  Mac: brew install openssl")
        sys.exit(1)
    
    # Check if certificate already exists
    if cert_file.exists() and key_file.exists():
        response = input(
            f"SSL certificate already exists at {cert_file}.\n"
            "Do you want to overwrite it? (y/N): "
        )
        if response.lower() != 'y':
            print("Certificate generation cancelled.")
            return
    
    # Generate certificate
    print(f"Generating self-signed SSL certificate for {hostname}...")
    print(f"Certificate will be valid for {days} days")
    
    # Create OpenSSL configuration for Subject Alternative Name (SAN)
    config_content = f"""
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
CN = {hostname}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = {hostname}
DNS.2 = localhost
IP.1 = 127.0.0.1
"""
    
    config_file = ssl_dir / "openssl.conf"
    config_file.write_text(config_content)
    
    try:
        # Generate private key
        print("Generating private key...")
        subprocess.run(
            [
                "openssl", "genrsa",
                "-out", str(key_file),
                "2048"
            ],
            check=True,
            capture_output=True
        )
        
        # Generate certificate signing request and self-signed certificate
        print("Generating certificate...")
        subprocess.run(
            [
                "openssl", "req",
                "-new", "-x509",
                "-key", str(key_file),
                "-out", str(cert_file),
                "-days", str(days),
                "-config", str(config_file),
                "-extensions", "v3_req"
            ],
            check=True,
            capture_output=True
        )
        
        # Clean up config file
        config_file.unlink()
        
        print(f"\n✓ SSL certificate generated successfully!")
        print(f"  Certificate: {cert_file}")
        print(f"  Private key: {key_file}")
        print(f"\n⚠️  WARNING: This is a self-signed certificate.")
        print(f"   Browsers will show a security warning.")
        print(f"   For production, use certificates from a trusted CA.")
        print(f"\nTo enable HTTPS, set in .env file:")
        print(f"  ML_USE_HTTPS=true")
        print(f"  ML_SSL_CERT_FILE={cert_file.relative_to(project_root)}")
        print(f"  ML_SSL_KEY_FILE={key_file.relative_to(project_root)}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error generating certificate: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr.decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate self-signed SSL certificate for HTTPS support"
    )
    parser.add_argument(
        "--hostname",
        default="localhost",
        help="Hostname for the certificate (default: localhost)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Certificate validity in days (default: 365)"
    )
    
    args = parser.parse_args()
    
    # Get actual IP address or hostname if needed
    hostname = args.hostname
    if hostname == "auto":
        import socket
        hostname = socket.gethostname()
        try:
            # Try to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            hostname = s.getsockname()[0]
            s.close()
        except:
            pass
    
    generate_ssl_certificate(hostname, args.days)

