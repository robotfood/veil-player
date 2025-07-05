import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # IPTV Configuration
    IPTV_PLAYLIST_URL = os.environ.get('IPTV_PLAYLIST_URL', '')
    
    # VPN Configuration
    VPN_CONFIG_PATH = os.environ.get('VPN_CONFIG_PATH')
    VPN_USER = os.environ.get('VPN_USER')
    VPN_PASSWORD = os.environ.get('VPN_PASSWORD')
