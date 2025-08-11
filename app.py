# ========================================
# CourseConnect - Social Network per Corsisti
# app.py - Versione Production-safe (senza chat)
# ========================================

from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# ========================================
# FLASK APP & CONFIG
# ========================================

app = Flask(__name__)

# Secret key: override in produzione con env var
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'courseconnect-secret-key-2024')

# Normalizza DATABASE_URL (Render Postgres spesso usa "postgres://")
db_url = os.environ.get('DATABASE_URL', 'sqlite:///courseconnect.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLite + worker async: disabilita check_same_thread
if db_url.startswith('sqlite'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"connect_args": {"check_same_thread": False}}

# Cookie session un po' più sicuri
app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
app.config.setdefault('SESSION_COOKIE_SECURE', True)  # True su HTTPS (Render)

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

    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_avatar_color(self):
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        return colors[len(self.username) % len(colors)]

    def get_initials(self):
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
            'created_at': (self.created_at or datetime.utcnow()).isoformat()
        }


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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
            'created_at': (self.created_at or datetime.utcnow()).isoformat(),
            'author': self.author.to_dict() if self.author else {},
            'likes_count': self.get_likes_count(),
            'is_liked': self.is_liked_by(current_user),
            'comments_count': self.comments.count()
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
            'created_at': (self.created_at or datetime.utcnow()).isoformat(),
            'author': self.author.to_dict() if self.author else {}
        }


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)


# ========================================
# UTILITY
# ========================================

def get_current_user():
    """Ottieni utente corrente dalla sessione"""
    uid = session.get('user_id')
    if not uid:
        return None
    return db.session.get(User, uid)


def _seed_data():
    """Popola dati demo in modo idempotente."""
    created_something = False

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
        created_something = True

    examples = [
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
    for u in examples:
        if not User.query.filter_by(username=u['username']).first():
            user = User(**u)
            user.set_password('password123')
            db.session.add(user)
            created_something = True

    if created_something:
        db.session.commit()

    if Post.query.count() == 0:
        admin = User.query.filter_by(username='admin').first()
        marco = User.query.filter_by(username='marco_dev').first()
        demo_posts = [
            {
                'content': '🎉 Benvenuti in CourseConnect! Il social network dedicato ai corsisti. Condividiamo esperienze, progetti e cresciamo insieme! 🚀',
                'user_id': admin.id if admin else None
            },
            {
                'content': '💻 Oggi ho completato il mio primo progetto React! Le sensazioni sono incredibili quando vedi il codice prendere vita nel browser. Chi altro sta imparando React?',
                'user_id': (marco or admin).id if (marco or admin) else None
            }
        ]
        for p in demo_posts:
            if p['user_id'] is not None:
                db.session.add(Post(**p))
        db.session.commit()


def create_tables():
    """Crea tabelle database e fa seed idempotente."""
    db.create_all()
    _seed_data()


# ========================================
# API ROUTES
# ========================================

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'users_count': User.query.count(),
            'posts_count': Post.query.count(),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500


@app.route('/api/init-db', methods=['GET'])
def init_database():
    try:
        create_tables()
        return jsonify({
            'status': 'success',
            'message': 'Database inizializzato/aggiornato con successo!',
            'users_count': User.query.count(),
            'posts_count': Post.query.count(),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}), 500


@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json(silent=True) or {}
        required = ['username', 'email', 'nome', 'cognome', 'corso', 'password']
        if not all(data.get(k) for k in required):
            return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
        if len(data['password']) < 6:
            return jsonify({'error': 'La password deve avere almeno 6 caratteri'}), 400
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username già in uso'}), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email già registrata'}), 400

        user = User(
            username=data['username'].strip(),
            email=data['email'].strip(),
            nome=data['nome'].strip(),
            cognome=data['cognome'].strip(),
            corso=data['corso'].strip(),
            bio=(data.get('bio') or '').strip()
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return jsonify({'message': 'Registrazione completata', 'user': user.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore registrazione: {str(e)}'}), 500


@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json(silent=True) or {}
        if not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Username e password richiesti'}), 400
        user = User.query.filter_by(username=data['username']).first()
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Credenziali non valide'}), 401
        session['user_id'] = user.id
        return jsonify({'message': 'Login effettuato', 'user': user.to_dict()})
    except Exception as e:
        return jsonify({'error': f'Errore login: {str(e)}'}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logout effettuato'})


@app.route('/api/me', methods=['GET'])
def get_current_user_info():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Non autenticato'}), 401
    return jsonify({'user': user.to_dict()})


def _paginate_posts(page, per_page):
    try:
        return Post.query.order_by(Post.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    except AttributeError:
        stmt = db.select(Post).order_by(Post.created_at.desc())
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        posts = _paginate_posts(page, per_page)
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
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Login richiesto'}), 401
        data = request.get_json(silent=True) or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'error': 'Contenuto post richiesto'}), 400
        if len(content) > 2000:
            return jsonify({'error': 'Post troppo lungo (max 2000 caratteri)'}), 400
        post = Post(content=content, user_id=user.id)
        db.session.add(post)
        db.session.commit()
        return jsonify({'message': 'Post creato', 'post': post.to_dict(user)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore creazione post: {str(e)}'}), 500


@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Login richiesto'}), 401
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'error': 'Post non trovato'}), 404
        existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
        if existing_like:
            db.session.delete(existing_like)
            action = 'removed'
        else:
            db.session.add(Like(user_id=user.id, post_id=post_id))
            action = 'added'
        db.session.commit()
        return jsonify({'action': action, 'likes_count': post.get_likes_count(), 'is_liked': post.is_liked_by(user)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore like: {str(e)}'}), 500


# ========================================
# WEB ROUTES
# ========================================

@app.route('/')
def home():
    return render_template('index.html')


# ========================================
# STARTUP: crea tabelle anche con gunicorn
# ========================================

with app.app_context():
    create_tables()


# ========================================
# DEV ENTRYPOINT (esecuzione locale)
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f"🚀 CourseConnect avviato su porta {port}")
    print(f"📊 Admin: admin / admin123")
    app.run(host='0.0.0.0', port=port, debug=debug)
