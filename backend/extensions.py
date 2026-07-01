from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import redis

db = SQLAlchemy()

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

socketio = SocketIO(cors_allowed_origins='*', async_mode='threading', manage_session=False)
