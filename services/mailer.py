from smtplib import SMTP_SSL as SMTP
from email.mime.text import MIMEText

SMTPserver = 'mail.justmarfix.ru' # mail server domain
sender =     'noreply@justmarfix.ru' # sender email adress
USERNAME = "noreply@justmarfix.ru" 
PASSWORD = "" # sender password
text_subtype = 'plain'

def send_email(username: str, dest: str, token: str):
    try:
        content=f"""\
        Уважаемый {username}!

        От вашего имени поступил запрос на смену пароля на сайте contingent.mos.ru.
        Чтобы сменить пароль, перейдите по ссылке: https://justmeow.ru/restore-password/{token}
        Ссылка будет действительна в течение 15 минут.

        Если это были не вы, просто проигнорируйте это письмо.
        """
        destination = [dest]
        subject = f'{username}: сброс пароля'
        msg = MIMEText(content, text_subtype)

        msg['From']   = f'No-Reply <{sender}>'
        msg['Subject'] = subject
        conn = SMTP(SMTPserver)
        conn.set_debuglevel(False)
        conn.login(USERNAME, PASSWORD)
        try:
            conn.sendmail(sender, destination, msg.as_string())
        finally:
            conn.quit()
    except BaseException as e:
        print(e)
