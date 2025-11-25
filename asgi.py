from app import create_app
from asgiref.wsgi import WsgiToAsgi

flask_app = create_app()
app = WsgiToAsgi(flask_app)
