from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking
from app.settings import settings
from jinja2 import Environment, FileSystemLoader, Template
from fastapi import status, HTTPException


sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

template_env = Environment(loader = FileSystemLoader('app/email_templates'))


def get_mail_message(to_email:str, subject:str, content:str) -> Mail:
    message = Mail(
        from_email=settings.MAIL_ADDRESS,
        to_emails=to_email,
        subject=subject,
        html_content=content
    )

    return message

def send_mail(to_mail:str, subject:str, mail_template:str, **kwargs) -> bool:
    if settings.ENABLED_SEND_MAIL is False:
        return False
    
    try:
        mail_template = template_env.get_template(mail_template)
        content = mail_template.render(**kwargs)
        message = get_mail_message(to_mail, subject, content)

        # Disable click tracking
        tracking_settings = TrackingSettings()
        click_tracking = ClickTracking(enable=False, enable_text=False)
        tracking_settings.click_tracking = click_tracking
        message.tracking_settings = tracking_settings
        
        response = sg.send(message)
        return True
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error while sending email: {e}")
