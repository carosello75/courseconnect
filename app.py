# ========================================
# CourseConnect - Social Network per Corsisti  
# app.py - Backend Flask Completo
# ========================================

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os, json

# ========================================
# FLASK APP & CONFIG
# ========================================

app = Flask(__name__)

# Secret key (in produzione sovrascrivi con env var)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'courseconnect-secret-key-2024')

# --- DATABASE_URL ---
# Default: SQLite in path ASSOLUTO nella working dir (evita "readonly database" su Render)
default_sqlite_path = os.path.join(os.getcwd(), 'courseconnect.db')
db_url = os.environ.get('DATABASE_URL', f'sqlite:///{default_sqlite_path}')

# Render Postgres spesso usa "postgres://", SQLAlchemy vuole "postgresql+psycopg2://"
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Engine options (pool, keep-alive)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
app.config['SQLALCHEMY_ENGINE_OPTIONS'].update({
    'pool_pre_ping': True,
    'pool_recycle': 300,
})

# SQLite + worker async: disabilita check_same_thread
if db_url.startswith('sqlite'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'].setdefault('connect_args', {})['check_same_thread'] = False

# Cookie di sessione più sicuri (su Render è HTTPS)
app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
app.config.setdefault('SESSION_COOKIE_SECURE', True)

# Uploads (immagini)
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            'avatar_url': self.avatar_url,
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
    attachments = db.relationship('PostAttachment', backref='post', lazy='dynamic', cascade='all, delete-orphan')

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
            'comments_count': self.comments.count(),
            'attachments': [
                {
                    'id': a.id,
                    'type': a.type,
                    'url': a.url,
                    'filename': a.filename,
                    'size': a.size
                } for a in self.attachments.order_by(PostAttachment.created_at.asc()).all()
            ]
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


class PostAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(20), default='image')  # image, file in futuro
    url = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), default='')
    size = db.Column(db.Integer, default=0)

    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

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

    # Post demo (solo se non ce ne sono)
    if Post.query.count() == 0:
        admin = User.query.filter_by(username='admin').first()
        marco = User.query.filter_by(username='marco_dev').first()
        demo_posts = [
            {
                'content': '🎉 Benvenuti in CourseConnect! Il social network dedicato ai corsisti. Condividiamo esperienze, progetti e cresciamo insieme! 🚀',
                'user_id': admin.id if admin else None
            },
            {
                'content': '```js\nconsole.log("Ciao CourseConnect!")\n```',
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


def _payload():
    """
    Estrae i dati sia da JSON che da form-data/x-www-form-urlencoded
    e normalizza chiavi alternative dal frontend.
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
    elif request.form:
        data = request.form.to_dict()
    else:
        try:
            data = json.loads((request.data or b'').decode('utf-8') or '{}')
        except Exception:
            data = {}

    # Alias comuni (inglese -> italiano)
    alias = {
        'firstName': 'nome',
        'lastName': 'cognome',
        'course': 'corso',
        'bioText': 'bio',
        'password1': 'password',
        'password_confirm': 'password',
    }
    for k, v in list(data.items()):
        if k in alias and alias[k] not in data:
            data[alias[k]] = v

    # Trim stringhe
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = v.strip()

    return data


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========================================
# API ROUTES
# ========================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check per monitoring"""
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
    """Inizializza/ri-seeda database (idempotente)"""
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
    """Registrazione nuovo utente (accetta JSON o form, con alias)"""
    try:
        data = _payload()
        required = ['username', 'email', 'nome', 'cognome', 'corso', 'password']
        missing = [k for k in required if not (data.get(k) or '').strip()]
        if missing:
            return jsonify({'error': 'Tutti i campi sono obbligatori', 'missing_fields': missing}), 400
        if len(data['password']) < 6:
            return jsonify({'error': 'La password deve avere almeno 6 caratteri'}), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username già in uso'}), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email già registrata'}), 400

        user = User(
            username=data['username'],
            email=data['email'],
            nome=data['nome'],
            cognome=data['cognome'],
            corso=data['corso'],
            bio=(data.get('bio') or '')
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
    """Login utente (accetta JSON o form)"""
    try:
        data = _payload()
        username = (data.get('username') or '')
        password = (data.get('password') or '')
        if not username or not password:
            return jsonify({'error': 'Username e password richiesti'}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({'error': 'Credenziali non valide'}), 401

        session['user_id'] = user.id
        return jsonify({'message': 'Login effettuato', 'user': user.to_dict()})
    except Exception as e:
        return jsonify({'error': f'Errore login: {str(e)}'}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout utente"""
    session.pop('user_id', None)
    return jsonify({'message': 'Logout effettuato'})


@app.route('/api/me', methods=['GET'])
def get_current_user_info():
    """
    Informazioni utente corrente.
    Evitiamo 401 in console: se non autenticato, 200 con authenticated:false.
    """
    user = get_current_user()
    if not user:
        return jsonify({'authenticated': False, 'user': None})
    return jsonify({'authenticated': True, 'user': user.to_dict()})


# ======= USERS API =======
@app.route('/api/users', methods=['GET'])
def list_users():
    """Elenco ultimi utenti attivi (per sidebar)."""
    try:
        limit = request.args.get('limit', 20, type=int)
        q = (request.args.get('q') or '').strip()

        query = User.query.filter_by(is_active=True)
        if q:
            like = f"%{q.lower()}%"
            query = query.filter(
                db.or_(
                    db.func.lower(User.nome).like(like),
                    db.func.lower(User.cognome).like(like),
                    db.func.lower(User.username).like(like),
                )
            )
        users = query.order_by(User.created_at.desc()).limit(limit).all()
        return jsonify({'users': [u.to_dict() for u in users]})
    except Exception as e:
        return jsonify({'error': f'Errore caricamento utenti: {str(e)}'}), 500


@app.route('/api/users/page', methods=['GET'])
def list_users_paged():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        pagination = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'users': [u.to_dict() for u in pagination.items],
            'page': page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
            'total': pagination.total
        })
    except Exception as e:
        return jsonify({'error': f'Errore paginazione utenti: {str(e)}'}), 500


# ======= POSTS =======

def _paginate_posts(page, per_page):
    """Compat con Flask-SQLAlchemy 3.x"""
    try:
        return Post.query.order_by(Post.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    except AttributeError:
        stmt = db.select(Post).order_by(Post.created_at.desc())
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Ottieni feed post (pubblico)"""
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
    """Crea nuovo post (richiede login)"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Login richiesto'}), 401

        data = _payload()
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'error': 'Contenuto post richiesto'}), 400
        if len(content) > 4000:
            return jsonify({'error': 'Post troppo lungo (max 4000 caratteri)'}), 400

        post = Post(content=content, user_id=user.id)
        db.session.add(post)
        db.session.commit()

        return jsonify({'message': 'Post creato', 'post': post.to_dict(user)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore creazione post: {str(e)}'}), 500


@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    """Metti/Togli like a post (richiede login)"""
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
        return jsonify({
            'action': action,
            'likes_count': post.get_likes_count(),
            'is_liked': post.is_liked_by(user)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore like: {str(e)}'}), 500


# ======= UPLOADS =======
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Login richiesto'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file nel payload (campo "file")'}), 400

    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Filename vuoto'}), 400

    if not _allowed_file(f.filename):
        return jsonify({'error': 'Estensione non permessa'}), 400

    base = secure_filename(f.filename)
    name, ext = os.path.splitext(base)
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    final_name = f"{user.id}_{ts}{ext.lower()}"

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], final_name)
    f.save(save_path)

    file_url = f"/uploads/{final_name}"
    return jsonify({'url': file_url, 'filename': base})


# ========================================
# WEB ROUTES
# ========================================

@app.route('/')
def home():
    """Homepage"""
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
