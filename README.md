# INIS Daily QA Automation (GitHub Actions)

Automated quality assurance system for the International Nuclear Information System (INIS) that runs daily via GitHub Actions.

## Overview

This system automatically:
1. Checks yesterday's INIS records for quality issues
2. Applies automatic corrections where possible
3. Sends detailed reports via email with QA results attached
4. Runs completely in the cloud without requiring local infrastructure

## Features

- **Automated QA Checking**: Uses Azure OpenAI to analyze record metadata
- **Smart Corrections**: Automatically fixes common issues like title formatting
- **Email Reports**: Sends comprehensive reports with attachments
- **GitHub Actions**: Runs on schedule without manual intervention
- **Secure**: All sensitive data stored as GitHub Secrets

## Setup

### 1. Fork this Repository

Fork this repository to your GitHub account.

### 2. Configure GitHub Secrets

Go to your repository Settings → Secrets and variables → Actions, and add the following secrets:

#### Required Secrets

**Azure OpenAI Configuration:**
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `ENDPOINT_URL`: Azure OpenAI endpoint URL (e.g., `https://your-resource.openai.azure.com/`)
- `DEPLOYMENT_NAME`: Your Azure OpenAI deployment name (e.g., `o4-mini`)

**Email Configuration:**
- `FROM_EMAIL`: Email address to send from (e.g., `your-email@gmail.com`)
- `EMAIL_APP_PASSWORD`: App password for email authentication
- `TO_EMAIL`: Recipient email address (e.g., `inis.feedback@iaea.org`)

#### Optional Secrets

- `SMTP_SERVER`: SMTP server (defaults to `smtp.gmail.com`)
- `SMTP_PORT`: SMTP port (defaults to `587`)

### 3. Enable GitHub Actions

Ensure GitHub Actions are enabled in your repository settings.

## Usage

### Automatic Daily Runs

The system runs automatically every day at 6:00 AM UTC. You can modify the schedule in `.github/workflows/daily-qa-check.yml`.

### Manual Runs

You can trigger the workflow manually:

1. Go to the "Actions" tab in your repository
2. Select "Daily INIS QA Check"
3. Click "Run workflow"
4. Optionally specify a date (YYYY-MM-DD format)

## Email Configuration

### Gmail Setup

If using Gmail:

1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
   - Use this password as `EMAIL_APP_PASSWORD`

### Other Email Providers

Update the `SMTP_SERVER` and `SMTP_PORT` secrets according to your provider:

- **Outlook**: `smtp.live.com`, port `587`
- **Yahoo**: `smtp.mail.yahoo.com`, port `587`
- **Custom SMTP**: Your provider's settings

## Architecture

### Core Components

- **`inis_daily_qa_automation.py`**: Main orchestration script
- **`o4-INISQAChecker.py`**: QA checking using Azure OpenAI
- **`qa_email_sender.py`**: Email reporting with attachments
- **`auto_correction_processor.py`**: Automatic correction application
- **`instructions.txt`**: QA prompt for the AI system

### Workflow

1. **Fetch Records**: Retrieves yesterday's records from INIS
2. **QA Analysis**: Analyzes each record using Azure OpenAI
3. **Apply Corrections**: Automatically fixes common issues
4. **Email Report**: Sends summary with detailed results attached
5. **Cleanup**: Removes temporary files

## Monitoring

### Logs

- Check the Actions tab for workflow run logs
- Failed runs will upload logs as artifacts
- Email delivery status is logged

### Troubleshooting

Common issues:

1. **Missing Secrets**: Ensure all required secrets are configured
2. **Email Authentication**: Verify app password is correct
3. **API Limits**: Check Azure OpenAI quota and rate limits
4. **Network Issues**: GitHub Actions may occasionally have connectivity issues

## Security

- All sensitive data is stored as GitHub Secrets
- No API keys or passwords are committed to the repository
- Temporary files are automatically cleaned up
- Email attachments are created securely and removed after sending

## Customization

### Schedule

Modify the cron expression in `.github/workflows/daily-qa-check.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'  # 6:00 AM UTC daily
```

### QA Instructions

Edit `instructions.txt` to modify the AI's quality checking behavior.

### Email Recipients

Add multiple recipients by updating the `TO_EMAIL` secret with comma-separated addresses.

## Development

### Local Testing

While the system is designed for GitHub Actions, you can test locally:

1. Set environment variables:
   ```bash
   export AZURE_OPENAI_API_KEY="your-key"
   export FROM_EMAIL="your-email@gmail.com"
   export EMAIL_APP_PASSWORD="your-app-password"
   # ... other variables
   ```

2. Run the automation:
   ```bash
   python inis_daily_qa_automation.py
   ```

### Dependencies

See `requirements.txt` for Python dependencies. The system uses:
- `openai>=1.30.0` for Azure OpenAI integration
- `requests>=2.28.0` for HTTP requests
- `python-dateutil>=2.8.0` for date handling

## License

[Add your license information here]

## Support

For issues and questions:
- Check the GitHub Actions logs
- Review the troubleshooting section
- Create an issue in this repository