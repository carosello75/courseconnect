# ======================================== 
# CourseConnect - Social Network per Corsisti 
# app.py - Backend Flask con Sistema Completo + Corsi Full LMS
# ======================================== 

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import hashlib
import os
import secrets
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'courseconnect-super-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///courseconnect.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# ======================================== 
# DATABASE MODELS 
# ======================================== 

def generate_avatar_color():
    """Genera un colore avatar casuale"""
    colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140', '#ff6b6b']
    return secrets.choice(colors)

def get_initials(nome, cognome):
    """Genera iniziali da nome e cognome"""
    return f"{nome[0].upper()}{cognome[0].upper()}" if nome and cognome else "XX"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    corso = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text)
    avatar_color = db.Column(db.String(7), default=generate_avatar_color)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='author', lazy=True, cascade='all, delete-orphan')
    
    # 🔔 Notifiche relationships
    sent_notifications = db.relationship('Notification', foreign_keys='Notification.sender_id', backref='sender', lazy='dynamic', cascade='all, delete-orphan')
    received_notifications = db.relationship('Notification', foreign_keys='Notification.recipient_id', backref='recipient', lazy='dynamic', cascade='all, delete-orphan')
    
    # 🎓 Corsi relationships - NUOVO
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, cascade='all, delete-orphan')
    lesson_progress = db.relationship('LessonProgress', backref='student', lazy=True, cascade='all, delete-orphan')
    
    @property
    def initials(self):
        return get_initials(self.nome, self.cognome)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Media files
    image_filename = db.Column(db.String(255))
    video_filename = db.Column(db.String(255))
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    photo_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class DeletedAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    deletion_reason = db.Column(db.String(200))
    feedback = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)

# 🔔 Modello Notifiche
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # like, comment, course_enrollment, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Optional reference IDs
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)

# 🎓 Modelli Corsi - ESISTENTE (modificato)
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    course_type = db.Column(db.String(50), default='CORSI')  # CORSI, TRAINING
    skill_level = db.Column(db.String(50), nullable=False)  # Beginner, Intermediate, Advanced
    duration_hours = db.Column(db.Integer, default=0)
    thumbnail_url = db.Column(db.String(500))
    price = db.Column(db.Float, default=0.0)
    is_private = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Instructor (admin who created the course)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    instructor = db.relationship('User', backref='taught_courses', foreign_keys=[instructor_id])
    
    # 🎓 NUOVO: Relationships per il sistema completo
    lessons = db.relationship('Lesson', backref='course', lazy=True, cascade='all, delete-orphan', order_by='Lesson.order_index')
    enrollments = db.relationship('Enrollment', backref='course', lazy=True, cascade='all, delete-orphan')

# 🎓 NUOVO: Modello Lezioni
class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)  # Contenuto markdown della lezione
    order_index = db.Column(db.Integer, nullable=False)  # Ordine nella sequenza
    duration_minutes = db.Column(db.Integer, default=10)  # Durata stimata in minuti
    is_free = db.Column(db.Boolean, default=False)  # Prima lezione sempre gratuita
    video_url = db.Column(db.String(500))  # URL video opzionale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Key
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Relationships
    progress_records = db.relationship('LessonProgress', backref='lesson', lazy=True, cascade='all, delete-orphan')

# 🎓 NUOVO: Modello Iscrizioni Corsi
class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='unique_user_course_enrollment'),)

# 🎓 NUOVO: Modello Progresso Lezioni
class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_spent_minutes = db.Column(db.Integer, default=0)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'lesson_id', name='unique_user_lesson_progress'),)

# ======================================== 
# UTILITY FUNCTIONS 
# ======================================== 

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_current_user():
    """Ottieni l'utente corrente dalla sessione"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def require_auth():
    """Decorator per richiedere autenticazione"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Autenticazione richiesta'}), 401
    return user

def require_admin():
    """Decorator per richiedere permessi admin"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Autenticazione richiesta'}), 401
    if not user.is_admin:
        return jsonify({'error': 'Permessi amministratore richiesti'}), 403
    return user

# 🔔 Funzioni Notifiche
def create_notification(recipient_id, notification_type, title, message, sender_id=None, post_id=None, comment_id=None, course_id=None):
    """Crea una nuova notifica"""
    try:
        notification = Notification(
            type=notification_type,
            title=title,
            message=message,
            recipient_id=recipient_id,
            sender_id=sender_id,
            post_id=post_id,
            comment_id=comment_id,
            course_id=course_id
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Errore creazione notifica: {e}")
        db.session.rollback()
        return False

def create_system_notification(recipient_id, notification_type, title, message):
    """Crea una notifica di sistema (senza sender)"""
    return create_notification(recipient_id, notification_type, title, message)

def time_ago(dt):
    """Converte datetime in formato 'time ago'"""
    if not dt:
        return 'Unknown'
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days}g fa"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h fa"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m fa"
    else:
        return "Ora"

# ======================================== 
# MAIN ROUTES 
# ======================================== 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ======================================== 
# AUTH API ROUTES 
# ======================================== 

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validazione input
        required_fields = ['nome', 'cognome', 'username', 'email', 'corso', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} richiesto'}), 400
        
        # Verifica se username o email esistono già
        existing_user = User.query.filter(
            (User.username == data['username']) | (User.email == data['email'])
        ).first()
        
        if existing_user:
            return jsonify({'error': 'Username o email già in uso'}), 400
        
        # Crea nuovo utente
        password_hash = generate_password_hash(data['password'])
        
        # Primo utente diventa admin automaticamente
        is_admin = User.query.count() == 0
        
        user = User(
            username=data['username'],
            email=data['email'],
            password_hash=password_hash,
            nome=data['nome'],
            cognome=data['cognome'],
            corso=data['corso'],
            bio=data.get('bio', ''),
            is_admin=is_admin
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Login automatico
        session['user_id'] = user.id
        
        # 🔔 Crea notifica di benvenuto
        create_system_notification(
            user.id,
            'welcome',
            'Benvenuto in CourseConnect!',
            f'Ciao {user.nome}! Benvenuto nella community di corsisti più dinamica. Inizia a connetterti e condividere la tua esperienza di apprendimento!'
        )
        
        return jsonify({
            'message': 'Registrazione completata con successo!',
            'user': {
                'id': user.id,
                'username': user.username,
                'nome': user.nome,
                'cognome': user.cognome,
                'corso': user.corso,
                'avatar_color': user.avatar_color,
                'initials': user.initials,
                'is_admin': user.is_admin
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante la registrazione: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username e password richiesti'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            
            return jsonify({
                'message': 'Login effettuato con successo!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'nome': user.nome,
                    'cognome': user.cognome,
                    'corso': user.corso,
                    'avatar_color': user.avatar_color,
                    'initials': user.initials,
                    'is_admin': user.is_admin
                }
            }), 200
        else:
            return jsonify({'error': 'Credenziali non valide'}), 401
            
    except Exception as e:
        return jsonify({'error': f'Errore durante il login: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logout effettuato con successo'}), 200

@app.route('/api/me')
def me():
    user = get_current_user()
    if user:
        # Conta notifiche non lette
        unread_notifications = Notification.query.filter_by(
            recipient_id=user.id,
            is_read=False
        ).count()
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'nome': user.nome,
                'cognome': user.cognome,
                'email': user.email,
                'corso': user.corso,
                'bio': user.bio,
                'avatar_color': user.avatar_color,
                'initials': user.initials,
                'is_admin': user.is_admin,
                'unread_notifications': unread_notifications
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 200

# ======================================== 
# POSTS API ROUTES 
# ======================================== 

@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        current_user = get_current_user()
        
        posts = Post.query.order_by(Post.created_at.desc()).all()
        
        posts_data = []
        for post in posts:
            # Conta likes e verifica se l'utente corrente ha messo like
            likes_count = Like.query.filter_by(post_id=post.id).count()
            is_liked = False
            if current_user:
                is_liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
            
            # Conta commenti
            comments_count = Comment.query.filter_by(post_id=post.id).count()
            
            posts_data.append({
                'id': post.id,
                'content': post.content,
                'created_at': post.created_at.isoformat(),
                'image_filename': post.image_filename,
                'video_filename': post.video_filename,
                'likes_count': likes_count,
                'is_liked': is_liked,
                'comments_count': comments_count,
                'author': {
                    'id': post.author.id,
                    'username': post.author.username,
                    'nome': post.author.nome,
                    'cognome': post.author.cognome,
                    'corso': post.author.corso,
                    'avatar_color': post.author.avatar_color,
                    'initials': post.author.initials
                }
            })
        
        return jsonify({'posts': posts_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento dei post: {str(e)}'}), 500

@app.route('/api/posts', methods=['POST'])
def create_post():
    user = require_auth()
    if isinstance(user, tuple):  # Error response
        return user
    
    try:
        # Handle multipart form data (for file uploads)
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            content = request.form.get('content')
            file = request.files.get('file')
        else:
            # Handle JSON data
            data = request.get_json()
            content = data.get('content') if data else None
            file = None
        
        if not content:
            return jsonify({'error': 'Contenuto del post richiesto'}), 400
        
        if len(content) > 4000:
            return jsonify({'error': 'Il post è troppo lungo (max 4000 caratteri)'}), 400
        
        # Create post
        post = Post(
            content=content,
            user_id=user.id
        )
        
        # Handle file upload
        image_filename = None
        video_filename = None
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Determine if it's an image or video
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext in {'png', 'jpg', 'jpeg', 'gif'}:
                image_filename = unique_filename
                post.image_filename = image_filename
            elif file_ext in {'mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv'}:
                video_filename = unique_filename
                post.video_filename = video_filename
        
        db.session.add(post)
        db.session.commit()
        
        # 🔔 Crea notifiche per i top utenti attivi (primi 10)
        top_users = User.query.filter(User.id != user.id).limit(10).all()
        for top_user in top_users:
            create_notification(
                top_user.id,
                'new_post',
                'Nuovo post nella community',
                f'{user.nome} {user.cognome} ha pubblicato qualcosa di interessante!',
                sender_id=user.id,
                post_id=post.id
            )
        
        return jsonify({
            'message': 'Post creato con successo!',
            'post': {
                'id': post.id,
                'content': post.content,
                'image_filename': image_filename,
                'video_filename': video_filename,
                'created_at': post.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante la creazione del post: {str(e)}'}), 500

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        post = Post.query.get_or_404(post_id)
        
        # Verifica che l'utente sia l'autore o admin
        if post.user_id != user.id and not user.is_admin:
            return jsonify({'error': 'Non autorizzato a eliminare questo post'}), 403
        
        # Rimuovi file associati se esistono
        if post.image_filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        if post.video_filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.video_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({'message': 'Post eliminato con successo'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'eliminazione: {str(e)}'}), 500

@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        post = Post.query.get_or_404(post_id)
        
        # Verifica se esiste già un like
        existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
        
        if existing_like:
            # Rimuovi like
            db.session.delete(existing_like)
            is_liked = False
        else:
            # Aggiungi like
            like = Like(user_id=user.id, post_id=post_id)
            db.session.add(like)
            is_liked = True
            
            # 🔔 Crea notifica per l'autore del post (se non è lo stesso utente)
            if post.author.id != user.id:
                create_notification(
                    post.author.id,
                    'like',
                    'Nuovo like ricevuto!',
                    f'{user.nome} {user.cognome} ha messo mi piace al tuo post',
                    sender_id=user.id,
                    post_id=post_id
                )
        
        db.session.commit()
        
        # Conta totale likes
        likes_count = Like.query.filter_by(post_id=post_id).count()
        
        return jsonify({
            'likes_count': likes_count,
            'is_liked': is_liked
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'operazione: {str(e)}'}), 500

# ======================================== 
# COMMENTS API ROUTES 
# ======================================== 

@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    try:
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'author': {
                    'id': comment.author.id,
                    'username': comment.author.username,
                    'nome': comment.author.nome,
                    'cognome': comment.author.cognome,
                    'avatar_color': comment.author.avatar_color,
                    'initials': comment.author.initials
                }
            })
        
        return jsonify({'comments': comments_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento dei commenti: {str(e)}'}), 500

@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def create_comment(post_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        data = request.get_json()
        content = data.get('content')
        
        if not content:
            return jsonify({'error': 'Contenuto del commento richiesto'}), 400
        
        if len(content) > 1000:
            return jsonify({'error': 'Commento troppo lungo (max 1000 caratteri)'}), 400
        
        post = Post.query.get_or_404(post_id)
        
        comment = Comment(
            content=content,
            user_id=user.id,
            post_id=post_id
        )
        
        db.session.add(comment)
        db.session.commit()
        
        # 🔔 Crea notifica per l'autore del post (se non è lo stesso utente)
        if post.author.id != user.id:
            create_notification(
                post.author.id,
                'comment',
                'Nuovo commento ricevuto!',
                f'{user.nome} {user.cognome} ha commentato il tuo post',
                sender_id=user.id,
                post_id=post_id,
                comment_id=comment.id
            )
        
        return jsonify({
            'message': 'Commento aggiunto con successo!',
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante la creazione del commento: {str(e)}'}), 500

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        comment = Comment.query.get_or_404(comment_id)
        
        # Verifica che l'utente sia l'autore o admin
        if comment.user_id != user.id and not user.is_admin:
            return jsonify({'error': 'Non autorizzato a eliminare questo commento'}), 403
        
        db.session.delete(comment)
        db.session.commit()
        
        return jsonify({'message': 'Commento eliminato con successo'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'eliminazione: {str(e)}'}), 500

# ======================================== 
# 🎓 COURSES API ROUTES - NUOVO SISTEMA COMPLETO
# ======================================== 

@app.route('/api/courses', methods=['GET'])
def get_courses():
    try:
        current_user = get_current_user()
        
        # Filtri dalla query string
        category = request.args.get('category')
        skill_level = request.args.get('skill_level')
        course_type = request.args.get('type')
        free_only = request.args.get('free_only') == 'true'
        
        # Build query
        query = Course.query
        
        if category:
            query = query.filter(Course.category == category)
        if skill_level:
            query = query.filter(Course.skill_level == skill_level)
        if course_type:
            query = query.filter(Course.course_type == course_type)
        if free_only:
            query = query.filter(Course.price == 0)
        
        # Non mostrare corsi privati a utenti non iscritti
        if not current_user or not current_user.is_admin:
            query = query.filter(Course.is_private == False)
        
        courses = query.order_by(Course.created_at.desc()).all()
        
        courses_data = []
        for course in courses:
            # Conta iscrizioni
            enrolled_count = Enrollment.query.filter_by(course_id=course.id).count()
            
            # Conta lezioni
            lessons_count = Lesson.query.filter_by(course_id=course.id).count()
            
            # Verifica se l'utente corrente è iscritto
            is_enrolled = False
            if current_user:
                is_enrolled = Enrollment.query.filter_by(
                    user_id=current_user.id,
                    course_id=course.id
                ).first() is not None
            
            courses_data.append({
                'id': course.id,
                'title': course.title,
                'description': course.description,
                'category': course.category,
                'course_type': course.course_type,
                'skill_level': course.skill_level,
                'duration_hours': course.duration_hours,
                'thumbnail_url': course.thumbnail_url,
                'price': course.price,
                'is_private': course.is_private,
                'created_at': course.created_at.isoformat(),
                'enrolled_count': enrolled_count,
                'lessons_count': lessons_count,
                'is_enrolled': is_enrolled,
                'total_lessons': lessons_count,  # Compatibility
                'instructor': {
                    'id': course.instructor.id,
                    'nome': course.instructor.nome,
                    'cognome': course.instructor.cognome,
                    'username': course.instructor.username
                } if course.instructor else None
            })
        
        return jsonify({
            'courses': courses_data,
            'total': len(courses_data)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento dei corsi: {str(e)}'}), 500

@app.route('/api/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    try:
        current_user = get_current_user()
        
        course = Course.query.get_or_404(course_id)
        
        # Verifica accesso a corsi privati
        if course.is_private and (not current_user or not current_user.is_admin):
            return jsonify({'error': 'Corso non disponibile'}), 403
        
        # Conta iscrizioni
        enrolled_count = Enrollment.query.filter_by(course_id=course.id).count()
        
        # Verifica se l'utente corrente è iscritto
        is_enrolled = False
        enrollment = None
        if current_user:
            enrollment = Enrollment.query.filter_by(
                user_id=current_user.id,
                course_id=course.id
            ).first()
            is_enrolled = enrollment is not None
        
        course_data = {
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'category': course.category,
            'course_type': course.course_type,
            'skill_level': course.skill_level,
            'duration_hours': course.duration_hours,
            'thumbnail_url': course.thumbnail_url,
            'price': course.price,
            'is_private': course.is_private,
            'created_at': course.created_at.isoformat(),
            'enrolled_count': enrolled_count,
            'is_enrolled': is_enrolled,
            'progress_percentage': enrollment.progress_percentage if enrollment else 0,
            'instructor': {
                'id': course.instructor.id,
                'nome': course.instructor.nome,
                'cognome': course.instructor.cognome,
                'username': course.instructor.username
            } if course.instructor else None
        }
        
        return jsonify({'course': course_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento del corso: {str(e)}'}), 500

@app.route('/api/courses', methods=['POST'])
def create_course():
    user = require_admin()
    if isinstance(user, tuple):
        return user
    
    try:
        data = request.get_json()
        
        # Validazione
        required_fields = ['title', 'description', 'category', 'skill_level']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} richiesto'}), 400
        
        course = Course(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            course_type=data.get('course_type', 'CORSI'),
            skill_level=data['skill_level'],
            duration_hours=data.get('duration_hours', 0),
            thumbnail_url=data.get('thumbnail_url'),
            price=data.get('price', 0.0),
            is_private=data.get('is_private', False),
            instructor_id=user.id
        )
        
        db.session.add(course)
        db.session.commit()
        
        # 🔔 Crea notifiche per tutti gli utenti
        all_users = User.query.filter(User.id != user.id).all()
        for recipient in all_users:
            create_notification(
                recipient.id,
                'new_course',
                'Nuovo corso disponibile!',
                f'È disponibile un nuovo corso: "{course.title}" in {course.category}',
                sender_id=user.id,
                course_id=course.id
            )
        
        return jsonify({
            'message': 'Corso creato con successo!',
            'course': {
                'id': course.id,
                'title': course.title,
                'category': course.category
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante la creazione del corso: {str(e)}'}), 500

@app.route('/api/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    user = require_admin()
    if isinstance(user, tuple):
        return user
    
    try:
        course = Course.query.get_or_404(course_id)
        
        db.session.delete(course)
        db.session.commit()
        
        return jsonify({'message': 'Corso eliminato con successo'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'eliminazione: {str(e)}'}), 500

# ======================================== 
# 🎓 ENROLLMENTS API ROUTES - NUOVO
# ======================================== 

@app.route('/api/courses/<int:course_id>/enroll', methods=['POST'])
def enroll_course(course_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        course = Course.query.get_or_404(course_id)
        
        # Verifica se già iscritto
        existing_enrollment = Enrollment.query.filter_by(
            user_id=user.id,
            course_id=course_id
        ).first()
        
        if existing_enrollment:
            return jsonify({'error': 'Già iscritto a questo corso'}), 400
        
        # Crea iscrizione
        enrollment = Enrollment(
            user_id=user.id,
            course_id=course_id
        )
        
        db.session.add(enrollment)
        db.session.commit()
        
        # 🔔 Crea notifica per l'istruttore
        if course.instructor and course.instructor.id != user.id:
            create_notification(
                course.instructor.id,
                'course_enrollment',
                'Nuova iscrizione al corso!',
                f'{user.nome} {user.cognome} si è iscritto al tuo corso "{course.title}"',
                sender_id=user.id,
                course_id=course_id
            )
        
        return jsonify({
            'message': 'Iscrizione completata con successo!',
            'enrollment_id': enrollment.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'iscrizione: {str(e)}'}), 500

# ======================================== 
# 🎓 LESSONS API ROUTES - NUOVO
# ======================================== 

@app.route('/api/courses/<int:course_id>/lessons', methods=['GET'])
def get_course_lessons(course_id):
    try:
        current_user = get_current_user()
        
        course = Course.query.get_or_404(course_id)
        
        # Verifica se l'utente è iscritto al corso
        is_enrolled = False
        if current_user:
            is_enrolled = Enrollment.query.filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first() is not None
        
        lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order_index).all()
        
        lessons_data = []
        for lesson in lessons:
            # Verifica se l'utente ha completato questa lezione
            is_completed = False
            if current_user:
                is_completed = LessonProgress.query.filter_by(
                    user_id=current_user.id,
                    lesson_id=lesson.id
                ).first() is not None
            
            # Prima lezione sempre accessibile, le altre solo se iscritto
            is_accessible = lesson.is_free or is_enrolled or (current_user and current_user.is_admin)
            
            lessons_data.append({
                'id': lesson.id,
                'title': lesson.title,
                'content': lesson.content if is_accessible else None,
                'order_index': lesson.order_index,
                'duration': lesson.duration_minutes,
                'is_free': lesson.is_free,
                'video_url': lesson.video_url if is_accessible else None,
                'created_at': lesson.created_at.isoformat(),
                'is_completed': is_completed,
                'is_accessible': is_accessible
            })
        
        return jsonify({'lessons': lessons_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento delle lezioni: {str(e)}'}), 500

@app.route('/api/lessons/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id):
    try:
        current_user = get_current_user()
        
        lesson = Lesson.query.get_or_404(lesson_id)
        course = lesson.course
        
        # Verifica accesso
        is_enrolled = False
        if current_user:
            is_enrolled = Enrollment.query.filter_by(
                user_id=current_user.id,
                course_id=course.id
            ).first() is not None
        
        # Verifica se l'utente può accedere a questa lezione
        can_access = lesson.is_free or is_enrolled or (current_user and current_user.is_admin)
        
        if not can_access:
            return jsonify({'error': 'Accesso alla lezione richiede iscrizione al corso'}), 403
        
        # Verifica se completata
        is_completed = False
        if current_user:
            is_completed = LessonProgress.query.filter_by(
                user_id=current_user.id,
                lesson_id=lesson_id
            ).first() is not None
        
        lesson_data = {
            'id': lesson.id,
            'title': lesson.title,
            'content': lesson.content,
            'order_index': lesson.order_index,
            'duration_minutes': lesson.duration_minutes,
            'is_free': lesson.is_free,
            'video_url': lesson.video_url,
            'created_at': lesson.created_at.isoformat(),
            'is_completed': is_completed,
            'course': {
                'id': course.id,
                'title': course.title
            }
        }
        
        return jsonify({'lesson': lesson_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento della lezione: {str(e)}'}), 500

@app.route('/api/lessons/<int:lesson_id>/complete', methods=['POST'])
def complete_lesson(lesson_id):
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        lesson = Lesson.query.get_or_404(lesson_id)
        course = lesson.course
        
        # Verifica iscrizione al corso
        enrollment = Enrollment.query.filter_by(
            user_id=user.id,
            course_id=course.id
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Devi essere iscritto al corso per completare le lezioni'}), 403
        
        # Verifica se già completata
        existing_progress = LessonProgress.query.filter_by(
            user_id=user.id,
            lesson_id=lesson_id
        ).first()
        
        if existing_progress:
            return jsonify({'error': 'Lezione già completata'}), 400
        
        # Crea record progresso
        progress = LessonProgress(
            user_id=user.id,
            lesson_id=lesson_id,
            time_spent_minutes=lesson.duration_minutes
        )
        
        db.session.add(progress)
        
        # Aggiorna progresso del corso
        total_lessons = Lesson.query.filter_by(course_id=course.id).count()
        completed_lessons = LessonProgress.query.join(Lesson).filter(
            LessonProgress.user_id == user.id,
            Lesson.course_id == course.id
        ).count() + 1  # +1 per la lezione appena completata
        
        progress_percentage = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0
        enrollment.progress_percentage = progress_percentage
        
        # Se corso completato al 100%
        if progress_percentage >= 100 and not enrollment.completed_at:
            enrollment.completed_at = datetime.utcnow()
            
            # 🔔 Notifica di completamento corso
            create_system_notification(
                user.id,
                'course_completed',
                'Corso completato!',
                f'Complimenti! Hai completato il corso "{course.title}". Hai guadagnato nuove competenze!'
            )
            
            # 🔔 Notifica all'istruttore
            if course.instructor and course.instructor.id != user.id:
                create_notification(
                    course.instructor.id,
                    'course_completed',
                    'Studente ha completato il corso!',
                    f'{user.nome} {user.cognome} ha completato il corso "{course.title}"',
                    sender_id=user.id,
                    course_id=course.id
                )
        else:
            # 🔔 Notifica progresso all'istruttore
            if course.instructor and course.instructor.id != user.id:
                create_notification(
                    course.instructor.id,
                    'lesson_completed',
                    'Progresso studente',
                    f'{user.nome} {user.cognome} ha completato la lezione "{lesson.title}"',
                    sender_id=user.id,
                    course_id=course.id
                )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lezione completata con successo!',
            'progress_percentage': progress_percentage,
            'course_completed': progress_percentage >= 100
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante il completamento: {str(e)}'}), 500

# ======================================== 
# 🔔 NOTIFICATIONS API ROUTES 
# ======================================== 

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        notifications = Notification.query.filter_by(
            recipient_id=user.id
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        notifications_data = []
        for notification in notifications:
            notification_data = {
                'id': notification.id,
                'type': notification.type,
                'title': notification.title,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'time_ago': time_ago(notification.created_at)
            }
            
            # Aggiungi info sender se presente
            if notification.sender:
                notification_data['sender'] = {
                    'id': notification.sender.id,
                    'nome': notification.sender.nome,
                    'cognome': notification.sender.cognome,
                    'username': notification.sender.username,
                    'avatar_color': notification.sender.avatar_color,
                    'initials': notification.sender.initials
                }
            
            notifications_data.append(notification_data)
        
        # Conta notifiche non lette
        unread_count = Notification.query.filter_by(
            recipient_id=user.id,
            is_read=False
        ).count()
        
        return jsonify({
            'notifications': notifications_data,
            'unread_count': unread_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento delle notifiche: {str(e)}'}), 500

@app.route('/api/notifications/unread-count', methods=['GET'])
def get_unread_notifications_count():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        unread_count = Notification.query.filter_by(
            recipient_id=user.id,
            is_read=False
        ).count()
        
        return jsonify({'unread_count': unread_count}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il conteggio: {str(e)}'}), 500

@app.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if notification_ids:
            # Segna specifiche notifiche come lette
            Notification.query.filter(
                Notification.id.in_(notification_ids),
                Notification.recipient_id == user.id
            ).update({'is_read': True}, synchronize_session=False)
        else:
            # Segna tutte le notifiche come lette
            Notification.query.filter_by(
                recipient_id=user.id,
                is_read=False
            ).update({'is_read': True}, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({'message': 'Notifiche segnate come lette'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'aggiornamento: {str(e)}'}), 500

# ======================================== 
# OTHER API ROUTES 
# ======================================== 

@app.route('/api/upload', methods=['POST'])
def upload_file():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nessun file fornito'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nessun file selezionato'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            return jsonify({
                'message': 'File caricato con successo',
                'filename': unique_filename,
                'url': f'/uploads/{unique_filename}'
            }), 200
        else:
            return jsonify({'error': 'Tipo di file non supportato'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Errore durante l\'upload: {str(e)}'}), 500

@app.route('/api/users')
def get_users():
    try:
        limit = int(request.args.get('limit', 10))
        users = User.query.order_by(User.created_at.desc()).limit(limit).all()
        
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'nome': user.nome,
                'cognome': user.cognome,
                'corso': user.corso,
                'avatar_color': user.avatar_color,
                'initials': user.initials,
                'created_at': user.created_at.isoformat()
            })
        
        return jsonify({'users': users_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento degli utenti: {str(e)}'}), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        reviews = Review.query.order_by(Review.created_at.desc()).all()
        
        reviews_data = []
        for review in reviews:
            reviews_data.append({
                'id': review.id,
                'text': review.text,
                'rating': review.rating,
                'location': review.location,
                'photo': review.photo_url,
                'created_at': review.created_at.isoformat(),
                'name': f"{review.author.nome} {review.author.cognome}",
                'course': f"{review.author.corso} • {review.location or 'Italia'}"
            })
        
        return jsonify({'reviews': reviews_data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore durante il caricamento delle recensioni: {str(e)}'}), 500

@app.route('/api/reviews', methods=['POST'])
def create_review():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        data = request.get_json()
        
        review = Review(
            text=data['text'],
            rating=data['rating'],
            location=data.get('location'),
            photo_url=data.get('photo_url'),
            user_id=user.id
        )
        
        db.session.add(review)
        db.session.commit()
        
        return jsonify({'message': 'Recensione creata con successo!'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante la creazione della recensione: {str(e)}'}), 500

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    user = require_auth()
    if isinstance(user, tuple):
        return user
    
    try:
        data = request.get_json()
        
        # Salva info per statistiche
        deleted_account = DeletedAccount(
            username=user.username,
            email=user.email,
            deletion_reason=data.get('reason'),
            feedback=data.get('feedback')
        )
        
        db.session.add(deleted_account)
        
        # Elimina l'utente (cascade eliminerà post, commenti, etc.)
        db.session.delete(user)
        db.session.commit()
        
        # Logout
        session.pop('user_id', None)
        
        return jsonify({'message': 'Account eliminato con successo'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'eliminazione: {str(e)}'}), 500

@app.route('/api/health')
def health_check():
    try:
        # Statistiche del sistema
        stats = {
            'status': 'healthy',
            'users_count': User.query.count(),
            'posts_count': Post.query.count(),
            'comments_count': Comment.query.count(),
            'courses_count': Course.query.count(),
            'enrollments_count': Enrollment.query.count(),
            'lessons_count': Lesson.query.count(),
            'notifications_count': Notification.query.count(),
            'reviews_count': Review.query.count()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore del sistema: {str(e)}'}), 500

# ======================================== 
# DATABASE INITIALIZATION 
# ======================================== 

def init_db():
    """Inizializza il database con dati di esempio"""
    with app.app_context():
        # Crea tutte le tabelle
        db.create_all()
        
        # Verifica se admin esiste già
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Crea account admin
            admin = User(
                username='admin',
                email='admin@courseconnect.com',
                password_hash=generate_password_hash('admin123'),
                nome='Admin',
                cognome='CourseConnect',
                corso='Amministrazione Sistema',
                bio='Amministratore principale di CourseConnect',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            
            # Crea alcuni corsi di esempio
            sample_courses = [
                {
                    'title': 'Corso Hacking Etico Completo',
                    'description': 'Impara l\'hacking etico, penetration testing e cybersecurity. Diventa un esperto della sicurezza informatica con questo corso completo che copre tutti gli aspetti del mondo della sicurezza informatica.',
                    'category': 'Cybersecurity',
                    'skill_level': 'Intermediate',
                    'duration_hours': 40,
                    'thumbnail_url': 'https://images.unsplash.com/photo-1555949963-aa79dcee981c?w=400',
                    'price': 99.99
                },
                {
                    'title': 'HTML & CSS Moderno',
                    'description': 'Impara HTML5 e CSS3 da zero. Crea siti web responsivi e moderni utilizzando le tecnologie web più avanzate. Include progetti pratici e esempi reali.',
                    'category': 'Web Development',
                    'skill_level': 'Beginner',
                    'duration_hours': 25,
                    'thumbnail_url': 'https://images.unsplash.com/photo-1627398242454-45a1465c2479?w=400',
                    'price': 0  # Gratuito
                },
                {
                    'title': 'JavaScript Avanzato',
                    'description': 'Approfondisci JavaScript con ES6+, async/await, promises, moduli e molto altro. Diventa un developer JavaScript esperto con progetti pratici.',
                    'category': 'Web Development',
                    'skill_level': 'Advanced',
                    'duration_hours': 35,
                    'thumbnail_url': 'https://images.unsplash.com/photo-1579468118864-1b9ea3c0db4a?w=400',
                    'price': 79.99
                },
                {
                    'title': 'Design UX/UI Fundamentals',
                    'description': 'Impara i principi del design UX/UI, prototipazione, ricerca utente e design thinking. Crea interfacce utente belle e funzionali.',
                    'category': 'Design',
                    'skill_level': 'Beginner',
                    'duration_hours': 30,
                    'thumbnail_url': 'https://images.unsplash.com/photo-1581291518857-4e27b48ff24e?w=400',
                    'price': 69.99
                }
            ]
            
            for course_data in sample_courses:
                course = Course(
                    instructor_id=admin.id,
                    **course_data
                )
                db.session.add(course)
            
            db.session.commit()
            
            # Aggiungi lezioni di esempio per il corso Hacking
            hacking_course = Course.query.filter_by(title='Corso Hacking Etico Completo').first()
            if hacking_course:
                sample_lessons = [
                    {
                        'title': 'Introduzione all\'Hacking Etico',
                        'content': '''# Introduzione all'Hacking Etico

## Cos'è l'Hacking Etico?

L'**hacking etico** è la pratica di testare sistemi informatici, reti e applicazioni per identificare vulnerabilità di sicurezza in modo legale e autorizzato.

### Obiettivi principali:
- Identificare vulnerabilità prima che vengano sfruttate
- Migliorare la sicurezza dei sistemi
- Proteggere dati sensibili e infrastrutture critiche

### Differenze tra Hacker Etico e Malintenzionato:

| Hacker Etico | Hacker Malintenzionato |
|---------------|------------------------|
| Autorizzazione scritta | Accesso non autorizzato |
| Scopo costruttivo | Scopo distruttivo |
| Report dettagliati | Sfruttamento delle vulnerabilità |

## Principi Fondamentali

1. **Autorizzazione**: Sempre ottenere permesso scritto
2. **Responsabilità**: Agire in modo responsabile
3. **Riservatezza**: Mantenere confidenziali le informazioni
4. **Integrità**: Non danneggiare i sistemi testati

> "Un grande potere comporta grandi responsabilità" - Questo vale anche per l'hacking etico.

## Prossimi Passi

Nella prossima lezione vedremo gli strumenti principali utilizzati nel penetration testing.''',
                        'order_index': 1,
                        'duration_minutes': 15,
                        'is_free': True  # Prima lezione sempre gratuita
                    },
                    {
                        'title': 'Strumenti di Penetration Testing',
                        'content': '''# Strumenti di Penetration Testing

## Kali Linux - La Distribuzione del Pentester

**Kali Linux** è la distribuzione Linux più utilizzata per il penetration testing, contenente oltre 600 strumenti preinstallati.

### Download e Installazione:
```bash
# Scarica da: https://www.kali.org/downloads/
# Verifica checksum:
sha256sum kali-linux-2024.1-installer-amd64.iso
```

## Strumenti Essenziali

### 1. Nmap - Network Mapper
```bash
# Scan di base
nmap 192.168.1.1

# Scan dettagliato con service detection
nmap -sS -sV -O 192.168.1.0/24

# Scan stealth
nmap -sS -T2 target.com
```

### 2. Metasploit Framework
```bash
# Avvia Metasploit
msfconsole

# Cerca exploit
search windows smb

# Usa un exploit
use exploit/windows/smb/ms17_010_eternalblue
```

### 3. Burp Suite - Web Application Testing
- **Proxy**: Intercetta traffico web
- **Spider**: Crawling automatico
- **Scanner**: Ricerca vulnerabilità
- **Repeater**: Test manuali

### 4. Wireshark - Network Analysis
Analizza il traffico di rete in tempo reale:
- Cattura pacchetti
- Analisi protocolli
- Ricostruzione sessioni

## Lab Practice

Prova questi comandi in un ambiente di test:

```bash
# Ping sweep
nmap -sn 192.168.1.0/24

# Port scan top ports
nmap --top-ports 1000 target.com

# OS fingerprinting
nmap -O target.com
```

> ⚠️ **Attenzione**: Usa questi strumenti solo su sistemi che possiedi o hai autorizzazione esplicita a testare.

## Prossima Lezione

Vedremo come eseguire reconnaissance e information gathering in modo professionale.''',
                        'order_index': 2,
                        'duration_minutes': 25,
                        'is_free': False
                    },
                    {
                        'title': 'Reconnaissance e Information Gathering',
                        'content': '''# Reconnaissance e Information Gathering

Il **reconnaissance** è la fase più importante del penetration testing. Più informazioni raccogli, maggiori sono le possibilità di successo.

## Tipi di Reconnaissance

### 1. Passive Reconnaissance
Raccolta informazioni **senza** interagire direttamente con il target:

```bash
# Whois lookup
whois target.com

# DNS enumeration
dig target.com ANY
nslookup target.com

# Google dorking
site:target.com filetype:pdf
site:target.com inurl:admin
```

### 2. Active Reconnaissance
Interazione **diretta** con il target:

```bash
# Network scanning
nmap -sS target.com

# Service enumeration
nmap -sV -sC target.com

# Web enumeration
dirb http://target.com
gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt
```

## OSINT (Open Source Intelligence)

### Strumenti OSINT:
1. **Shodan**: "Google per dispositivi IoT"
2. **Maltego**: Visualizzazione collegamenti
3. **theHarvester**: Email e subdomain discovery
4. **Recon-ng**: Framework OSINT

### theHarvester Example:
```bash
# Trova email e subdomains
theHarvester -d target.com -l 500 -b google
theHarvester -d target.com -l 500 -b bing
```

## Social Engineering Information

### Fonti di informazioni:
- **LinkedIn**: Dipendenti, tecnologie usate
- **Facebook/Instagram**: Informazioni personali
- **GitHub**: Codice sorgente, credenziali
- **Job boards**: Stack tecnologico

### Esempio di ricerca LinkedIn:
```
site:linkedin.com "target company" "system administrator"
site:linkedin.com "target company" "network engineer"
```

## DNS Enumeration Avanzato

```bash
# Zone transfer test
dig axfr @ns1.target.com target.com

# Subdomain enumeration
dnsrecon -d target.com -t brt -D /usr/share/dnsrecon/namelist.txt

# Reverse DNS lookup
dnsrecon -r 192.168.1.0/24
```

## Web Application Reconnaissance

```bash
# Technology stack identification
whatweb target.com

# Directory enumeration
dirb http://target.com
gobuster dir -u http://target.com -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt

# Subdomain enumeration
sublist3r -d target.com
```

## Best Practices

1. **Documentazione**: Registra tutto quello che trovi
2. **Organizzazione**: Usa tools come CherryTree o Obsidian
3. **Legalità**: Rispetta sempre i termini di servizio
4. **Stealth**: Usa proxy/VPN quando appropriato

## Lab Exercise

Prova questo workflow su un target autorizzato:

```bash
# 1. Basic information
whois target.com
dig target.com ANY

# 2. Subdomain discovery
sublist3r -d target.com

# 3. Technology stack
whatweb target.com

# 4. Directory enumeration (be careful with rate limiting)
dirb http://target.com -w
```

> 📝 **Homework**: Crea una checklist personalizzata per il reconnaissance basata sugli strumenti che preferisci.

## Prossima Lezione

Nella prossima lezione impareremo le tecniche di **Vulnerability Assessment** e **Exploitation**.''',
                        'order_index': 3,
                        'duration_minutes': 30,
                        'is_free': False
                    }
                ]
                
                for lesson_data in sample_lessons:
                    lesson = Lesson(
                        course_id=hacking_course.id,
                        **lesson_data
                    )
                    db.session.add(lesson)
                
                db.session.commit()
            
            # Aggiungi lezioni per HTML & CSS
            html_course = Course.query.filter_by(title='HTML & CSS Moderno').first()
            if html_course:
                html_lessons = [
                    {
                        'title': 'Introduzione a HTML5',
                        'content': '''# Introduzione a HTML5

## Cos'è HTML?

**HTML** (HyperText Markup Language) è il linguaggio di markup standard per creare pagine web.

### Struttura base:
```html
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>La mia prima pagina</title>
</head>
<body>
    <h1>Benvenuto!</h1>
    <p>Questa è la mia prima pagina HTML.</p>
</body>
</html>
```

## Novità di HTML5

### Nuovi elementi semantici:
- `<header>`: Intestazione
- `<nav>`: Navigazione  
- `<main>`: Contenuto principale
- `<article>`: Articolo
- `<section>`: Sezione
- `<aside>`: Contenuto laterale
- `<footer>`: Piè di pagina

### Esempio pratico:
```html
<header>
    <nav>
        <ul>
            <li><a href="#home">Home</a></li>
            <li><a href="#about">Chi siamo</a></li>
        </ul>
    </nav>
</header>

<main>
    <article>
        <h1>Titolo articolo</h1>
        <p>Contenuto dell'articolo...</p>
    </article>
</main>

<footer>
    <p>&copy; 2024 Il mio sito</p>
</footer>
```

## Attributi globali utili

```html
<!-- ID e classi -->
<div id="header" class="container">

<!-- Data attributes -->
<div data-user-id="123" data-role="admin">

<!-- Accessibilità -->
<img src="foto.jpg" alt="Descrizione immagine">
<button aria-label="Chiudi finestra">×</button>
```

Nella prossima lezione vedremo i form HTML5 e le loro nuove funzionalità!''',
                        'order_index': 1,
                        'duration_minutes': 20,
                        'is_free': True
                    },
                    {
                        'title': 'CSS3 e Layout Moderni',
                        'content': '''# CSS3 e Layout Moderni

## Flexbox - Layout flessibile

Flexbox rivoluziona il modo di creare layout in CSS:

```css
.container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}

.item {
    flex: 1;
    padding: 20px;
}
```

### Proprietà principali:
- `justify-content`: Allineamento orizzontale
- `align-items`: Allineamento verticale
- `flex-direction`: Direzione (row/column)
- `flex-wrap`: A capo automatico

## CSS Grid - Layout a griglia

```css
.grid-container {
    display: grid;
    grid-template-columns: 1fr 2fr 1fr;
    grid-template-rows: auto 1fr auto;
    gap: 20px;
    height: 100vh;
}

.header { grid-area: 1 / 1 / 2 / 4; }
.sidebar { grid-area: 2 / 1 / 3 / 2; }
.main { grid-area: 2 / 2 / 3 / 3; }
.aside { grid-area: 2 / 3 / 3 / 4; }
.footer { grid-area: 3 / 1 / 4 / 4; }
```

## CSS Custom Properties (Variabili)

```css
:root {
    --primary-color: #3498db;
    --secondary-color: #e74c3c;
    --font-size: 16px;
}

.button {
    background-color: var(--primary-color);
    font-size: var(--font-size);
}
```

## Responsive Design

```css
/* Mobile first */
.container {
    width: 100%;
    padding: 10px;
}

/* Tablet */
@media (min-width: 768px) {
    .container {
        max-width: 750px;
        margin: 0 auto;
    }
}

/* Desktop */
@media (min-width: 1024px) {
    .container {
        max-width: 1200px;
        padding: 20px;
    }
}
```

Prossima lezione: JavaScript per interattività!''',
                        'order_index': 2,
                        'duration_minutes': 25,
                        'is_free': False
                    }
                ]
                
                for lesson_data in html_lessons:
                    lesson = Lesson(
                        course_id=html_course.id,
                        **lesson_data
                    )
                    db.session.add(lesson)
                
                db.session.commit()
            
            print("✅ Database inizializzato con admin e corsi di esempio!")
            print("👤 Admin: username='admin', password='admin123'")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
