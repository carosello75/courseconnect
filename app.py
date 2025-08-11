# ========================================
# CourseConnect - Social Network per Corsisti  
# app.py - Versione Sicura (Senza Chat)
# ========================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# Inizializzazione Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'courseconnect-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///courseconnect.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inizializzazione Database
db = SQLAlchemy(app)

# ========================================
# MODELLI DATABASE
# ========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    corso = db.Column(db.String(200), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, default='')
    avatar_url = db.Column(db.String(500), default='')
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relazioni
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_avatar_color(self):
        """Genera colore avatar basato su username"""
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        return colors[len(self.username) % len(colors)]
    
    def get_initials(self):
        """Ottieni iniziali per avatar"""
        return f"{self.nome[0]}{self.cognome[0]}".upper() if self.nome and self.cognome else self.username[0].upper()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nome': self.nome,
            'cognome': self.cognome,
            'corso': self.corso,
            'bio': self.bio,
            'avatar_color': self.get_avatar_color(),
            'initials': self.get_initials(),
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat()
        }

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relazioni
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_likes_count(self):
        return self.likes.count()
    
    def is_liked_by(self, user):
        if not user:
            return False
        return self.likes.filter_by(user_id=user.id).first() is not None
    
    def to_dict(self, current_user=None):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            'author': self.author.to_dict() if self.author else {},
            'likes_count': self.get_likes_count(),
            'is_liked': self.is_liked_by(current_user),
            'comments_count': self.comments.count()
        }

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Keys
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    
    # Constraint per evitare like duplicati
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

# ========================================
# UTILITY FUNCTIONS
# ========================================

def get_current_user():
    """Ottieni utente corrente dalla sessione"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

# ========================================
# API ROUTES
# ========================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check per monitoring"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'users_count': User.query.count(),
            'posts_count': Post.query.count(),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/api/register', methods=['POST'])
def register():
    """Registrazione nuovo utente"""
    try:
        data = request.get_json()
        
        # Validazione dati
        if not all(k in data for k in ['username', 'email', 'nome', 'cognome', 'corso', 'password']):
            return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
        
        # Verifica username/email univoci
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username già in uso'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email già registrata'}), 400
        
        # Crea nuovo utente
        user = User(
            username=data['username'],
            email=data['email'],
            nome=data['nome'],
            cognome=data['cognome'],
            corso=data['corso'],
            bio=data.get('bio', '')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Login automatico
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'Registrazione completata',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore registrazione: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Login utente"""
    try:
        data = request.get_json()
        
        if not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Username e password richiesti'}), 400
        
        # Trova utente
        user = User.query.filter_by(username=data['username']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Credenziali non valide'}), 401
        
        # Crea sessione
        session['user_id'] = user.id
        
        return jsonify({
            'message': 'Login effettuato',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore login: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout utente"""
    session.pop('user_id', None)
    return jsonify({'message': 'Logout effettuato'})

@app.route('/api/me', methods=['GET'])
def get_current_user_info():
    """Informazioni utente corrente"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Non autenticato'}), 401
    
    return jsonify({'user': user.to_dict()})

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Ottieni feed post"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Paginazione post
        posts = Post.query.order_by(Post.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        current_user = get_current_user()
        
        return jsonify({
            'posts': [post.to_dict(current_user) for post in posts.items],
            'has_next': posts.has_next,
            'has_prev': posts.has_prev,
            'page': page,
            'total': posts.total
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore caricamento post: {str(e)}'}), 500

@app.route('/api/posts', methods=['POST'])
def create_post():
    """Crea nuovo post"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Login richiesto'}), 401
        
        data = request.get_json()
        
        if not data.get('content') or not data['content'].strip():
            return jsonify({'error': 'Contenuto post richiesto'}), 400
        
        if len(data['content']) > 2000:
            return jsonify({'error': 'Post troppo lungo (max 2000 caratteri)'}), 400
        
        # Crea post
        post = Post(
            content=data['content'].strip(),
            user_id=user.id
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            'message': 'Post creato',
            'post': post.to_dict(user)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore creazione post: {str(e)}'}), 500

@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    """Metti/Togli like a post"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Login richiesto'}), 401
        
        post = Post.query.get_or_404(post_id)
        
        # Verifica se già messo like
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
        
        return jsonify({
            'action': action,
            'likes_count': post.get_likes_count(),
            'is_liked': post.is_liked_by(user)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore like: {str(e)}'}), 500

# ========================================
# WEB ROUTES
# ========================================

@app.route('/')
def home():
    """Homepage"""
    return render_template('index.html')

# ========================================
# DATABASE SETUP
# ========================================

def create_tables():
    """Crea tabelle database"""
    with app.app_context():
        db.create_all()
        
        # Crea admin se non esiste
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@courseconnect.it',
                nome='Admin',
                cognome='CourseConnect',
                corso='Amministratore',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Utenti esempio
            users_data = [
                {
                    'username': 'marco_dev',
                    'email': 'marco@example.com',
                    'nome': 'Marco',
                    'cognome': 'Rossi',
                    'corso': 'Sviluppo Web Full-Stack',
                    'bio': '🚀 Appassionato di tecnologia e coding'
                },
                {
                    'username': 'sofia_design',
                    'email': 'sofia@example.com',
                    'nome': 'Sofia',
                    'cognome': 'Bianchi',
                    'corso': 'UI/UX Design',
                    'bio': '🎨 Designer creativa con passione per l\'estetica'
                }
            ]
            
            for user_data in users_data:
                user = User(**user_data)
                user.set_password('password123')
                db.session.add(user)
            
            db.session.commit()
            
            # Post esempio
            posts_data = [
                {
                    'content': '🎉 Benvenuti in CourseConnect! Il social network dedicato ai corsisti. Condividiamo esperienze, progetti e cresciamo insieme! 🚀',
                    'user_id': admin.id
                },
                {
                    'content': '💻 Oggi ho completato il mio primo progetto React! Le sensazioni sono incredibili quando vedi il codice prendere vita nel browser. Chi altro sta imparando React?',
                    'user_id': 2  # marco_dev
                }
            ]
            
            for post_data in posts_data:
                post = Post(**post_data)
                db.session.add(post)
            
            db.session.commit()
            print("✅ Database inizializzato con dati esempio!")

# ========================================
# APP STARTUP
# ========================================

if __name__ == '__main__':
    create_tables()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚀 CourseConnect avviato su porta {port}")
    print(f"📊 Admin: admin / admin123")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
