# ========================================
# CourseConnect - Social Network per Corsisti
# app.py - Backend Flask con Sistema Completo
# ========================================

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime, timedelta
import logging
import mimetypes

app = Flask(__name__)
app.config['SECRET_KEY'] = 'courseconnect-secret-key-2024'

# Database Configuration
if os.environ.get('DATABASE_URL'):
    # Production PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
else:
    # Development SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///courseconnect.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'videos': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'}
}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# ========================================
# MODELS
# ========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default='')
    course = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='author', lazy=True, cascade='all, delete-orphan')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255))
    video_filename = db.Column(db.String(255))  # Nuovo campo per video
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments_count = db.Column(db.Integer, default=0)
    likes_count = db.Column(db.Integer, default=0)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DeletedAccount(db.Model):
    """Modello per tracciare account eliminati e feedback"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    deletion_reason = db.Column(db.String(500))
    feedback = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)

# ========================================
# HELPER FUNCTIONS
# ========================================

def allowed_file(filename, file_type):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[file_type]

def get_file_type(filename):
    """Determina se un file è immagine o video"""
    if not filename:
        return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ALLOWED_EXTENSIONS['images']:
        return 'image'
    elif ext in ALLOWED_EXTENSIONS['videos']:
        return 'video'
    return None

def create_tables():
    """Crea tutte le tabelle se non esistono"""
    try:
        with app.app_context():
            db.create_all()
            
            # Crea admin di default se non esiste
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email='admin@courseconnect.it',
                    password_hash=generate_password_hash('admin123'),
                    bio='Amministratore di CourseConnect',
                    course='Computer Science'
                )
                db.session.add(admin_user)
                
                # Post di benvenuto
                welcome_post = Post(
                    user_id=1,
                    content='🎉 Benvenuti su CourseConnect! \n\nQuesta è la piattaforma dove i corsisti possono:\n\n✅ Condividere esperienze di studio\n✅ Pubblicare foto e video\n✅ Commentare e interagire\n✅ Recensire corsi\n✅ Fare networking\n\nInizia a condividere la tua esperienza di studio! 📚'
                )
                db.session.add(welcome_post)
                
                db.session.commit()
                logger.info("✅ Admin user and welcome post created")
                
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")

# ========================================
# ROUTES
# ========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================================
# AUTH ROUTES
# ========================================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validazioni
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username già esistente'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email già registrata'}), 400
        
        # Crea nuovo utente
        user = User(
            username=data['username'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            bio=data.get('bio', ''),
            course=data.get('course', '')
        )
        
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'bio': user.bio,
                'course': user.course
            }
        })
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Errore durante la registrazione'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        user = User.query.filter_by(username=data['username']).first()
        
        if user and check_password_hash(user.password_hash, data['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            
            return jsonify({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'bio': user.bio,
                    'course': user.course
                }
            })
        else:
            return jsonify({'error': 'Credenziali non valide'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Errore durante il login'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# ========================================
# ACCOUNT DELETION ROUTES
# ========================================

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    """Elimina account utente con feedback"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Non autorizzato'}), 401
        
        data = request.get_json()
        user = User.query.get(session['user_id'])
        
        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404
        
        # Salva feedback sull'eliminazione
        deleted_account = DeletedAccount(
            username=user.username,
            email=user.email,
            deletion_reason=data.get('reason', ''),
            feedback=data.get('feedback', '')
        )
        db.session.add(deleted_account)
        
        # Elimina l'utente (cascade eliminerà post, commenti, like)
        db.session.delete(user)
        db.session.commit()
        
        # Pulisci sessione
        session.clear()
        
        logger.info(f"Account deleted: {user.username}, Reason: {data.get('reason', 'No reason')}")
        
        return jsonify({
            'success': True,
            'message': 'Account eliminato con successo'
        })
        
    except Exception as e:
        logger.error(f"Account deletion error: {e}")
        return jsonify({'error': 'Errore durante l\'eliminazione dell\'account'}), 500

# ========================================
# POST ROUTES
# ========================================

@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
        posts_data = []
        
        for post in posts:
            # Controlla se l'utente loggato ha messo like
            user_liked = False
            if 'user_id' in session:
                user_liked = Like.query.filter_by(
                    user_id=session['user_id'], 
                    post_id=post.id
                ).first() is not None
            
            posts_data.append({
                'id': post.id,
                'user_id': post.user_id,
                'username': post.author.username,
                'content': post.content,
                'image_filename': post.image_filename,
                'video_filename': post.video_filename,  # Includi video
                'created_at': post.created_at.isoformat(),
                'likes_count': post.likes_count,
                'comments_count': post.comments_count,
                'user_liked': user_liked,
                'user_can_delete': 'user_id' in session and (
                    session['user_id'] == post.user_id or 
                    session.get('username') == 'admin'
                )
            })
        
        return jsonify({'posts': posts_data})
        
    except Exception as e:
        logger.error(f"Get posts error: {e}")
        return jsonify({'error': 'Errore nel caricamento dei post'}), 500

@app.route('/api/posts', methods=['POST'])
def create_post():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Devi essere loggato per pubblicare'}), 401
        
        content = request.form.get('content')
        if not content or len(content.strip()) == 0:
            return jsonify({'error': 'Il contenuto del post è richiesto'}), 400
        
        # Crea il post
        post = Post(
            user_id=session['user_id'],
            content=content
        )
        
        # Gestisci upload file (immagine o video)
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                file_type = get_file_type(file.filename)
                
                if file_type and allowed_file(file.filename, file_type + 's'):
                    # Genera nome sicuro
                    filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
                    
                    if file_type == 'video':
                        # Salva in sottocartella video
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', filename)
                        post.video_filename = f'videos/{filename}'
                    else:
                        # Salva immagine nella cartella principale
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        post.image_filename = filename
                    
                    file.save(filepath)
                    logger.info(f"File uploaded: {filename}, Type: {file_type}")
                else:
                    return jsonify({'error': 'Formato file non supportato'}), 400
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'post': {
                'id': post.id,
                'user_id': post.user_id,
                'username': post.author.username,
                'content': post.content,
                'image_filename': post.image_filename,
                'video_filename': post.video_filename,
                'created_at': post.created_at.isoformat(),
                'likes_count': 0,
                'comments_count': 0,
                'user_liked': False,
                'user_can_delete': True
            }
        })
        
    except Exception as e:
        logger.error(f"Create post error: {e}")
        return jsonify({'error': 'Errore durante la pubblicazione'}), 500

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Non autorizzato'}), 401
        
        post = Post.query.get_or_404(post_id)
        
        # Verifica permessi
        if session['user_id'] != post.user_id and session.get('username') != 'admin':
            return jsonify({'error': 'Non puoi eliminare questo post'}), 403
        
        # Elimina file se esistono
        if post.image_filename:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete image file: {e}")
        
        if post.video_filename:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.video_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete video file: {e}")
        
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Delete post error: {e}")
        return jsonify({'error': 'Errore durante l\'eliminazione'}), 500

# ========================================
# COMMENT ROUTES
# ========================================

@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'id': comment.id,
                'user_id': comment.user_id,
                'username': comment.author.username,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'user_can_delete': 'user_id' in session and (
                    session['user_id'] == comment.user_id or 
                    session.get('username') == 'admin'
                )
            })
        
        return jsonify({'comments': comments_data})
        
    except Exception as e:
        logger.error(f"Get comments error: {e}")
        return jsonify({'error': 'Errore nel caricamento dei commenti'}), 500

@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def create_comment(post_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Devi essere loggato per commentare'}), 401
        
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Il contenuto del commento è richiesto'}), 400
        
        if len(content) > 1000:
            return jsonify({'error': 'Il commento è troppo lungo (max 1000 caratteri)'}), 400
        
        post = Post.query.get_or_404(post_id)
        
        comment = Comment(
            post_id=post_id,
            user_id=session['user_id'],
            content=content
        )
        
        db.session.add(comment)
        
        # Aggiorna contatore commenti
        post.comments_count = Comment.query.filter_by(post_id=post_id).count() + 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'user_id': comment.user_id,
                'username': comment.author.username,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'user_can_delete': True
            }
        })
        
    except Exception as e:
        logger.error(f"Create comment error: {e}")
        return jsonify({'error': 'Errore durante la creazione del commento'}), 500

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Non autorizzato'}), 401
        
        comment = Comment.query.get_or_404(comment_id)
        
        # Verifica permessi
        if session['user_id'] != comment.user_id and session.get('username') != 'admin':
            return jsonify({'error': 'Non puoi eliminare questo commento'}), 403
        
        post_id = comment.post_id
        db.session.delete(comment)
        
        # Aggiorna contatore commenti
        post = Post.query.get(post_id)
        if post:
            post.comments_count = Comment.query.filter_by(post_id=post_id).count() - 1
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Delete comment error: {e}")
        return jsonify({'error': 'Errore durante l\'eliminazione del commento'}), 500

# ========================================
# LIKE ROUTES
# ========================================

@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Devi essere loggato per mettere like'}), 401
        
        post = Post.query.get_or_404(post_id)
        existing_like = Like.query.filter_by(
            user_id=session['user_id'], 
            post_id=post_id
        ).first()
        
        if existing_like:
            # Rimuovi like
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            action = 'removed'
        else:
            # Aggiungi like
            new_like = Like(user_id=session['user_id'], post_id=post_id)
            db.session.add(new_like)
            post.likes_count += 1
            action = 'added'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'action': action,
            'likes_count': post.likes_count
        })
        
    except Exception as e:
        logger.error(f"Toggle like error: {e}")
        return jsonify({'error': 'Errore durante l\'operazione'}), 500

# ========================================
# USER ROUTES
# ========================================

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        users_data = []
        
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'bio': user.bio,
                'course': user.course,
                'created_at': user.created_at.isoformat(),
                'posts_count': Post.query.filter_by(user_id=user.id).count()
            })
        
        return jsonify({'users': users_data})
        
    except Exception as e:
        logger.error(f"Get users error: {e}")
        return jsonify({'error': 'Errore nel caricamento degli utenti'}), 500

@app.route('/api/user/current', methods=['GET'])
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'logged_in': False})
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'logged_in': False})
    
    return jsonify({
        'logged_in': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'bio': user.bio,
            'course': user.course
        }
    })

# ========================================
# REVIEW ROUTES
# ========================================

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        reviews = Review.query.order_by(Review.created_at.desc()).all()
        reviews_data = []
        
        for review in reviews:
            reviews_data.append({
                'id': review.id,
                'username': review.author.username,
                'course_name': review.course_name,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at.isoformat()
            })
        
        return jsonify({'reviews': reviews_data})
        
    except Exception as e:
        logger.error(f"Get reviews error: {e}")
        return jsonify({'error': 'Errore nel caricamento delle recensioni'}), 500

@app.route('/api/reviews', methods=['POST'])
def create_review():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Devi essere loggato per scrivere una recensione'}), 401
        
        data = request.get_json()
        
        review = Review(
            user_id=session['user_id'],
            course_name=data['course_name'],
            rating=int(data['rating']),
            comment=data.get('comment', '')
        )
        
        db.session.add(review)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Create review error: {e}")
        return jsonify({'error': 'Errore durante la creazione della recensione'}), 500

# ========================================
# INIT DATABASE
# ========================================

# Crea tabelle all'avvio
create_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
