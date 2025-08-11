# ========================================
# CourseConnect - Social Network Completo
# Backend Flask + Chat Real-time + Media Upload
# ========================================

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json
import uuid
from PIL import Image

# Inizializzazione Flask
app = Flask(__name__)

# Configurazioni
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'courseconnect-super-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///courseconnect.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Inizializzazione estensioni
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Crea cartelle upload se non esistono
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)

# Configurazioni upload
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'webm'}

# ========================================
# MODELLI DATABASE
# ========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, default='')
    course = db.Column(db.String(100), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relazioni
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'bio': self.bio,
            'course': self.course,
            'posts_count': self.posts.count(),
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat()
        }

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    media_type = db.Column(db.String(20), default='text')  # text, image, video
    media_url = db.Column(db.String(500))  # URL del file caricato
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relazioni
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_likes_count(self):
        return self.likes.count()
    
    def is_liked_by(self, user_id):
        if not user_id:
            return False
        return self.likes.filter_by(user_id=user_id).first() is not None
    
    def to_dict(self, current_user_id=None):
        return {
            'id': self.id,
            'content': self.content,
            'media_type': self.media_type,
            'media_url': self.media_url,
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            'author': self.author.to_dict() if self.author else {},
            'likes_count': self.get_likes_count(),
            'comments_count': self.comments.count(),
            'is_liked': self.is_liked_by(current_user_id)
        }

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            'author': self.author.to_dict() if self.author else {}
        }

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    course = db.Column(db.String(100))  # Chat per corso specifico
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    messages = db.relationship('ChatMessage', backref='room', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'course': self.course,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            'messages_count': self.messages.count()
        }

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, file
    file_url = db.Column(db.String(500))  # Per allegati
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relazioni
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'message_type': self.message_type,
            'file_url': self.file_url,
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            'author': self.author.to_dict() if self.author else {},
            'room_id': self.room_id
        }

# ========================================
# UTILITY FUNCTIONS
# ========================================

def get_current_user():
    """Ottieni utente corrente dalla sessione"""
    try:
        if 'user_id' in session:
            return User.query.get(session['user_id'])
    except:
        pass
    return None

def api_response(data=None, success=True, message='', error='', status_code=200):
    """Standardizza le risposte API"""
    response_data = {
        'success': success,
        'message': message,
        'error': error
    }
    if data:
        response_data.update(data)
    
    response = jsonify(response_data)
    response.status_code = status_code
    return response

def allowed_file(filename, file_type='image'):
    """Controlla se il file è di tipo consentito"""
    if file_type == 'image':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'video':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS
    return False

def resize_image(image_path, max_size=(800, 800)):
    """Ridimensiona immagine per ottimizzare storage"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(image_path, optimize=True, quality=85)
    except Exception as e:
        print(f"Errore nel resize immagine: {e}")

# ========================================
# ROUTES API - AUTENTICAZIONE
# ========================================

@app.route('/api/register', methods=['POST'])
def register():
    """Registrazione nuovo utente"""
    try:
        data = request.get_json()
        if not data:
            return api_response(success=False, error='Dati non validi', status_code=400)
        
        # Validazioni
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field, '').strip():
                return api_response(success=False, error=f'Campo {field} richiesto', status_code=400)
        
        # Check se utente esiste già
        if User.query.filter_by(username=data['username'].strip()).first():
            return api_response(success=False, error='Username già in uso', status_code=400)
        
        if User.query.filter_by(email=data['email'].strip()).first():
            return api_response(success=False, error='Email già registrata', status_code=400)
        
        # Crea nuovo utente
        user = User(
            username=data['username'].strip(),
            email=data['email'].strip(),
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            bio=data.get('bio', '').strip(),
            course=data.get('course', '').strip()
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Login automatico
        session['user_id'] = user.id
        session['username'] = user.username
        
        return api_response(
            data={'user': user.to_dict()},
            message='Registrazione completata con successo!'
        )
        
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=f'Errore server: {str(e)}', status_code=500)

@app.route('/api/login', methods=['POST'])
def login():
    """Login utente"""
    try:
        data = request.get_json()
        if not data:
            return api_response(success=False, error='Dati non validi', status_code=400)
        
        username_or_email = data.get('username_or_email', '').strip()
        password = data.get('password', '')
        
        if not username_or_email or not password:
            return api_response(success=False, error='Username/email e password richiesti', status_code=400)
        
        # Cerca utente
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()
        
        if not user or not user.check_password(password):
            return api_response(success=False, error='Credenziali non valide', status_code=401)
        
        if not user.is_active:
            return api_response(success=False, error='Account disattivato', status_code=401)
        
        # Login
        session['user_id'] = user.id
        session['username'] = user.username
        
        return api_response(
            data={'user': user.to_dict()},
            message='Login effettuato con successo!'
        )
        
    except Exception as e:
        return api_response(success=False, error=f'Errore server: {str(e)}', status_code=500)

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout utente"""
    try:
        session.clear()
        return api_response(message='Logout effettuato con successo!')
    except Exception as e:
        return api_response(success=False, error=f'Errore server: {str(e)}', status_code=500)

@app.route('/api/me', methods=['GET'])
def get_current_user_api():
    """Ottieni dati utente corrente"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Non autorizzato', status_code=401)
        
        return api_response(data={'user': user.to_dict()})
        
    except Exception as e:
        return api_response(success=False, error=f'Errore server: {str(e)}', status_code=500)

# ========================================
# ROUTES API - POST
# ========================================

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Ottieni tutti i post (feed pubblico)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        posts_query = Post.query.order_by(Post.created_at.desc())
        posts = posts_query.paginate(page=page, per_page=per_page, error_out=False)
        
        current_user_id = session.get('user_id')
        
        posts_data = []
        for post in posts.items:
            try:
                posts_data.append(post.to_dict(current_user_id))
            except Exception as e:
                print(f"Errore nel processare post {post.id}: {e}")
                continue
        
        return api_response(data={
            'posts': posts_data,
            'has_next': posts.has_next,
            'page': page,
            'total': posts.total
        })
        
    except Exception as e:
        return api_response(success=False, error=f'Errore nel caricamento post: {str(e)}', status_code=500)

@app.route('/api/posts', methods=['POST'])
def create_post():
    """Crea nuovo post con supporto media"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        data = request.get_json()
        if not data:
            return api_response(success=False, error='Dati non validi', status_code=400)
        
        content = data.get('content', '').strip()
        media_type = data.get('media_type', 'text')
        media_url = data.get('media_url', '')
        
        # Validazioni
        if not content and not media_url:
            return api_response(success=False, error='Contenuto o media richiesto', status_code=400)
        
        if content and len(content) > 2000:
            return api_response(success=False, error='Post troppo lungo (max 2000 caratteri)', status_code=400)
        
        post = Post(
            content=content,
            media_type=media_type,
            media_url=media_url,
            user_id=user.id
        )
        
        db.session.add(post)
        db.session.commit()
        
        return api_response(
            data={'post': post.to_dict(user.id)},
            message='Post pubblicato con successo!'
        )
        
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=f'Errore nella creazione post: {str(e)}', status_code=500)

@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    """Toggle like su post"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        post = Post.query.get(post_id)
        if not post:
            return api_response(success=False, error='Post non trovato', status_code=404)
        
        existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
        
        if existing_like:
            # Rimuovi like
            db.session.delete(existing_like)
            action = 'removed'
        else:
            # Aggiungi like
            like = Like(user_id=user.id, post_id=post_id)
            db.session.add(like)
            action = 'added'
        
        db.session.commit()
        
        return api_response(data={
            'action': action,
            'likes_count': post.get_likes_count()
        })
        
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=f'Errore nel like: {str(e)}', status_code=500)

@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    """Ottieni commenti post"""
    try:
        post = Post.query.get_or_404(post_id)
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
        
        return api_response(data={
            'comments': [comment.to_dict() for comment in comments]
        })
        
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)

@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    """Aggiungi commento"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return api_response(success=False, error='Contenuto commento richiesto', status_code=400)
        
        post = Post.query.get_or_404(post_id)
        
        comment = Comment(
            content=content,
            user_id=user.id,
            post_id=post_id
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return api_response(
            data={'comment': comment.to_dict()},
            message='Commento aggiunto!'
        )
        
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=str(e), status_code=500)

# ========================================
# ROUTES API - UPLOAD MEDIA
# ========================================

@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    """Upload immagine per post"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        if 'image' not in request.files:
            return api_response(success=False, error='Nessuna immagine selezionata', status_code=400)
        
        file = request.files['image']
        if file.filename == '':
            return api_response(success=False, error='Nessuna immagine selezionata', status_code=400)
        
        if not allowed_file(file.filename, 'image'):
            return api_response(success=False, error='Formato immagine non supportato. Usa: PNG, JPG, JPEG, GIF, WEBP', status_code=400)
        
        # Genera nome file unico
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images', unique_filename)
        
        # Salva file
        file.save(file_path)
        
        # Ridimensiona per ottimizzare
        resize_image(file_path)
        
        # URL pubblico
        image_url = f"/static/uploads/images/{unique_filename}"
        
        return api_response(data={
            'image_url': image_url,
            'filename': unique_filename
        }, message='Immagine caricata con successo!')
        
    except Exception as e:
        return api_response(success=False, error=f'Errore upload immagine: {str(e)}', status_code=500)

@app.route('/api/upload/video', methods=['POST'])
def upload_video():
    """Upload video per post"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        if 'video' not in request.files:
            return api_response(success=False, error='Nessun video selezionato', status_code=400)
        
        file = request.files['video']
        if file.filename == '':
            return api_response(success=False, error='Nessun video selezionato', status_code=400)
        
        if not allowed_file(file.filename, 'video'):
            return api_response(success=False, error='Formato video non supportato. Usa: MP4, AVI, MOV, WEBM', status_code=400)
        
        # Controlla dimensione file (max 50MB per video)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            return api_response(success=False, error='Video troppo grande. Massimo 50MB', status_code=400)
        
        # Genera nome file unico
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', unique_filename)
        
        # Salva file
        file.save(file_path)
        
        # URL pubblico
        video_url = f"/static/uploads/videos/{unique_filename}"
        
        return api_response(data={
            'video_url': video_url,
            'filename': unique_filename
        }, message='Video caricato con successo!')
        
    except Exception as e:
        return api_response(success=False, error=f'Errore upload video: {str(e)}', status_code=500)

# ========================================
# ROUTES API - CHAT
# ========================================

@app.route('/api/chat/rooms', methods=['GET'])
def get_chat_rooms():
    """Ottieni tutte le chat room"""
    try:
        rooms = ChatRoom.query.filter_by(is_public=True).order_by(ChatRoom.created_at.desc()).all()
        return api_response(data={
            'rooms': [room.to_dict() for room in rooms]
        })
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)

@app.route('/api/chat/rooms', methods=['POST'])
def create_chat_room():
    """Crea nuova chat room"""
    try:
        user = get_current_user()
        if not user:
            return api_response(success=False, error='Login richiesto', status_code=401)
        
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        course = data.get('course', '').strip()
        
        if not name:
            return api_response(success=False, error='Nome chat richiesto', status_code=400)
        
        room = ChatRoom(
            name=name,
            description=description,
            course=course,
            created_by=user.id
        )
        
        db.session.add(room)
        db.session.commit()
        
        return api_response(
            data={'room': room.to_dict()},
            message='Chat room creata!'
        )
        
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=str(e), status_code=500)

@app.route('/api/chat/rooms/<int:room_id>/messages', methods=['GET'])
def get_chat_messages(room_id):
    """Ottieni messaggi di una chat room"""
    try:
        room = ChatRoom.query.get_or_404(room_id)
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        messages = ChatMessage.query.filter_by(room_id=room_id)\
            .order_by(ChatMessage.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Inverti ordine per mostrare messaggi più vecchi prima
        messages_list = list(reversed([msg.to_dict() for msg in messages.items]))
        
        return api_response(data={
            'messages': messages_list,
            'has_next': messages.has_next,
            'page': page
        })
        
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)

# ========================================
# WEBSOCKET EVENTS - CHAT REAL-TIME
# ========================================

@socketio.on('connect')
def on_connect():
    """Utente si connette alla chat"""
    print(f'Client connesso: {request.sid}')
    emit('connected', {'message': 'Connesso al server chat!'})

@socketio.on('disconnect')
def on_disconnect():
    """Utente si disconnette"""
    print(f'Client disconnesso: {request.sid}')

@socketio.on('join_room')
def on_join_room(data):
    """Utente entra in una chat room"""
    try:
        room_id = data.get('room_id')
        username = data.get('username', 'Utente')
        
        if not room_id:
            emit('error', {'message': 'Room ID richiesto'})
            return
        
        # Verifica che la room esista
        room = ChatRoom.query.get(room_id)
        if not room:
            emit('error', {'message': 'Chat room non trovata'})
            return
        
        # Entra nella room
        join_room(str(room_id))
        
        # Notifica agli altri utenti
        emit('user_joined', {
            'message': f'{username} è entrato nella chat',
            'username': username,
            'timestamp': datetime.now().strftime('%H:%M')
        }, room=str(room_id), include_self=False)
        
        # Conferma al client
        emit('joined_room', {
            'room_id': room_id,
            'room_name': room.name,
            'message': f'Sei entrato in {room.name}'
        })
        
    except Exception as e:
        emit('error', {'message': f'Errore join room: {str(e)}'})

@socketio.on('leave_room')
def on_leave_room(data):
    """Utente esce da una chat room"""
    try:
        room_id = data.get('room_id')
        username = data.get('username', 'Utente')
        
        if room_id:
            leave_room(str(room_id))
            
            # Notifica agli altri
            emit('user_left', {
                'message': f'{username} ha lasciato la chat',
                'username': username,
                'timestamp': datetime.now().strftime('%H:%M')
            }, room=str(room_id))
            
    except Exception as e:
        emit('error', {'message': f'Errore leave room: {str(e)}'})

@socketio.on('send_message')
def on_send_message(data):
    """Invia messaggio in chat"""
    try:
        user_id = data.get('user_id')
        room_id = data.get('room_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        file_url = data.get('file_url', '')
        
        if not user_id or not room_id:
            emit('error', {'message': 'User ID e Room ID richiesti'})
            return
        
        if not content and not file_url:
            emit('error', {'message': 'Contenuto messaggio richiesto'})
            return
        
        # Verifica utente
        user = User.query.get(user_id)
        if not user:
            emit('error', {'message': 'Utente non trovato'})
            return
        
        # Verifica room
        room = ChatRoom.query.get(room_id)
        if not room:
            emit('error', {'message': 'Chat room non trovata'})
            return
        
        # Salva messaggio nel database
        message = ChatMessage(
            content=content,
            message_type=message_type,
            file_url=file_url,
            user_id=user_id,
            room_id=room_id
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Prepara dati messaggio
        message_data = {
            'id': message.id,
            'content': content,
            'message_type': message_type,
            'file_url': file_url,
            'author': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'course': user.course
            },
            'created_at': message.created_at.isoformat(),
            'timestamp': datetime.now().strftime('%H:%M'),
            'room_id': room_id
        }
        
        # Invia a tutti nella room
        emit('receive_message', message_data, room=str(room_id))
        
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': f'Errore invio messaggio: {str(e)}'})

@socketio.on('typing_start')
def on_typing_start(data):
    """Utente inizia a scrivere"""
    try:
        room_id = data.get('room_id')
        username = data.get('username')
        
        if room_id and username:
            emit('user_typing', {
                'username': username,
                'typing': True
            }, room=str(room_id), include_self=False)
            
    except Exception as e:
        pass

@socketio.on('typing_stop')
def on_typing_stop(data):
    """Utente smette di scrivere"""
    try:
        room_id = data.get('room_id')
        username = data.get('username')
        
        if room_id and username:
            emit('user_typing', {
                'username': username,
                'typing': False
            }, room=str(room_id), include_self=False)
            
    except Exception as e:
        pass

# ========================================
# ROUTES WEB - PAGINE PRINCIPALI
# ========================================

@app.route('/')
def index():
    """Homepage - Feed principale"""
    return render_template('index.html')

@app.route('/chat')
def chat_page():
    """Pagina chat"""
    return render_template('chat.html')

@app.route('/profile/<username>')
def profile_page(username):
    """Pagina profilo utente"""
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

# Serve file statici
@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve file caricati"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================================
# UTILITY E HEALTH CHECK
# ========================================

@app.route('/health')
def health_check():
    """Health check per monitoring"""
    try:
        # Test database connection
        users_count = User.query.count()
        posts_count = Post.query.count()
        rooms_count = ChatRoom.query.count()
        
        return api_response(data={
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'users_count': users_count,
            'posts_count': posts_count,
            'chat_rooms_count': rooms_count
        })
    except Exception as e:
        return api_response(success=False, error=f'Errore health check: {str(e)}', status_code=500)

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    """Handler 404"""
    if request.path.startswith('/api/'):
        return api_response(success=False, error='Endpoint API non trovato', status_code=404)
    return render_template('index.html')

@app.errorhandler(500)
def internal_error(error):
    """Handler 500"""
    db.session.rollback()
    if request.path.startswith('/api/'):
        return api_response(success=False, error='Errore interno del server', status_code=500)
    return render_template('index.html')

# ========================================
# INIZIALIZZAZIONE DATABASE
# ========================================

def create_tables():
    """Crea tabelle database e dati di esempio"""
    try:
        with app.app_context():
            db.create_all()
            
            # Controlla se esistono già utenti
            if User.query.count() > 0:
                print("✅ Database già inizializzato")
                return
            
            # Crea utente admin
            admin = User(
                username='admin',
                email='admin@courseconnect.com',
                first_name='Admin',
                last_name='CourseConnect',
                bio='Amministratore della piattaforma CourseConnect',
                course='Amministrazione'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Crea utenti di esempio
            users_data = [
                {'username': 'marco_dev', 'email': 'marco@example.com', 'first_name': 'Marco', 'last_name': 'Rossi', 'course': 'Sviluppo Web', 'bio': 'Appassionato di React e Python'},
                {'username': 'sofia_design', 'email': 'sofia@example.com', 'first_name': 'Sofia', 'last_name': 'Bianchi', 'course': 'UI/UX Design', 'bio': 'Designer creativa con focus su UX'},
                {'username': 'luca_marketing', 'email': 'luca@example.com', 'first_name': 'Luca', 'last_name': 'Verdi', 'course': 'Digital Marketing', 'bio': 'Esperto in social media marketing'}
            ]
            
            created_users = []
            for user_data in users_data:
                user = User(**user_data)
                user.set_password('password123')
                db.session.add(user)
                created_users.append(user)
            
            db.session.commit()
            
            # Crea post di esempio
            posts_data = [
                {'user': admin, 'content': '🎉 Benvenuti su CourseConnect! Questa è la piattaforma sociale per corsisti. Condividete i vostri progressi e imparate insieme!'},
                {'user': created_users[0], 'content': 'Oggi ho completato il modulo su React Hooks! 💪 Chi altro sta studiando React? Consigli per gestire lo stato complesso?'},
                {'user': created_users[1], 'content': 'Appena finito di creare il mio primo prototipo in Figma! 🎨 L\'user research è davvero fondamentale per un buon design.'},
                {'user': created_users[2], 'content': 'Ottimi risultati dalla campagna Instagram di questa settimana! 📈 Il contenuto video funziona sempre meglio. Voi che strategie usate?'},
                {'user': created_users[0], 'content': 'Qualcuno ha esperienza con Flask? Sto costruendo la mia prima web app e ho qualche dubbio sul deployment 🤔'},
                {'user': created_users[1], 'content': 'Condivido questa risorsa super utile per le palette di colori: Coolors.co 🌈 Perfetto per trovare combinazioni armoniose!'}
            ]
            
            for post_data in posts_data:
                post = Post(
                    content=post_data['content'],
                    user_id=post_data['user'].id,
                    created_at=datetime.utcnow()
                )
                db.session.add(post)
            
            db.session.commit()
            print("✅ Database inizializzato con successo!")
            print("👤 Admin: username=admin, password=admin123")
            print("👥 Utenti esempio: password=password123")
            
    except Exception as e:
        print(f"❌ Errore nell'inizializzazione database: {e}")
        db.session.rollback()

def create_default_chat_rooms():
    """Crea chat room di default"""
    try:
        with app.app_context():
            # Controlla se esistono già room
            if ChatRoom.query.count() > 0:
                print("✅ Chat rooms già create")
                return
            
            default_rooms = [
                {
                    'name': '💬 Chat Generale',
                    'description': 'Discussioni generali tra tutti i corsisti',
                    'course': ''
                },
                {
                    'name': '💻 Sviluppo Web',
                    'description': 'Chat dedicata ai corsisti di sviluppo web',
                    'course': 'Sviluppo Web'
                },
                {
                    'name': '🎨 Design UI/UX',
                    'description': 'Chat per designer e appassionati di UX',
                    'course': 'UI/UX Design'
                },
                {
                    'name': '📈 Digital Marketing',
                    'description': 'Strategie e discussioni di marketing digitale',
                    'course': 'Digital Marketing'
                },
                {
                    'name': '❓ Domande & Risposte',
                    'description': 'Fai domande e aiuta gli altri corsisti',
                    'course': ''
                },
                {
                    'name': '🚀 Progetti',
                    'description': 'Condividi i tuoi progetti e collabora',
                    'course': ''
                }
            ]
            
            # Trova admin user
            admin = User.query.filter_by(username='admin').first()
            admin_id = admin.id if admin else 1
            
            for room_data in default_rooms:
                room = ChatRoom(
                    name=room_data['name'],
                    description=room_data['description'],
                    course=room_data['course'],
                    created_by=admin_id
                )
                db.session.add(room)
            
            db.session.commit()
            print("✅ Chat rooms default create!")
            
    except Exception as e:
        print(f"❌ Errore creazione chat rooms: {e}")
        db.session.rollback()

# ========================================
# AVVIO APPLICAZIONE
# ========================================

if __name__ == '__main__':
    create_tables()
    create_default_chat_rooms()
    
    # Avvio server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚀 CourseConnect COMPLETO avviato su porta {port}")
    print(f"🌐 Features: Social Network + Chat Real-time + Media Upload")
    print(f"🎯 Modalità: {'Development' if debug else 'Production'}")
    
    # Avvia con SocketIO per chat real-time
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)