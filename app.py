from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import secrets

app = Flask(__name__)

# Configurazione
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///courseconnect.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Inizializza database
db = SQLAlchemy(app)

# Crea directory uploads se non esiste
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Modelli Database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    course = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relazioni
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')
    likes_given = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='author', lazy=True, cascade='all, delete-orphan')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relazioni
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraint unico per evitare doppi like
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stelle
    text = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Funzioni helper
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 🚨 BACKUP ROUTE URGENTE - SALVA DATI SQLITE PRIMA CHE SI PERDANO! 🚨
@app.route('/api/backup-data')
def backup_data():
    """Route di emergenza per backup completo dei dati SQLite"""
    try:
        print("🚨 INIZIANDO BACKUP DATI URGENTE...")
        
        # Export tutti gli utenti
        users = User.query.all()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'password_hash': user.password_hash,
                'bio': user.bio,
                'course': user.course,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        # Export tutti i post
        posts = Post.query.all()
        posts_data = []
        for post in posts:
            posts_data.append({
                'id': post.id,
                'user_id': post.user_id,
                'content': post.content,
                'image_filename': post.image_filename,
                'created_at': post.created_at.isoformat() if post.created_at else None
            })
        
        # Export tutti i like
        likes = Like.query.all()
        likes_data = []
        for like in likes:
            likes_data.append({
                'id': like.id,
                'user_id': like.user_id,
                'post_id': like.post_id,
                'created_at': like.created_at.isoformat() if like.created_at else None
            })
        
        # Export recensioni (se esistono)
        reviews_data = []
        try:
            reviews = Review.query.all()
            for review in reviews:
                reviews_data.append({
                    'id': review.id,
                    'user_id': review.user_id,
                    'rating': review.rating,
                    'text': review.text,
                    'photo_filename': review.photo_filename,
                    'city': review.city,
                    'is_approved': review.is_approved,
                    'created_at': review.created_at.isoformat() if review.created_at else None
                })
        except Exception as e:
            print(f"⚠️ Tabella Review non trovata o errore: {e}")
        
        backup_data = {
            'backup_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'database_type': 'SQLite',
                'total_users': len(users_data),
                'total_posts': len(posts_data),
                'total_likes': len(likes_data),
                'total_reviews': len(reviews_data),
                'backup_version': '1.0'
            },
            'users': users_data,
            'posts': posts_data,
            'likes': likes_data,
            'reviews': reviews_data
        }
        
        print(f"✅ BACKUP COMPLETATO: {len(users_data)} utenti, {len(posts_data)} post, {len(likes_data)} like, {len(reviews_data)} recensioni")
        
        return jsonify(backup_data)
        
    except Exception as e:
        print(f"❌ ERRORE BACKUP: {str(e)}")
        return jsonify({
            'error': str(e),
            'backup_failed': True,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Route per cancellare recensioni
@app.route('/api/reviews/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401
    
    try:
        review = Review.query.get_or_404(review_id)
        
        # Solo l'autore può cancellare la propria recensione
        if review.user_id != session['user_id']:
            return jsonify({'error': 'Non autorizzato'}), 403
        
        # Rimuovi file foto se esiste
        if review.photo_filename:
            try:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], review.photo_filename)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            except:
                pass
        
        db.session.delete(review)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route principale
@app.route('/')
def home():
    return render_template('index.html')

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        course = data.get('course', '').strip()
        bio = data.get('bio', '').strip()
        
        # Validazione
        if not username or len(username) < 3:
            return jsonify({'error': 'Username deve essere di almeno 3 caratteri'}), 400
        
        if not password or len(password) < 6:
            return jsonify({'error': 'Password deve essere di almeno 6 caratteri'}), 400
        
        # Controlla se username esiste già
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username già esistente'}), 400
        
        # Controlla se email esiste già (se fornita)
        if email and User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email già registrata'}), 400
        
        # Crea nuovo utente
        new_user = User(
            username=username,
            email=email if email else None,
            password_hash=generate_password_hash(password),
            course=course if course else None,
            bio=bio if bio else None
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Benvenuto su CourseConnect, {username}!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username e password richiesti'}), 400
        
        # Trova utente
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Credenziali non valide'}), 401
        
        # Salva sessione
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'success': True,
            'message': f'Benvenuto, {user.username}!',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'course': user.course,
                'bio': user.bio
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logout effettuato'})

@app.route('/api/current-user')
def current_user():
    if 'user_id' not in session:
        return jsonify({'authenticated': False})
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'authenticated': False})
    
    return jsonify({
        'authenticated': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'course': user.course,
            'bio': user.bio
        }
    })

@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
        posts_data = []
        
        for post in posts:
            # Conta like per questo post
            like_count = Like.query.filter_by(post_id=post.id).count()
            
            # Controlla se l'utente corrente ha messo like
            user_has_liked = False
            if 'user_id' in session:
                user_has_liked = Like.query.filter_by(
                    post_id=post.id,
                    user_id=session['user_id']
                ).first() is not None
            
            posts_data.append({
                'id': post.id,
                'content': post.content,
                'image_filename': post.image_filename,
                'created_at': post.created_at.isoformat(),
                'author': {
                    'id': post.author.id,
                    'username': post.author.username,
                    'course': post.author.course
                },
                'like_count': like_count,
                'user_has_liked': user_has_liked
            })
        
        return jsonify(posts_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/posts', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401
    
    try:
        content = request.form.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Contenuto del post richiesto'}), 400
        
        # Gestione file upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                # Genera nome file sicuro
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                extension = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"{timestamp}_{secrets.token_hex(8)}.{extension}"
                
                # Salva file
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                file.save(file_path)
        
        # Crea nuovo post
        new_post = Post(
            user_id=session['user_id'],
            content=content,
            image_filename=image_filename
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Post pubblicato con successo!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401
    
    try:
        post = Post.query.get_or_404(post_id)
        
        # Solo l'autore del post o admin può eliminarlo
        if post.user_id != session['user_id'] and session.get('username') != 'admin':
            return jsonify({'error': 'Non autorizzato'}), 403
        
        # Rimuovi file immagine se esiste
        if post.image_filename:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass  # Non fallire se non riesce a rimuovere il file
        
        # Elimina post (i like vengono eliminati automaticamente grazie al cascade)
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/like', methods=['POST'])
def toggle_like():
    if 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401
    
    try:
        data = request.get_json()
        post_id = data.get('post_id')
        
        if not post_id:
            return jsonify({'error': 'ID post richiesto'}), 400
        
        # Controlla se il post esiste
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'error': 'Post non trovato'}), 404
        
        # Controlla se l'utente ha già messo like
        existing_like = Like.query.filter_by(
            user_id=session['user_id'],
            post_id=post_id
        ).first()
        
        if existing_like:
            # Rimuovi like
            db.session.delete(existing_like)
            action = 'removed'
        else:
            # Aggiungi like
            new_like = Like(
                user_id=session['user_id'],
                post_id=post_id
            )
            db.session.add(new_like)
            action = 'added'
        
        db.session.commit()
        
        # Conta like aggiornati
        like_count = Like.query.filter_by(post_id=post_id).count()
        
        return jsonify({
            'success': True,
            'action': action,
            'like_count': like_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def get_users():
    try:
        users = User.query.order_by(User.created_at.desc()).limit(10).all()
        users_data = []
        
        for user in users:
            post_count = Post.query.filter_by(user_id=user.id).count()
            users_data.append({
                'id': user.id,
                'username': user.username,
                'course': user.course,
                'post_count': post_count
            })
        
        return jsonify(users_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).all()
        reviews_data = []
        
        for review in reviews:
            reviews_data.append({
                'id': review.id,
                'rating': review.rating,
                'text': review.text,
                'photo_filename': review.photo_filename,
                'city': review.city,
                'created_at': review.created_at.isoformat(),
                'author': {
                    'id': review.author.id,
                    'username': review.author.username,
                    'course': review.author.course
                }
            })
        
        return jsonify(reviews_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reviews', methods=['POST'])
def create_review():
    if 'user_id' not in session:
        return jsonify({'error': 'Login richiesto'}), 401
    
    try:
        # Controlla se l'utente ha già lasciato una recensione
        existing_review = Review.query.filter_by(user_id=session['user_id']).first()
        if existing_review:
            return jsonify({'error': 'Hai già lasciato una recensione'}), 400
        
        rating = int(request.form.get('rating', 0))
        text = request.form.get('text', '').strip()
        city = request.form.get('city', '').strip()
        
        if not (1 <= rating <= 5):
            return jsonify({'error': 'Rating deve essere tra 1 e 5'}), 400
        
        if not text or len(text) < 10:
            return jsonify({'error': 'Recensione deve essere di almeno 10 caratteri'}), 400
        
        if len(text) > 500:
            return jsonify({'error': 'Recensione troppo lunga (max 500 caratteri)'}), 400
        
        # Gestione upload foto
        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                extension = file.filename.rsplit('.', 1)[1].lower()
                photo_filename = f"review_{timestamp}_{secrets.token_hex(8)}.{extension}"
                
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                file.save(file_path)
        
        # Crea nuova recensione
        new_review = Review(
            user_id=session['user_id'],
            rating=rating,
            text=text,
            photo_filename=photo_filename,
            city=city if city else None,
            is_approved=True  # Auto-approvata per ora
        )
        
        db.session.add(new_review)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Recensione pubblicata con successo!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Health check
@app.route('/api/health')
def health_check():
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        
        # Conta records
        user_count = User.query.count()
        post_count = Post.query.count()
        like_count = Like.query.count()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'stats': {
                'users': user_count,
                'posts': post_count,
                'likes': like_count
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

def create_tables():
    """Inizializza database e dati di esempio"""
    with app.app_context():
        db.create_all()
        
        # Controlla se admin esiste già
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@courseconnect.com',
                password_hash=generate_password_hash('admin123'),
                bio='Amministratore CourseConnect - Gestione piattaforma e supporto community',
                course='Gestione Piattaforma'
            )
            db.session.add(admin)
            db.session.commit()
            
            # Post di benvenuto dall'admin
            welcome_post = Post(
                user_id=admin.id,
                content="""# 🎉 Benvenuti su CourseConnect!

Ciao e benvenuti nella nostra community di corsisti! 👋

**Cosa puoi fare qui:**
- 📝 Condividi i tuoi progetti e progressi
- 💬 Fai domande e aiuta altri studenti  
- 📸 Carica screenshot e demo del tuo lavoro
- ⭐ Lascia recensioni sui corsi
- 🔗 Connettiti con altri professionisti

**Per iniziare:**
1. Completa il tuo profilo
2. Presenta te stesso con un primo post
3. Esplora i contenuti della community
4. Segui altri corsisti interessanti

Buon networking e buono studio! 🚀

*L'Amministrazione*"""
            )
            db.session.add(welcome_post)
            db.session.commit()
            
            print("✅ Database inizializzato con admin e post di benvenuto!")
        else:
            print("✅ Database già inizializzato!")

if __name__ == '__main__':
    create_tables()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚨 BACKUP ROUTE ATTIVA: /api/backup-data")
    print(f"🚀 CourseConnect avviato su porta {port}")
    print(f"📊 Admin: admin / admin123")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
