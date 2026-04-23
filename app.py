from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
import os
import base64
import hashlib
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui-mude-em-producao'
app.config['UPLOAD_FOLDER'] = 'static/uploads/fotos'
app.config['UPLOAD_MIDIA_FOLDER'] = 'static/uploads/midias'
app.config['UPLOAD_BANNER_FOLDER'] = 'static/uploads/banners'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB para vídeos
app.config['ALLOWED_IMAGES'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['ALLOWED_VIDEOS'] = {'mp4', 'webm', 'avi', 'mov', 'mkv'}

# Criar pastas necessárias
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_MIDIA_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_BANNER_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/postagens', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Arquivos JSON para armazenamento
USUARIOS_FILE = 'data/usuarios.json'
POSTAGENS_FILE = 'data/postagens.json'
COMENTARIOS_FILE = 'data/comentarios.json'
VISTAS_FILE = 'data/vistas.json'
CONFIG_FILE = 'data/config.json'

# Funções para manipular JSON
def carregar_json(arquivo):
    if os.path.exists(arquivo):
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def salvar_json(arquivo, dados):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'banner_url': '/static/img/banner-padrao.jpg'}

def salvar_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def allowed_file(filename, tipo):
    """Verifica se o arquivo é permitido"""
    if not '.' in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if tipo == 'imagem':
        return ext in app.config['ALLOWED_IMAGES']
    elif tipo == 'video':
        return ext in app.config['ALLOWED_VIDEOS']
    return False

def salvar_arquivo(arquivo, tipo, pasta='midias'):
    """Salva arquivo de mídia no servidor"""
    if arquivo and arquivo.filename:
        if allowed_file(arquivo.filename, tipo):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo.filename}")
            if pasta == 'banners':
                filepath = os.path.join(app.config['UPLOAD_BANNER_FOLDER'], filename)
            else:
                filepath = os.path.join(app.config['UPLOAD_MIDIA_FOLDER'], filename)
            arquivo.save(filepath)
            return f'/static/uploads/{pasta}/{filename}'
    return None

def salvar_foto(imagem_base64, nome_arquivo):
    """Salva foto em disco"""
    try:
        if 'base64,' in imagem_base64:
            imagem_base64 = imagem_base64.split('base64,')[1]
        
        imagem_bytes = base64.b64decode(imagem_base64)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        with open(filepath, 'wb') as f:
            f.write(imagem_bytes)
        
        return f'/static/uploads/fotos/{nome_arquivo}'
    except Exception as e:
        print(f"Erro ao salvar foto: {e}")
        return None

def detectar_face_simulado(imagem_base64):
    """Versão simplificada para detecção de rosto (sempre aceita)"""
    if imagem_base64 and len(imagem_base64) > 1000:
        return True
    return False

# Rotas principais
@app.route('/')
def index():
    config = carregar_config()
    return render_template('index.html', banner_url=config.get('banner_url', '/static/img/banner-padrao.jpg'))

@app.route('/reconhecer', methods=['POST'])
def reconhecer():
    foto = request.form.get('foto')
    if not foto:
        return jsonify({'success': False, 'error': 'Nenhuma foto fornecida'})
    
    # Detecta se é uma pessoa real (simulado)
    if detectar_face_simulado(foto):
        # Gera um hash único para a foto
        foto_hash = hashlib.md5(foto.encode()).hexdigest()
        
        # Carrega usuários existentes
        usuarios = carregar_json(USUARIOS_FILE)
        
        # Verifica se o usuário já existe
        usuario = None
        for u in usuarios:
            if u['foto_hash'] == foto_hash:
                usuario = u
                break
        
        if not usuario:
            # Cria novo usuário
            usuario_id = len(usuarios) + 1
            nome_arquivo = f"usuario_{usuario_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            foto_path = salvar_foto(foto, nome_arquivo)
            
            usuario = {
                'id': usuario_id,
                'nome': f"Usuario_{usuario_id}",
                'foto_path': foto_path,
                'foto_hash': foto_hash,
                'data_cadastro': datetime.now().isoformat(),
                'ultimo_acesso': datetime.now().isoformat(),
                'is_admin': False
            }
            usuarios.append(usuario)
            salvar_json(USUARIOS_FILE, usuarios)
        
        # Atualiza último acesso
        usuario['ultimo_acesso'] = datetime.now().isoformat()
        salvar_json(USUARIOS_FILE, usuarios)
        
        # Cria sessão
        session['usuario_id'] = usuario['id']
        session['usuario_nome'] = usuario.get('nome', f"Usuario_{usuario['id']}")
        session['usuario_foto'] = usuario['foto_path']
        
        return jsonify({'success': True, 'redirect': url_for('home')})
    else:
        return jsonify({'success': False, 'error': 'Não foi possível detectar um rosto válido. Tente novamente.'})

@app.route('/home')
def home():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))
    
    usuario = None
    usuarios = carregar_json(USUARIOS_FILE)
    for u in usuarios:
        if u['id'] == session['usuario_id']:
            usuario = u
            break
    
    config = carregar_config()
    return render_template('home.html', usuario=usuario, banner_url=config.get('banner_url', '/static/img/banner-padrao.jpg'))

@app.route('/api/postagens')
def api_postagens():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    postagens = carregar_json(POSTAGENS_FILE)
    comentarios = carregar_json(COMENTARIOS_FILE)
    vistas = carregar_json(VISTAS_FILE)
    usuarios = carregar_json(USUARIOS_FILE)
    
    # Ordenar por data decrescente
    postagens.sort(key=lambda x: x['data_postagem'], reverse=True)
    
    # Paginação
    start = (page - 1) * per_page
    end = start + per_page
    postagens_page = postagens[start:end]
    
    postagens_data = []
    for post in postagens_page:
        # Verifica se o usuário já viu
        ja_viu = False
        for vista in vistas:
            if vista['usuario_id'] == session['usuario_id'] and vista['postagem_id'] == post['id']:
                ja_viu = True
                break
        
        # Busca comentários da postagem
        comentarios_post = [c for c in comentarios if c['postagem_id'] == post['id']]
        comentarios_data = []
        for coment in comentarios_post:
            # Busca foto do usuário
            user_foto = '/static/uploads/fotos/default.jpg'
            for u in usuarios:
                if u['id'] == coment['usuario_id']:
                    user_foto = u.get('foto_path', '/static/uploads/fotos/default.jpg')
                    break
            
            # Nome do comentário: se não informou, mostra "Não quero informar meu nome"
            nome_exibido = coment.get('nome_usuario')
            if not nome_exibido or nome_exibido.strip() == '':
                nome_exibido = "Não quero informar meu nome"
            
            comentarios_data.append({
                'id': coment['id'],
                'texto': coment['texto'],
                'nome': nome_exibido,
                'foto': user_foto,
                'data': datetime.fromisoformat(coment['data_comentario']).strftime('%d/%m/%Y %H:%M')
            })
        
        total_vistas = len([v for v in vistas if v['postagem_id'] == post['id']])
        
        postagens_data.append({
            'id': post['id'],
            'titulo': post['titulo'],
            'resumo': post['resumo'],
            'tipo': post['tipo'],
            'conteudo': post['conteudo'],
            'data': datetime.fromisoformat(post['data_postagem']).strftime('%d/%m/%Y %H:%M'),
            'autor': post.get('autor', 'Admin'),
            'foto_autor': post.get('foto_admin', '/static/img/admin-padrao.jpg'),
            'ja_viu': ja_viu,
            'comentarios': comentarios_data,
            'total_vistas': total_vistas
        })
    
    has_next = len(postagens) > end
    
    return jsonify({
        'postagens': postagens_data,
        'has_next': has_next,
        'page': page
    })

@app.route('/api/postagem/<int:post_id>/viu', methods=['POST'])
def marcar_viu(post_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    vistas = carregar_json(VISTAS_FILE)
    
    # Verifica se já marcou
    for vista in vistas:
        if vista['usuario_id'] == session['usuario_id'] and vista['postagem_id'] == post_id:
            return jsonify({'success': False, 'error': 'Você já marcou esta postagem como vista'})
    
    # Adiciona nova vista
    nova_vista = {
        'id': len(vistas) + 1,
        'usuario_id': session['usuario_id'],
        'postagem_id': post_id,
        'data_vista': datetime.now().isoformat()
    }
    vistas.append(nova_vista)
    salvar_json(VISTAS_FILE, vistas)
    
    return jsonify({'success': True})

@app.route('/api/comentario', methods=['POST'])
def adicionar_comentario():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    data = request.get_json()
    post_id = data.get('post_id')
    texto = data.get('texto', '').strip()
    nome = data.get('nome', '').strip()
    
    if not texto:
        return jsonify({'success': False, 'error': 'Comentário vazio'})
    
    comentarios = carregar_json(COMENTARIOS_FILE)
    
    novo_comentario = {
        'id': len(comentarios) + 1,
        'usuario_id': session['usuario_id'],
        'postagem_id': post_id,
        'texto': texto,
        'nome_usuario': nome if nome else None,
        'data_comentario': datetime.now().isoformat()
    }
    comentarios.append(novo_comentario)
    salvar_json(COMENTARIOS_FILE, comentarios)
    
    return jsonify({'success': True})

# Rotas Admin
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        # Senha padrão: admin123
        if senha == 'admin123':
            # Cria ou busca admin
            usuarios = carregar_json(USUARIOS_FILE)
            admin = None
            for u in usuarios:
                if u.get('is_admin'):
                    admin = u
                    break
            
            if not admin:
                admin_id = len(usuarios) + 1
                admin = {
                    'id': admin_id,
                    'nome': 'Administrador',
                    'foto_path': '/static/img/admin-padrao.jpg',
                    'foto_hash': 'admin_hash',
                    'data_cadastro': datetime.now().isoformat(),
                    'ultimo_acesso': datetime.now().isoformat(),
                    'is_admin': True
                }
                usuarios.append(admin)
                salvar_json(USUARIOS_FILE, usuarios)
            
            session['usuario_id'] = admin['id']
            session['usuario_nome'] = admin['nome']
            session['usuario_foto'] = admin['foto_path']
            session['is_admin'] = True
            
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Senha incorreta')
    return render_template('admin_login.html')

@app.route('/admin')
def admin_dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('admin_login'))
    
    # Verifica se é admin
    usuarios = carregar_json(USUARIOS_FILE)
    usuario_atual = None
    for u in usuarios:
        if u['id'] == session['usuario_id']:
            usuario_atual = u
            break
    
    if not usuario_atual or not usuario_atual.get('is_admin'):
        return redirect(url_for('home'))
    
    config = carregar_config()
    return render_template('admin.html', banner_url=config.get('banner_url', '/static/img/banner-padrao.jpg'))

@app.route('/admin/api/banner', methods=['POST'])
def admin_upload_banner():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'banner' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'})
    
    arquivo = request.files['banner']
    if arquivo.filename == '':
        return jsonify({'success': False, 'error': 'Arquivo vazio'})
    
    # Salvar banner
    banner_path = salvar_arquivo(arquivo, 'imagem', 'banners')
    if banner_path:
        # Atualizar configuração
        config = carregar_config()
        config['banner_url'] = banner_path
        salvar_config(config)
        return jsonify({'success': True, 'banner_url': banner_path})
    
    return jsonify({'success': False, 'error': 'Formato não suportado'})

@app.route('/admin/api/postagens')
def admin_api_postagens():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    postagens = carregar_json(POSTAGENS_FILE)
    vistas = carregar_json(VISTAS_FILE)
    comentarios = carregar_json(COMENTARIOS_FILE)
    
    postagens.sort(key=lambda x: x['data_postagem'], reverse=True)
    
    return jsonify([{
        'id': p['id'],
        'titulo': p['titulo'],
        'tipo': p['tipo'],
        'data': datetime.fromisoformat(p['data_postagem']).strftime('%d/%m/%Y %H:%M'),
        'total_vistas': len([v for v in vistas if v['postagem_id'] == p['id']]),
        'total_comentarios': len([c for c in comentarios if c['postagem_id'] == p['id']])
    } for p in postagens])

@app.route('/admin/api/postagem', methods=['POST'])
def admin_criar_postagem():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Verificar se é upload de arquivo ou JSON
    if request.files:
        # Upload de arquivo (foto ou vídeo)
        arquivo = request.files.get('arquivo')
        tipo = request.form.get('tipo')
        titulo = request.form.get('titulo')
        resumo = request.form.get('resumo')
        
        if arquivo and arquivo.filename:
            # Salvar arquivo
            caminho_arquivo = salvar_arquivo(arquivo, tipo)
            
            if caminho_arquivo:
                postagens = carregar_json(POSTAGENS_FILE)
                nova_postagem = {
                    'id': len(postagens) + 1,
                    'titulo': titulo,
                    'resumo': resumo,
                    'tipo': tipo,
                    'conteudo': caminho_arquivo,
                    'data_postagem': datetime.now().isoformat(),
                    'autor': session.get('usuario_nome', 'Admin'),
                    'foto_admin': session.get('usuario_foto', '/static/img/admin-padrao.jpg')
                }
                postagens.append(nova_postagem)
                salvar_json(POSTAGENS_FILE, postagens)
                return jsonify({'success': True, 'id': nova_postagem['id']})
    else:
        # Postagem via JSON (texto ou YouTube)
        data = request.get_json()
        postagens = carregar_json(POSTAGENS_FILE)
        
        nova_postagem = {
            'id': len(postagens) + 1,
            'titulo': data.get('titulo'),
            'resumo': data.get('resumo'),
            'tipo': data.get('tipo'),
            'conteudo': data.get('conteudo'),
            'data_postagem': datetime.now().isoformat(),
            'autor': session.get('usuario_nome', 'Admin'),
            'foto_admin': session.get('usuario_foto', '/static/img/admin-padrao.jpg')
        }
        postagens.append(nova_postagem)
        salvar_json(POSTAGENS_FILE, postagens)
        
        return jsonify({'success': True, 'id': nova_postagem['id']})
    
    return jsonify({'success': False, 'error': 'Erro ao salvar postagem'})

@app.route('/admin/api/postagem/<int:post_id>', methods=['DELETE'])
def admin_deletar_postagem(post_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    postagens = carregar_json(POSTAGENS_FILE)
    
    # Encontrar e deletar arquivo físico se existir
    for post in postagens:
        if post['id'] == post_id:
            if post['tipo'] in ['foto', 'video_local']:
                # Deletar arquivo do servidor
                filepath = post['conteudo'].lstrip('/')
                if os.path.exists(filepath):
                    os.remove(filepath)
            break
    
    postagens = [p for p in postagens if p['id'] != post_id]
    salvar_json(POSTAGENS_FILE, postagens)
    
    # Remove comentários relacionados
    comentarios = carregar_json(COMENTARIOS_FILE)
    comentarios = [c for c in comentarios if c['postagem_id'] != post_id]
    salvar_json(COMENTARIOS_FILE, comentarios)
    
    # Remove vistas relacionadas
    vistas = carregar_json(VISTAS_FILE)
    vistas = [v for v in vistas if v['postagem_id'] != post_id]
    salvar_json(VISTAS_FILE, vistas)
    
    return jsonify({'success': True})

@app.route('/admin/api/comentarios')
def admin_api_comentarios():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    comentarios = carregar_json(COMENTARIOS_FILE)
    usuarios = carregar_json(USUARIOS_FILE)
    
    comentarios.sort(key=lambda x: x['data_comentario'], reverse=True)
    
    return jsonify([{
        'id': c['id'],
        'texto': c['texto'],
        'postagem_id': c['postagem_id'],
        'usuario_nome': c.get('nome_usuario') or "Não quero informar meu nome",
        'data': datetime.fromisoformat(c['data_comentario']).strftime('%d/%m/%Y %H:%M')
    } for c in comentarios])

@app.route('/admin/api/comentario/<int:comentario_id>', methods=['DELETE'])
def admin_deletar_comentario(comentario_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    comentarios = carregar_json(COMENTARIOS_FILE)
    comentarios = [c for c in comentarios if c['id'] != comentario_id]
    salvar_json(COMENTARIOS_FILE, comentarios)
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Criar arquivos iniciais e postagem demo
def init_database():
    if not os.path.exists(POSTAGENS_FILE):
        post_demo = {
            'id': 1,
            'titulo': 'Bem-vindo ao Coloquei a cara e Falei!',
            'resumo': 'Este é um exemplo de postagem. O admin pode criar posts com texto, fotos e vídeos.',
            'tipo': 'texto',
            'conteudo': 'Bem-vindo ao nosso portal! Aqui você encontra as melhores notícias e conteúdo exclusivo. Marque que você viu e comente!',
            'data_postagem': datetime.now().isoformat(),
            'autor': 'Admin',
            'foto_admin': '/static/img/admin-padrao.jpg'
        }
        salvar_json(POSTAGENS_FILE, [post_demo])
    
    # Criar foto padrão admin
    os.makedirs('static/img', exist_ok=True)
    default_admin_path = 'static/img/admin-padrao.jpg'
    if not os.path.exists(default_admin_path):
        with open(default_admin_path, 'wb') as f:
            icon_base64 = "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAALTSURBVHgB7d1NbtNAGMfxZ0pFJYRoN6hU1BKQVhyhGyQ4ArcjIS5Qu2ADHID2AGmP0B4gETcgcYEWUBFok9ixP+t6DKInUWbGzmte7/ejjM2kXvz4YTyShBBCCCGEEEIIIYQQQgghhBCiC/wDEkIIIUQK2bBvR0i+KJI0TVOrjTGG/G4Yxvw+DDEnzmOMMcYYYxKz2WxsMplsZrPZ1hhT2SfOcRzHcRzHcf2fYRiGYYQQhRBCEEJwjuPkOY7jOI4jhBB5nucKIQRN0xhjTKFpWhhjzKJpGmNMURQlTdMUwzAghDDGmLCGdCWEEGmapmmaZlmWNU3zxbZt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27bt/v379//+/XtjjOGMMcYYY0yapmmmappmOaZpmmmaCkIIjDFmGIY0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdMYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxpi/6CeEEEIIIYQQQgghhLgwt9lsrLV2MplM0zT9y7Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27ZtO4QQQgghhBBCCCGEEEIIIYQQQgghhBBCCCGEEEIIIYQQQgghhPgf/AUQjEN8pBmG+AAAAABJRU5ErkJggg=="
            import base64
            f.write(base64.b64decode(icon_base64))
    
    # Criar banner padrão
    os.makedirs('static/img', exist_ok=True)
    default_banner_path = 'static/img/banner-padrao.jpg'
    if not os.path.exists(default_banner_path):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (1200, 300), color='#2e7d32')
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, 1200, 300], fill='#1976d2')
            img.save(default_banner_path)
        except:
            import shutil
            shutil.copy(default_admin_path, default_banner_path)
    
    # Configuração padrão
    if not os.path.exists(CONFIG_FILE):
        salvar_config({'banner_url': '/static/img/banner-padrao.jpg'})

init_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)