# app.py (aggiornato)

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


# ======= USERS API (NUOVA) =======
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



# templates/index.html (aggiornato – navbar dark, utenti dinamici, markdown, upload, share)

<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CourseConnect - Social Network per Corsisti</title>

  <!-- Bootstrap 5 -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <!-- Font Awesome -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <!-- Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <!-- highlight.js theme -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github-dark.min.css">

  <style>
    :root{ --primary-color:#667eea; --secondary-color:#764ba2; --accent-color:#f093fb; --success-color:#4facfe; --warning-color:#f6d365; --danger-color:#ff6b6b; --dark-bg:#1a1a1a; --card-bg:#2d2d2d; --text-light:#e0e0e0; --text-muted:#9ca3af; --border-color:#374151; }
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Inter',sans-serif;background:linear-gradient(135deg,var(--dark-bg) 0%,#2d1b69 100%);color:var(--text-light);min-height:100vh;overflow-x:hidden}
    .bg-animation{position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;opacity:.1}
    .floating-shapes{position:absolute;width:100%;height:100%;overflow:hidden}
    .shape{position:absolute;background:linear-gradient(45deg,var(--primary-color),var(--secondary-color));border-radius:50%;animation:float 8s ease-in-out infinite}
    .shape:nth-child(1){width:80px;height:80px;left:10%;animation-delay:0s}
    .shape:nth-child(2){width:120px;height:120px;left:70%;animation-delay:2s}
    .shape:nth-child(3){width:60px;height:60px;left:85%;animation-delay:4s}
    @keyframes float{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-20px) rotate(180deg)}}
    .glass-card{background:rgba(45,45,45,.7);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.1);border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,.3);transition:all .3s ease}
    .glass-card:hover{transform:translateY(-5px);box-shadow:0 12px 40px rgba(0,0,0,.4)}
    .navbar{background:rgba(26,26,26,.9)!important;backdrop-filter:blur(10px);border-bottom:1px solid var(--border-color);padding:1rem 0}
    .navbar-brand{font-weight:700;background:linear-gradient(45deg,var(--primary-color),var(--accent-color));-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:1.5rem}
    .nav-link{color:var(--text-light)!important;font-weight:500;transition:color .3s ease}
    .nav-link:hover{color:var(--primary-color)!important}
    .navbar .navbar-toggler{border-color:rgba(255,255,255,.25)}
    .navbar .navbar-toggler:focus{box-shadow:0 0 0 .15rem rgba(102,126,234,.35)}
    .btn-primary{background:linear-gradient(45deg,var(--primary-color),var(--secondary-color));border:none;padding:.75rem 2rem;border-radius:10px;font-weight:600;transition:all .3s ease}
    .btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(102,126,234,.3)}
    .btn-outline-primary{color:var(--primary-color);border-color:var(--primary-color);background:transparent}
    .btn-outline-primary:hover{background:var(--primary-color);border-color:var(--primary-color);color:#fff}
    .hero-section{padding:4rem 0;text-align:center}
    .hero-title{font-size:3.5rem;font-weight:700;margin-bottom:1.5rem;background:linear-gradient(45deg,var(--primary-color),var(--accent-color));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .hero-subtitle{font-size:1.25rem;color:var(--text-muted);margin-bottom:2rem;max-width:600px;margin-left:auto;margin-right:auto}
    .form-control,.form-select{background:rgba(45,45,45,.7);border:1px solid var(--border-color);color:var(--text-light);border-radius:10px;padding:.75rem 1rem}
    .form-control:focus,.form-select:focus{background:rgba(45,45,45,.9);border-color:var(--primary-color);color:var(--text-light);box-shadow:0 0 0 .2rem rgba(102,126,234,.25)}
    .form-control::placeholder{color:var(--text-muted)}
    .form-select option{background:var(--card-bg);color:var(--text-light)}
    .is-invalid{border-color:var(--danger-color)!important;box-shadow:0 0 0 .2rem rgba(255,107,107,.25)!important}
    .is-valid{border-color:var(--success-color)!important;box-shadow:0 0 0 .2rem rgba(79,172,254,.25)!important}
    .invalid-feedback{color:var(--danger-color);font-size:.875rem;margin-top:.25rem}
    .valid-feedback{color:var(--success-color);font-size:.875rem;margin-top:.25rem}
    .modal-content{background:var(--card-bg);border:1px solid var(--border-color);border-radius:16px}
    .modal-header{border-bottom:1px solid var(--border-color)}
    .modal-footer{border-top:1px solid var(--border-color)}
    .alert{border-radius:10px;border:none;position:fixed;top:20px;right:20px;z-index:9999;min-width:300px;max-width:400px}
    .alert-success{background:linear-gradient(45deg,rgba(79,172,254,.9),rgba(79,172,254,.9));color:#fff;border:1px solid rgba(79,172,254,.3)}
    .alert-danger{background:linear-gradient(45deg,rgba(255,107,107,.9),rgba(255,107,107,.9));color:#fff;border:1px solid rgba(255,107,107,.3)}
    .post-card{margin-bottom:1.5rem;padding:1.5rem}
    .user-avatar{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;color:#fff;margin-right:1rem}
    .post-content{font-size:1rem;line-height:1.6;margin:1rem 0}
    .post-actions{display:flex;gap:1rem;margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border-color)}
    .action-btn{background:none;border:none;color:var(--text-muted);padding:.5rem 1rem;border-radius:8px;transition:all .3s ease;cursor:pointer}
    .action-btn:hover{color:var(--primary-color);background:rgba(102,126,234,.1)}
    .action-btn.liked{color:var(--danger-color)}
    .loading{display:none;text-align:center;padding:2rem}
    .spinner{width:40px;height:40px;border:4px solid rgba(102,126,234,.3);border-top:4px solid var(--primary-color);border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 1rem}
    @keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
    .sidebar{background:rgba(45,45,45,.4);border-radius:16px;padding:1.5rem;margin-bottom:2rem}
    .sidebar h5{color:var(--primary-color);margin-bottom:1rem}
    .post-content pre code{display:block;padding:1rem;border-radius:12px}
    .post-content pre{background:rgba(0,0,0,.35);border:1px solid var(--border-color)}
    @media (max-width:991.98px){.navbar .navbar-collapse{background:rgba(26,26,26,.98);border:1px solid var(--border-color);border-radius:12px;padding:.5rem 1rem;margin-top:.75rem}.navbar-nav .nav-link{padding:.5rem 0}}
    @media (max-width:768px){.hero-title{font-size:2.5rem}.hero-subtitle{font-size:1rem}.post-card{padding:1rem}}
    .fade-in{animation:fadeIn .6s ease-in}
    @keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
    .slide-up{animation:slideUp .4s ease-out}
    @keyframes slideUp{from{transform:translateY(100px);opacity:0}to{transform:translateY(0);opacity:1}}
  </style>
</head>
<body>
  <div class="bg-animation">
    <div class="floating-shapes"><div class="shape"></div><div class="shape"></div><div class="shape"></div></div>
  </div>

  <nav class="navbar navbar-expand-lg navbar-dark fixed-top">
    <div class="container">
      <a class="navbar-brand" href="/"><i class="fas fa-graduation-cap me-2"></i>CourseConnect</a>
      <button class="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
        <i class="fas fa-bars" style="font-size:1.25rem"></i>
      </button>
      <div class="collapse navbar-collapse" id="navbarNav">
        <ul class="navbar-nav ms-auto">
          <li class="nav-item" id="nav-login"><a class="nav-link" href="#" data-bs-toggle="modal" data-bs-target="#loginModal"><i class="fas fa-sign-in-alt me-2"></i>Accedi</a></li>
          <li class="nav-item" id="nav-register"><a class="nav-link" href="#" data-bs-toggle="modal" data-bs-target="#registerModal"><i class="fas fa-user-plus me-2"></i>Registrati</a></li>
          <li class="nav-item" id="nav-user" style="display:none;"><span class="nav-link"><i class="fas fa-user me-2"></i>Ciao, <span id="user-name"></span>!</span></li>
          <li class="nav-item" id="nav-logout" style="display:none;"><a class="nav-link" href="#" onclick="logout()"><i class="fas fa-sign-out-alt me-2"></i>Logout</a></li>
        </ul>
      </div>
    </div>
  </nav>

  <div class="container mt-5 pt-5">
    <div id="guest-section">
      <div class="hero-section fade-in">
        <h1 class="hero-title"><i class="fas fa-graduation-cap me-3"></i>CourseConnect</h1>
        <p class="hero-subtitle">Il social network dedicato ai corsisti. Connettiti, condividi e cresci insieme alla community di apprendimento più dinamica!</p>
        <div class="d-flex gap-3 justify-content-center flex-wrap">
          <button class="btn btn-primary btn-lg" data-bs-toggle="modal" data-bs-target="#registerModal"><i class="fas fa-rocket me-2"></i>Inizia Ora</button>
          <button class="btn btn-outline-primary btn-lg" data-bs-toggle="modal" data-bs-target="#loginModal"><i class="fas fa-sign-in-alt me-2"></i>Accedi</button>
        </div>
      </div>

      <div class="row mt-5">
        <div class="col-md-4 mb-4"><div class="glass-card text-center p-4 h-100 fade-in"><i class="fas fa-users fa-3x mb-3" style="color:var(--primary-color)"></i><h4>Community</h4><p>Connettiti con corsisti da tutta Italia, condividi esperienze e crea relazioni durature.</p></div></div>
        <div class="col-md-4 mb-4"><div class="glass-card text-center p-4 h-100 fade-in"><i class="fas fa-lightbulb fa-3x mb-3" style="color:var(--accent-color)"></i><h4>Condivisione</h4><p>Condividi progetti, successi e sfide. Impara dagli altri e aiuta chi è agli inizi.</p></div></div>
        <div class="col-md-4 mb-4"><div class="glass-card text-center p-4 h-100 fade-in"><i class="fas fa-chart-line fa-3x mb-3" style="color:var(--success-color)"></i><h4>Crescita</h4><p>Accelera il tuo apprendimento attraverso feedback, collaborazioni e opportunità.</p></div></div>
      </div>
    </div>

    <div id="user-section" style="display:none;">
      <div class="row">
        <div class="col-lg-8">
          <div class="glass-card p-4 mb-4 slide-up">
            <h5 class="mb-3"><i class="fas fa-edit me-2"></i>Cosa stai imparando oggi?</h5>
            <div class="d-flex gap-2 flex-wrap mb-2">
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="mdWrap('**','**')"><strong>B</strong></button>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="mdWrap('*','*')"><em>I</em></button>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="mdWrap('`','`')">`code`</button>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="mdWrap('\n```\n','\n```\n', true)">code block</button>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="insertLink()">link</button>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="triggerImagePick()"><i class="fa-regular fa-image me-1"></i> immagine</button>
              <input type="file" id="image-input" accept="image/*" class="d-none" />
            </div>
            <div class="mb-3">
              <textarea class="form-control" id="post-content" rows="5" placeholder="Markdown supportato: **grassetto**, *corsivo*, `codice`, ```blocchi```, ![alt](url)" maxlength="4000"></textarea>
              <div class="text-end mt-2"><small class="text-muted"><span id="char-count">0</span>/4000 caratteri</small></div>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-primary" onclick="createPost()"><i class="fas fa-paper-plane me-2"></i>Pubblica</button>
              <button class="btn btn-outline-primary" type="button" onclick="previewPost()"><i class="fa-regular fa-eye me-2"></i>Anteprima</button>
            </div>
            <div id="post-preview" class="mt-3" style="display:none"><div class="border rounded p-3" id="post-preview-body"></div></div>
          </div>

          <div id="posts-container"><div class="loading"><div class="spinner"></div><p>Caricamento post...</p></div></div>
        </div>

        <div class="col-lg-4">
          <div class="sidebar glass-card">
            <h5><i class="fas fa-fire me-2"></i>Corsisti Attivi</h5>
            <div id="active-users"></div>
          </div>

          <div class="sidebar glass-card">
            <h5><i class="fas fa-star me-2"></i>Tips del Giorno</h5>
            <p class="mb-2"><strong>💡 Coding:</strong> Usa console.log() per debuggare il JavaScript</p>
            <p class="mb-2"><strong>🎨 Design:</strong> I colori complementari creano contrasto efficace</p>
            <p class="mb-0"><strong>📈 Marketing:</strong> A/B test per ottimizzare le conversioni</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Login Modal -->
  <div class="modal fade" id="loginModal" tabindex="-1">
    <div class="modal-dialog"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title"><i class="fas fa-sign-in-alt me-2"></i>Accedi a CourseConnect</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <form id="login-form">
          <div class="mb-3"><label for="login-username" class="form-label">Username</label><input type="text" class="form-control" id="login-username" required></div>
          <div class="mb-3"><label for="login-password" class="form-label">Password</label><input type="password" class="form-control" id="login-password" required></div>
          <div class="text-center"><small class="text-muted">🔧 Test: admin/admin123 o marco_dev/password123</small></div>
        </form>
      </div>
      <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Chiudi</button><button type="button" class="btn btn-primary" onclick="login()"><i class="fas fa-sign-in-alt me-2"></i>Accedi</button></div>
    </div></div>
  </div>

  <!-- Register Modal -->
  <div class="modal fade" id="registerModal" tabindex="-1">
    <div class="modal-dialog modal-lg"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title"><i class="fas fa-user-plus me-2"></i>Registrati su CourseConnect</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <form id="register-form" novalidate>
          <div class="row">
            <div class="col-md-6"><div class="mb-3"><label for="register-nome" class="form-label">Nome *</label><input type="text" class="form-control" id="register-nome" required><div class="invalid-feedback">Il nome è obbligatorio</div></div></div>
            <div class="col-md-6"><div class="mb-3"><label for="register-cognome" class="form-label">Cognome *</label><input type="text" class="form-control" id="register-cognome" required><div class="invalid-feedback">Il cognome è obbligatorio</div></div></div>
          </div>
          <div class="row">
            <div class="col-md-6"><div class="mb-3"><label for="register-username" class="form-label">Username *</label><input type="text" class="form-control" id="register-username" required><div class="invalid-feedback">L'username è obbligatorio</div></div></div>
            <div class="col-md-6"><div class="mb-3"><label for="register-email" class="form-label">Email *</label><input type="email" class="form-control" id="register-email" required><div class="invalid-feedback">Inserisci un'email valida</div></div></div>
          </div>
          <div class="mb-3"><label for="register-corso" class="form-label">Corso di Studio *</label>
            <select class="form-select" id="register-corso" required>
              <option value="">Seleziona il tuo corso...</option>
              <option value="Sviluppo Web Full-Stack">Sviluppo Web Full-Stack</option>
              <option value="UI/UX Design">UI/UX Design</option>
              <option value="Digital Marketing">Digital Marketing</option>
              <option value="Data Science">Data Science</option>
              <option value="Mobile Development">Mobile Development</option>
              <option value="Cybersecurity">Cybersecurity</option>
              <option value="Cloud Computing">Cloud Computing</option>
              <option value="Game Development">Game Development</option>
              <option value="Web Design">Web Design</option>
              <option value="Altro">Altro</option>
            </select>
            <div class="invalid-feedback">Seleziona un corso dal menu</div>
          </div>
          <div class="mb-3"><label for="register-password" class="form-label">Password *</label><input type="password" class="form-control" id="register-password" required minlength="6"><div class="form-text">Minimo 6 caratteri</div><div class="invalid-feedback">La password deve essere di almeno 6 caratteri</div></div>
          <div class="mb-3"><label for="register-bio" class="form-label">Bio (Opzionale)</label><textarea class="form-control" id="register-bio" rows="2" placeholder="Raccontaci di te..."></textarea></div>
        </form>
      </div>
      <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Chiudi</button><button type="button" class="btn btn-primary" onclick="register()" id="register-btn"><i class="fas fa-user-plus me-2"></i>Registrati</button></div>
    </div></div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.7/dist/purify.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/lib/common.min.js"></script>

  <script>
    // State Management
    let currentUser = null; let posts = [];

    document.addEventListener('DOMContentLoaded', function(){ checkAuth(); setupEventListeners(); });

    function setupEventListeners(){
      const postContent = document.getElementById('post-content');
      if(postContent){
        postContent.addEventListener('input', function(){ const cc = document.getElementById('char-count'); if(cc){ cc.textContent = this.value.length; } });
        postContent.addEventListener('keydown', function(e){ if(e.ctrlKey && e.key==='Enter'){ createPost(); } });
      }
      const formFields = ['register-nome','register-cognome','register-username','register-email','register-corso','register-password'];
      formFields.forEach(id=>{ const f=document.getElementById(id); if(f){ f.addEventListener('input',()=>validateField(f)); f.addEventListener('blur',()=>validateField(f)); } });
    }

    // Markdown setup
    marked.setOptions({ breaks:true, gfm:true });
    function renderMarkdown(md){ const raw = marked.parse(md||''); return DOMPurify.sanitize(raw, { USE_PROFILES:{ html:true } }); }
    function hljsApply(el){ el.querySelectorAll('pre code').forEach(block=>{ try{ hljs.highlightElement(block);}catch(e){} }); }
    function mdWrap(left,right,block){ const ta=document.getElementById('post-content'); const s=ta.selectionStart,e=ta.selectionEnd; const before=ta.value.substring(0,s),sel=ta.value.substring(s,e),after=ta.value.substring(e); const wrapped = block? `${before}${left}${sel||'\n'}${right}${after}`: `${before}${left}${sel||'testo'}${right}${after}`; ta.value=wrapped; ta.focus(); document.getElementById('char-count').textContent=ta.value.length; }
    function insertLink(){ const url=prompt('Inserisci URL:'); if(!url) return; const ta=document.getElementById('post-content'); const s=ta.selectionStart,e=ta.selectionEnd; const sel=ta.value.substring(s,e)||'link'; ta.setRangeText(`[${sel}](${url})`, s, e, 'end'); document.getElementById('char-count').textContent=ta.value.length; }
    function triggerImagePick(){ document.getElementById('image-input').click(); }

    document.addEventListener('change', async (e)=>{
      if(e.target && e.target.id==='image-input'){
        const file=e.target.files[0]; if(!file) return;
        try{
          const fd=new FormData(); fd.append('file', file);
          const res=await fetch('/api/upload',{ method:'POST', body: fd });
          const data=await res.json(); if(!res.ok) throw new Error(data.error||'Upload fallito');
          const ta=document.getElementById('post-content'); const md=`\n![](${data.url})\n`; const pos=ta.selectionStart; ta.setRangeText(md,pos,pos,'end'); document.getElementById('char-count').textContent=ta.value.length; showAlert('Immagine caricata','success');
        }catch(err){ showAlert(err.message,'danger'); }
        e.target.value='';
      }
    });

    function previewPost(){ const md=document.getElementById('post-content').value; const html=renderMarkdown(md); const box=document.getElementById('post-preview'); const body=document.getElementById('post-preview-body'); body.innerHTML=html; box.style.display='block'; hljsApply(body); }

    async function sharePost(postId){ const url=`${location.origin}${location.pathname}#post-${postId}`; try{ if(navigator.share){ await navigator.share({ title:'CourseConnect', text:"Dai un'occhiata al mio post", url }); } else { await navigator.clipboard.writeText(url); showAlert('Link copiato negli appunti','success'); } } catch(e){} }

    // Auth
    async function checkAuth(){ try{ const response=await fetch('/api/me'); if(response.ok){ const data=await response.json(); currentUser=data.user; if(data.authenticated){ showUserSection(); loadPosts(); } else { showGuestSection(); } } else { showGuestSection(); } } catch(e){ showGuestSection(); } }

    async function login(){ const username=document.getElementById('login-username').value.trim(); const password=document.getElementById('login-password').value; if(!username||!password){ showAlert('Inserisci username e password','danger'); return; } try{ const response=await fetch('/api/login',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ username, password }) }); const data=await response.json(); if(response.ok){ currentUser=data.user; showAlert('Login effettuato con successo!','success'); closeModal('loginModal'); showUserSection(); loadPosts(); } else { showAlert(data.error||'Errore durante il login','danger'); } } catch(e){ showAlert('Errore di connessione','danger'); } }

    // Validation
    function validateField(field){ const value=field.value.trim(); let ok=true; field.classList.remove('is-valid','is-invalid'); switch(field.id){ case 'register-nome': case 'register-cognome': case 'register-username': ok=value.length>=2; break; case 'register-email': ok=/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value); break; case 'register-corso': ok=value!==''; break; case 'register-password': ok=value.length>=6; break; } field.classList.add(ok?'is-valid':'is-invalid'); return ok; }
    function validateForm(){ const ids=['register-nome','register-cognome','register-username','register-email','register-corso','register-password']; let ok=true; ids.forEach(id=>{ const f=document.getElementById(id); if(!validateField(f)) ok=false; }); return ok; }

    async function register(){ if(!validateForm()){ showAlert('Correggi gli errori nel form prima di continuare','danger'); return; } const formData={ nome:document.getElementById('register-nome').value.trim(), cognome:document.getElementById('register-cognome').value.trim(), username:document.getElementById('register-username').value.trim(), email:document.getElementById('register-email').value.trim(), corso:document.getElementById('register-corso').value, password:document.getElementById('register-password').value, bio:document.getElementById('register-bio').value.trim() };
      const btn=document.getElementById('register-btn'); const orig=btn.innerHTML; btn.disabled=true; btn.innerHTML='<i class="fas fa-spinner fa-spin me-2"></i>Registrazione...';
      try{ const res=await fetch('/api/register',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(formData) }); const data=await res.json(); if(res.ok){ currentUser=data.user; showAlert('🎉 Registrazione completata! Benvenuto in CourseConnect!','success'); closeModal('registerModal'); showUserSection(); loadPosts(); loadActiveUsers(); } else { showAlert(data.error||'Errore durante la registrazione','danger'); } } catch(err){ showAlert('Errore di connessione. Riprova.','danger'); } finally { btn.disabled=false; btn.innerHTML=orig; }
    }

    async function logout(){ try{ await fetch('/api/logout',{ method:'POST' }); currentUser=null; showAlert('Logout effettuato','success'); showGuestSection(); } catch(e){ showAlert('Errore durante il logout','danger'); } }

    function showGuestSection(){ document.getElementById('guest-section').style.display='block'; document.getElementById('user-section').style.display='none'; document.getElementById('nav-login').style.display='block'; document.getElementById('nav-register').style.display='block'; document.getElementById('nav-user').style.display='none'; document.getElementById('nav-logout').style.display='none'; }
    function showUserSection(){ document.getElementById('guest-section').style.display='none'; document.getElementById('user-section').style.display='block'; document.getElementById('nav-login').style.display='none'; document.getElementById('nav-register').style.display='none'; document.getElementById('nav-user').style.display='block'; document.getElementById('nav-logout').style.display='block'; if(currentUser){ document.getElementById('user-name').textContent=currentUser.nome; } loadActiveUsers(); }

    // Users sidebar
    async function loadActiveUsers(){ const box=document.getElementById('active-users'); if(!box) return; box.innerHTML='<div class="text-muted">Caricamento...</div>'; try{ const res=await fetch('/api/users?limit=10'); const data=await res.json(); if(!res.ok) throw new Error(data.error||'Errore'); if(!data.users||data.users.length===0){ box.innerHTML='<small class="text-muted">Nessun utente ancora.</small>'; return; } box.innerHTML = data.users.map(u=>`<div class="d-flex align-items-center mb-3"><div class="user-avatar" style="background:${u.avatar_color}; width:40px; height:40px;">${u.initials}</div><div><div class="fw-bold">${u.nome} ${u.cognome}</div><small class="text-muted">@${u.username} • ${u.corso}</small></div></div>`).join(''); } catch(e){ box.innerHTML=`<div class="text-danger"><small>${e.message}</small></div>`; } }

    // Posts
    async function loadPosts(){ const container=document.getElementById('posts-container'); container.innerHTML='<div class="loading"><div class="spinner"></div><p>Caricamento post...</p></div>'; try{ const res=await fetch('/api/posts'); const data=await res.json(); if(res.ok){ posts=data.posts; renderPosts(); } else { container.innerHTML=`<div class="alert alert-danger">Errore: ${data.error}</div>`; } } catch(e){ container.innerHTML='<div class="alert alert-danger">Errore di connessione</div>'; } }

    function renderPosts(){ const container=document.getElementById('posts-container'); if(posts.length===0){ container.innerHTML = `<div class="glass-card p-4 text-center"><i class="fas fa-comments fa-3x mb-3" style="color:var(--text-muted)"></i><h5>Nessun post ancora</h5><p class="text-muted">Sii il primo a condividere qualcosa con la community!</p></div>`; return; } container.innerHTML = posts.map(post=>{ const html=renderMarkdown(post.content); return `
      <div class="post-card glass-card slide-up" id="post-${post.id}">
        <div class="d-flex align-items-start">
          <div class="user-avatar" style="background:${post.author.avatar_color}">${post.author.initials}</div>
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div><h6 class="mb-0">${post.author.nome} ${post.author.cognome}</h6><small class="text-muted">@${post.author.username} • ${post.author.corso}</small></div>
              <small class="text-muted">${formatDate(post.created_at)}</small>
            </div>
            <div class="post-content">${html}</div>
            <div class="post-actions">
              <button class="action-btn ${post.is_liked ? 'liked' : ''}" onclick="toggleLike(${post.id})"><i class="fas fa-heart me-1"></i><span id="likes-${post.id}">${post.likes_count}</span></button>
              <button class="action-btn" onclick="sharePost(${post.id})"><i class="fas fa-share me-1"></i>Condividi</button>
            </div>
          </div>
        </div>
      </div>`; }).join(''); container.querySelectorAll('.post-card .post-content').forEach(el=>hljsApply(el)); }

    async function createPost(){ const content=document.getElementById('post-content').value.trim(); if(!content){ showAlert('Scrivi qualcosa prima di pubblicare!','danger'); return; } if(content.length>4000){ showAlert('Il post è troppo lungo (max 4000 caratteri)','danger'); return; } try{ const response=await fetch('/api/posts',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ content }) }); const data=await response.json(); if(response.ok){ document.getElementById('post-content').value=''; document.getElementById('char-count').textContent='0'; document.getElementById('post-preview').style.display='none'; showAlert('Post pubblicato!','success'); loadPosts(); } else { showAlert(data.error||'Errore durante la pubblicazione','danger'); } } catch(e){ showAlert('Errore di connessione','danger'); } }

    async function toggleLike(postId){ try{ const res=await fetch(`/api/posts/${postId}/like`,{ method:'POST' }); const data=await res.json(); if(res.ok){ const likesSpan=document.getElementById(`likes-${postId}`); const likeBtn=likesSpan.parentElement; likesSpan.textContent=data.likes_count; if(data.is_liked) likeBtn.classList.add('liked'); else likeBtn.classList.remove('liked'); } else { showAlert(data.error||'Errore','danger'); } } catch(e){ showAlert('Errore di connessione','danger'); } }

    function formatDate(dateString){ const date=new Date(dateString); const now=new Date(); const s=Math.floor((now-date)/1000); if(s<60) return 'Ora'; if(s<3600) return Math.floor(s/60)+'m'; if(s<86400) return Math.floor(s/3600)+'h'; if(s<604800) return Math.floor(s/86400)+'g'; return date.toLocaleDateString('it-IT'); }

    function showAlert(message,type){ document.querySelectorAll('.alert').forEach(a=>a.remove()); const alertDiv=document.createElement('div'); alertDiv.className=`alert alert-${type} alert-dismissible fade show`; alertDiv.innerHTML=`<strong>${type==='success'?'✅':'❌'}</strong> ${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`; document.body.appendChild(alertDiv); setTimeout(()=>{ if(alertDiv&&alertDiv.parentNode) alertDiv.remove(); },5000); }
    function closeModal(id){ const modal=bootstrap.Modal.getInstance(document.getElementById(id)); if(modal) modal.hide(); }

    window.addEventListener('scroll', function(){ document.querySelectorAll('.glass-card').forEach(el=>{ const top=el.getBoundingClientRect().top; if(top < window.innerHeight - 150) el.classList.add('fade-in'); }); });
  </script>
</body>
</html>


# requirements.txt (aggiunta dipendenza Postgres)

Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Werkzeug==2.3.7
Jinja2==3.1.6
gunicorn==21.2.0
psycopg2-binary==2.9.9
