from setuptools import setup, find_packages

setup(
    name="dentist-clinic-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot==20.7",
        "python-dotenv==1.0.0",
        "gspread==5.12.0",
        "google-auth==2.23.4",
        "google-auth-oauthlib==1.1.0",
        "google-auth-httplib2==0.1.1",
        "google-api-python-client==2.108.0",
        "apscheduler==3.10.4",
        "pytz==2023.3",
    ],
    python_requires=">=3.8",
)
