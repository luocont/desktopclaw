---
name: python-smtp-sender
description: |
  Python smtplib wrapper for sending emails via SMTP servers.

  Send emails using Python's built-in smtplib library with support for TLS/SSL,
  attachments, HTML content, and common email providers (Gmail, Outlook, QQ Mail, etc.).
  Ideal for Python applications, scripts, and automation workflows.
user-invocable: true

metadata:
  keywords:
    - python
    - smtplib
    - email
    - smtp
    - gmail
    - outlook
    - qq mail
    - attachments html email
    - ssl tls
license: MIT
---

# Python SMTP Email Sender

**Status**: Production Ready ✅
**Last Updated**: 2026-02-14
**Library**: Python smtplib, email.mime

---

## Default Configuration

```QQ Mail (已配置)
- Email: 3794982701@qq.com
- SMTP: smtp.qq.com:587 (TLS)
```

### 快速发送（使用默认配置）

```python
import smtplib
from email.mime.text import MIMEText

def send_email_quick(recipient, subject, body):
    # 默认配置
    sender_email = "3794982701@qq.com"
    password = "imceiluvpagyccig"

    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.qq.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)

# 使用示例
send_email_quick("recipient@example.com", "邮件主题", "邮件内容")
```

## Quick Start

### Basic Email Sending

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = "your_email@gmail.com"
sender_password = "your_app_password"  # Use App Password, not regular password
recipient_email = "recipient@example.com"

# Create message
msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = recipient_email
msg['Subject'] = 'Test Email'

# Add body
msg.attach(MIMEText('Hello, this is a test email!', 'plain'))

# Send email
with smtplib.SMTP(smtp_server, smtp_port) as server:
    server.starttls()  # Enable TLS
    server.login(sender_email, sender_password)
    server.send_message(msg)
    print("Email sent successfully!")
```

---

## Common SMTP Providers

### Gmail (Google)

```python
import smtplib
from email.mime.text import MIMEText

def send_gmail(sender_email, app_password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
```

**Important**: You need to:
1. Enable 2-Step Verification in Google Account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Use the App Password (16-character code), not your regular password

### Google Workspace (Custom Domain)

```python
# For custom domain emails via Google Workspace
smtp_server = 'smtp.gmail.com'
smtp_port = 587
# Use your full email (e.g., you@yourdomain.com)
```

### Outlook / Microsoft 365

```python
import smtplib

def send_outlook(sender_email, password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.office365.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

### QQ Mail

```python
import smtplib

def send_qq_mail(sender_email, password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.qq.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

**QQ Mail Authorization Code**: Go to QQ Mail Settings → Account → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV Service → Enable SMTP → Get authorization code.

### 163 Mail

```python
import smtplib

def send_163_mail(sender_email, password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.163.com', 465) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

### 126 Mail

```python
import smtplib

def send_126_mail(sender_email, password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.126.com', 25) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

---

## Provider Configuration Reference

| Provider | SMTP Server | TLS Port | SSL Port | Notes |
|----------|-------------|----------|----------|-------|
| Gmail | `smtp.gmail.com` | 587 | 465 | Requires App Password |
| Outlook | `smtp.office365.com` | 587 | 993 | Standard Microsoft 365 |
| Yahoo | `smtp.mail.yahoo.com` | 587 | 465 | Requires App Password |
| QQ Mail | `smtp.qq.com` | 587 | 465 | Requires auth code |
| 163 Mail | `smtp.163.com` | 994 | 465 | |
| 126 Mail | `smtp.126.com` | 465 | 25 | |
| Sina | `smtp.sina.com` | 25 | 465 | |
| Aliyun | `smtp.aliyun.com` | 465 | 465 | |
| SendGrid | `smtp.sendgrid.net` | 587 | 465 | API key as password |
| Mailgun | `smtp.mailgun.org` | 587 | 465 | |

---

## Advanced Features

### HTML Emails

```python
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_html_email(sender_email, password, recipient_email, subject, html_content):
    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Add plain text version
    text_part = MIMEText('This is a plain text fallback', 'plain')
    msg.attach(text_part)

    # Add HTML version
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

**Example HTML:**

```python
html_content = """
<html>
  <body>
    <h1>Hello!</h1>
    <p>This is an <b>HTML email</b>.</p>
    <p><a href="https://example.com">Click here</a></p>
  </body>
</html>
"""
```

### Email with Attachments

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

def send_email_with_attachment(sender_email, password, recipient_email, subject,
                              body, attachment_path):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Add body
    msg.attach(MIMEText(body, 'plain'))

    # Add attachment
    with open(attachment_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())

    encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition',
        f'attachment; filename="{os.path.basename(attachment_path)}"'
    )
    msg.attach(part)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

### Multiple Recipients

```python
def send_bulk_email(sender_email, password, recipient_list, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipient_list)  # Comma-separated
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg(msg, from_addr=sender_email, to_addrs=recipient_list))
```

### CC and BCC

```python
def send_with_cc_bcc(sender_email, password, to_email, cc_emails, bcc_emails, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Cc'] = ', '.join(cc_emails)
    msg['Subject'] = subject

    # BCC recipients are not in headers, passed directly to send_message
    all_recipients = [to_email] + cc_emails + bcc_emails

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg, to_addrs=all_recipients)
```

### Reply-To and Custom Headers

```python
def send_with_headers(sender_email, password, recipient_email, subject, body, reply_to):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg['Reply-To'] = reply_to
    msg['X-Priority'] = '1'  # High priority
    msg['X-Mailer'] = 'Python Email Script'

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

---

## Complete Email Sender Class

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import List, Optional

class EmailSender:
    """A flexible email sender class supporting multiple SMTP providers."""

    # Predefined SMTP configurations
    SMTP_CONFIGS = {
        'gmail': {'server': 'smtp.gmail.com', 'port': 587, 'use_tls': True},
        'outlook': {'server': 'smtp.office365.com', 'port': 587, 'use_tls': True},
        'yahoo': {'server': 'smtp.mail.yahoo.com', 'port': 587, 'use_tls': True},
        'qq': {'server': 'smtp.qq.com', 'port': 587, 'use_tls': True},
        '163': {'server': 'smtp.163.com', 'port': 465, 'use_tls': True},
        '126': {'server': 'smtp.126.com', 'port': 25, 'use_tls': True},
    }

    def __init__(self, smtp_server: str, smtp_port: int,
                 sender_email: str, password: str, use_tls: bool = True):
        """
        Initialize the email sender.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP port
            sender_email: Sender email address
            password: Email password or app password
            use_tls: Whether to use TLS/SSL
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.password = password
        self.use_tls = use_tls

    @classmethod
    def from_provider(cls, provider: str, sender_email: str, password: str):
        """Create EmailSender from a predefined provider."""
        config = cls.SMTP_CONFIGS.get(provider.lower())
        if not config:
            raise ValueError(f"Unknown provider: {provider}")
        return cls(
            config['server'],
            config['port'],
            sender_email,
            password,
            config['use_tls']
        )

    def send(self, recipient_email: str, subject: str,
             body: str, html: bool = False,
             cc: Optional[List[str]] = None,
             bcc: Optional[List[str]] = None,
             reply_to: Optional[str] = None,
             attachments: Optional[List[str]] = None) -> bool:
        """
        Send an email.

        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body (text or HTML)
            html: Whether body is HTML
            cc: List of CC recipients
            bcc: List of BCC recipients
            reply_to: Reply-To address
            attachments: List of file paths to attach

        Returns:
            True if successful, False otherwise
        """
        try:
            msg = MIMEMultipart('alternative') if html else MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject

            if reply_to:
                msg['Reply-To'] = reply_to

            # Add body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Add CC header
            all_recipients = [recipient_email]
            if cc:
                msg['Cc'] = ', '.join(cc)
                all_recipients.extend(cc)

            # BCC recipients
            if bcc:
                all_recipients.extend(bcc)

            # Add attachments
            if attachments:
                for attachment_path in attachments:
                    self._add_attachment(msg, attachment_path)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.sender_email, self.password)
                server.send_message(msg, to_addrs=all_recipients)

            return True

        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """Add a file attachment to the message."""
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{os.path.basename(file_path)}"'
        )
        msg.attach(part)
```

**Usage:**

```python
# Using predefined provider
sender = EmailSender.from_provider('gmail', 'your@gmail.com', 'app_password')
sender.send(
    recipient_email='recipient@example.com',
    subject='Hello',
    body='<h1>Hi there!</h1>',
    html=True
)

# Using custom SMTP
sender = EmailSender(
    smtp_server='custom.smtp.com',
    smtp_port=587,
    sender_email='user@domain.com',
    password='password',
    use_tls=True
)
sender.send(
    recipient_email='recipient@example.com',
    subject='Test',
    body='This is a test email.'
)
```

---

## Error Handling & Best Practices

### Proper Error Handling

```python
import smtplib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_safe(sender_email, password, recipient_recipient_email, subject, body):
    try:
        msg = MIMEText(body, 'plain')
        msg['From'] = sender_email
        msg['To'] = recipient_recipient_email
        msg['Subject'] = subject

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.set_debuglevel(1)  # Enable debug output
            server.starttls()
            server.login(sender_email, password)
            server.send_message(msg)
            logger.info(f"Email sent to {recipient_recipient_email}")
            return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Authentication failed. Check email/password.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
```

### Using Environment Variables for Security

```python
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Example .env file:
# EMAIL_ADDRESS=your_email@gmail.com
# EMAIL_PASSWORD=your_app_password
```

### Timeout Configuration

```python
def send_email_with_timeout(sender_email, password, recipient_email, subject, body):
    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
```

---

## Common SMTP Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `SMTPAuthenticationError` | Invalid credentials | Use app password, enable 2FA |
| `SMTPServerDisconnected` | Connection timeout | Check network, increase timeout |
| `SMTPRecipientsRefused` | Invalid recipient | Verify email format |
| `SMTPDataError` | Message too large | Check attachment size limits |
| `SSLError` | SSL/TLS issue | Check port, TLS settings |

---

## Testing

### Test SMTP Connection

```python
import smtplib

def test_smtp_connection(smtp_server, smtp_port):
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            print(f"Successfully connected to {smtp_server}:{smtp_port}")
            print(f"Server capabilities: {server.esmtp_features}")
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

# Test
test_smtp_connection('smtp.gmail.com', 587)
```

---

## Resources

- [Python smtplib Documentation](https://docs.python.org/3/library/smtplib.html)
- [Python email.mime Documentation](https://docs.python.org/3/library/email.mime.html)
- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [Microsoft SMTP Settings](https://support.microsoft.com/en-us/office/pop-or-imap-access-for-a-microsoft-exchange-account-58f80a16-7df0-41f8-94ec-623b272f0b3c)

---

**Security Notes**:
- Never commit email passwords to version control
- Use environment variables or secret managers
- Enable 2-Step Verification and use App Passwords when available
- Use TLS/SSL for secure transmission
- Consider rate limiting for bulk sending
