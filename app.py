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

@app.route('/reconhecer', methods=['POST'])
def reconhecer():
    foto = request.form.get('foto')
    modo = request.form.get('modo', 'login')  # 'login' ou 'cadastrar'
    if not foto:
        return jsonify({'success': False, 'error': 'Nenhuma foto fornecida'})

    if detectar_face_simulado(foto):
        foto_hash = hashlib.md5(foto.encode()).hexdigest()
        usuarios = carregar_json(USUARIOS_FILE)
        usuario = None
        for u in usuarios:
            if u['foto_hash'] == foto_hash:
                usuario = u
                break

        if usuario:
            # Usuário já existe
            usuario['ultimo_acesso'] = datetime.now().isoformat()
            if 'redes_sociais' not in usuario:
                usuario['redes_sociais'] = {'instagram': '', 'whatsapp': '', 'facebook': '', 'twitter': ''}
            salvar_json(USUARIOS_FILE, usuarios)
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario.get('nome', f"Usuario_{usuario['id']}")
            session['usuario_foto'] = usuario['foto_path']
            return jsonify({'success': True, 'redirect': url_for('home'), 'mensagem': f"👋 Seja bem vindo novamente, {usuario['nome']}!"})

        # Usuário não existe
        if modo == 'cadastrar':
            # Cadastrar nova foto
            usuario_id = len(usuarios) + 1
            nome_arquivo = f"usuario_{usuario_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            foto_path = salvar_foto(foto, nome_arquivo)
            novo_usuario = {
                'id': usuario_id,
                'nome': f"Usuario_{usuario_id}",
                'foto_path': foto_path,
                'foto_hash': foto_hash,
                'data_cadastro': datetime.now().isoformat(),
                'ultimo_acesso': datetime.now().isoformat(),
                'is_admin': False,
                'primeiro_acesso': True,
                'redes_sociais': {'instagram': '', 'whatsapp': '', 'facebook': '', 'twitter': ''}
            }
            usuarios.append(novo_usuario)
            salvar_json(USUARIOS_FILE, usuarios)
            session['usuario_id'] = novo_usuario['id']
            session['usuario_nome'] = novo_usuario['nome']
            session['usuario_foto'] = novo_usuario['foto_path']
            return jsonify({'success': True, 'redirect': url_for('home'), 'mensagem': '🎉 Cadastro realizado! Agora você pode interagir.'})
        else:
            # Modo login, usuário não existe
            return jsonify({'success': False, 'error': 'usuario_nao_existe', 'mensagem': 'Rosto não reconhecido.'})

    else:
        return jsonify({'success': False, 'error': 'Nenhum rosto detectado. Tente novamente.'})
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui-mude-em-producao'
app.config['UPLOAD_FOLDER'] = 'static/uploads/fotos'
app.config['UPLOAD_MIDIA_FOLDER'] = 'static/uploads/midias'
app.config['UPLOAD_BANNER_FOLDER'] = 'static/uploads/banners'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['ALLOWED_IMAGES'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['ALLOWED_VIDEOS'] = {'mp4', 'webm', 'avi', 'mov', 'mkv'}

# Criar pastas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_MIDIA_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_BANNER_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/postagens', exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('static/img', exist_ok=True)

# Arquivos JSON
USUARIOS_FILE = 'data/usuarios.json'
POSTAGENS_FILE = 'data/postagens.json'
COMENTARIOS_FILE = 'data/comentarios.json'
VISTAS_FILE = 'data/vistas.json'
CONFIG_FILE = 'data/config.json'

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
    if not '.' in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if tipo == 'imagem':
        return ext in app.config['ALLOWED_IMAGES']
    elif tipo == 'video':
        return ext in app.config['ALLOWED_VIDEOS']
    return False

def salvar_arquivo(arquivo, tipo, pasta='midias'):
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
    if imagem_base64 and len(imagem_base64) > 1000:
        return True
    return False

@app.route('/')
def index():
    config = carregar_config()
    return render_template('index.html', banner_url=config.get('banner_url', '/static/img/banner-padrao.jpg'))

@app.route('/reconhecer', methods=['POST'])
def reconhecer():
    foto = request.form.get('foto')
    if not foto:
        return jsonify({'success': False, 'error': 'Nenhuma foto fornecida'})

    if detectar_face_simulado(foto):
        foto_hash = hashlib.md5(foto.encode()).hexdigest()
        usuarios = carregar_json(USUARIOS_FILE)
        usuario = None
        for u in usuarios:
            if u['foto_hash'] == foto_hash:
                usuario = u
                break

        mensagem = ""
        primeiro_acesso = False

        if not usuario:
            # Primeiro acesso
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
                'is_admin': False,
                'primeiro_acesso': True,
                'redes_sociais': {
                    'instagram': '',
                    'whatsapp': '',
                    'facebook': '',
                    'twitter': ''
                }
            }
            usuarios.append(usuario)
            salvar_json(USUARIOS_FILE, usuarios)
            mensagem = "🎉 Bem-vindo(a)! Sua foto foi cadastrada com sucesso. Agora você pode comentar e interagir!"
            primeiro_acesso = True
        else:
            # Usuário já existente
            primeiro_acesso = False
            nome_usuario = usuario.get('nome', 'Amigo')
            mensagem = f"👋 Seja bem vindo novamente, {nome_usuario}! Já botou a cara, pode falar."
            # Atualizar último acesso
            usuario['ultimo_acesso'] = datetime.now().isoformat()
            if 'redes_sociais' not in usuario:
                usuario['redes_sociais'] = {'instagram': '', 'whatsapp': '', 'facebook': '', 'twitter': ''}
            salvar_json(USUARIOS_FILE, usuarios)

        # Guardar mensagem na sessão para exibir na home
        session['mensagem_boas_vindas'] = mensagem
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
    mensagem = session.pop('mensagem_boas_vindas', None)
    return render_template('home.html', usuario=usuario, banner_url=config.get('banner_url', '/static/img/banner-padrao.jpg'), mensagem_boas_vindas=mensagem)

# Rota para página de perfil
@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))
    usuarios = carregar_json(USUARIOS_FILE)
    usuario = None
    for u in usuarios:
        if u['id'] == session['usuario_id']:
            usuario = u
            break
    return render_template('perfil.html', usuario=usuario)

# API para atualizar perfil (nome, redes sociais)
@app.route('/api/perfil', methods=['POST'])
def atualizar_perfil():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    data = request.get_json()
    nome = data.get('nome', '').strip()
    redes = data.get('redes_sociais', {})
    usuarios = carregar_json(USUARIOS_FILE)
    for u in usuarios:
        if u['id'] == session['usuario_id']:
            if nome:
                u['nome'] = nome
            u['redes_sociais'] = redes
            salvar_json(USUARIOS_FILE, usuarios)
            session['usuario_nome'] = nome
            return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Usuário não encontrado'})

# API para trocar foto do perfil
@app.route('/api/perfil/foto', methods=['POST'])
def trocar_foto():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    if 'foto' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    arquivo = request.files['foto']
    if arquivo.filename == '':
        return jsonify({'error': 'Arquivo vazio'}), 400
    if not allowed_file(arquivo.filename, 'imagem'):
        return jsonify({'error': 'Formato não suportado'}), 400

    # Salvar nova foto
    ext = arquivo.filename.rsplit('.', 1)[1].lower()
    nome_arquivo = secure_filename(f"usuario_{session['usuario_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    arquivo.save(filepath)
    foto_url = f'/static/uploads/fotos/{nome_arquivo}'

    # Atualizar JSON
    usuarios = carregar_json(USUARIOS_FILE)
    for u in usuarios:
        if u['id'] == session['usuario_id']:
            # Deletar foto antiga (opcional)
            old_path = u['foto_path'].lstrip('/')
            if os.path.exists(old_path):
                os.remove(old_path)
            u['foto_path'] = foto_url
            # Atualizar hash da foto para não precisar reconhecer novamente? (opcional)
            # Não atualizamos o hash para manter login facial funcionando com a nova foto? 
            # Na verdade, o login facial usa o hash do rosto. Se ele trocar a foto manualmente, 
            # a próxima vez que entrar com a câmera, o hash será diferente. Para evitar isso,
            # podemos manter o mesmo hash (não recomendado). Melhor deixar como está: o usuário pode trocar a foto do perfil,
            # mas o login continuará usando a foto original tirada na câmera. É o esperado.
            salvar_json(USUARIOS_FILE, usuarios)
            session['usuario_foto'] = foto_url
            return jsonify({'success': True, 'foto_url': foto_url})
    return jsonify({'success': False, 'error': 'Usuário não encontrado'})

# API para obter redes sociais de um usuário (para exibir no modal)
@app.route('/api/usuario/<int:user_id>/redes')
def get_redes_sociais(user_id):
    usuarios = carregar_json(USUARIOS_FILE)
    for u in usuarios:
        if u['id'] == user_id:
            return jsonify({
                'nome': u.get('nome', f"Usuario_{user_id}"),
                'foto': u.get('foto_path', '/static/img/admin-padrao.jpg'),
                'redes': u.get('redes_sociais', {})
            })
    return jsonify({'error': 'Usuário não encontrado'}), 404

# ... (mantenha as rotas antigas de postagens, comentários, admin, etc. exatamente como estavam) ...

# A partir daqui, mantenha todas as rotas que você já tinha (api_postagens, marcar_viu, adicionar_comentario, admin, etc.)
# Para economizar espaço, vou copiar o resto do seu app.py anterior, pois essas rotas não foram alteradas.
# (na prática, você deve manter o que já funcionava)

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
    
    postagens.sort(key=lambda x: x['data_postagem'], reverse=True)
    start = (page - 1) * per_page
    end = start + per_page
    postagens_page = postagens[start:end]
    
    postagens_data = []
    for post in postagens_page:
        ja_viu = False
        for vista in vistas:
            if vista['usuario_id'] == session['usuario_id'] and vista['postagem_id'] == post['id']:
                ja_viu = True
                break
        
        comentarios_post = [c for c in comentarios if c['postagem_id'] == post['id']]
        comentarios_data = []
        for coment in comentarios_post:
            user_foto = '/static/uploads/fotos/default.jpg'
            user_nome = "Usuário"
            for u in usuarios:
                if u['id'] == coment['usuario_id']:
                    user_foto = u.get('foto_path', '/static/uploads/fotos/default.jpg')
                    user_nome = u.get('nome', f"Usuario_{coment['usuario_id']}")
                    break
            nome_exibido = coment.get('nome_usuario')
            if not nome_exibido or nome_exibido.strip() == '':
                nome_exibido = "Não quero informar meu nome"
            comentarios_data.append({
                'id': coment['id'],
                'texto': coment['texto'],
                'nome': nome_exibido,
                'foto': user_foto,
                'data': datetime.fromisoformat(coment['data_comentario']).strftime('%d/%m/%Y %H:%M'),
                'usuario_id': coment['usuario_id'],  # adicionado para referência
                'usuario_nome_real': user_nome
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
    return jsonify({'postagens': postagens_data, 'has_next': has_next, 'page': page})

@app.route('/api/postagem/<int:post_id>/viu', methods=['POST'])
def marcar_viu(post_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    vistas = carregar_json(VISTAS_FILE)
    for vista in vistas:
        if vista['usuario_id'] == session['usuario_id'] and vista['postagem_id'] == post_id:
            return jsonify({'success': False, 'error': 'Você já marcou esta postagem'})
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

# Rotas Admin (já existentes, mantenha as suas. Aqui vou colocar as essenciais)
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == 'admin123':
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
    banner_path = salvar_arquivo(arquivo, 'imagem', 'banners')
    if banner_path:
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
    if request.files:
        arquivo = request.files.get('arquivo')
        tipo = request.form.get('tipo')
        titulo = request.form.get('titulo')
        resumo = request.form.get('resumo')
        if arquivo and arquivo.filename:
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
    for post in postagens:
        if post['id'] == post_id:
            if post['tipo'] in ['foto', 'video_local']:
                filepath = post['conteudo'].lstrip('/')
                if os.path.exists(filepath):
                    os.remove(filepath)
            break
    postagens = [p for p in postagens if p['id'] != post_id]
    salvar_json(POSTAGENS_FILE, postagens)
    comentarios = carregar_json(COMENTARIOS_FILE)
    comentarios = [c for c in comentarios if c['postagem_id'] != post_id]
    salvar_json(COMENTARIOS_FILE, comentarios)
    vistas = carregar_json(VISTAS_FILE)
    vistas = [v for v in vistas if v['postagem_id'] != post_id]
    salvar_json(VISTAS_FILE, vistas)
    return jsonify({'success': True})

@app.route('/admin/api/comentarios')
def admin_api_comentarios():
    if 'usuario_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    comentarios = carregar_json(COMENTARIOS_FILE)
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
    default_admin_path = 'static/img/admin-padrao.jpg'
    if not os.path.exists(default_admin_path):
        icon_base64 = "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAALTSURBVHgB7d1NbtNAGMfxZ0pFJYRoN6hU1BKQVhyhGyQ4ArcjIS5Qu2ADHID2AGmP0B4gETcgcYEWUBFok9ixP+t6DKInUWbGzmte7/ejjM2kXvz4YTyShBBCCCGEEEIIIYQQQgghhBCiC/wDEkIIIUQK2bBvR0i+KJI0TVOrjTGG/G4Yxvw+DDEnzmOMMcYYYxKz2WxsMplsZrPZ1hhT2SfOcRzHcRzHcf2fYRiGYYQQhRBCEEJwjuPkOY7jOI4jhBB5nucKIQRN0xhjTKFpWhhjzKJpGmNMURQlTdMUwzAghDDGmLCGdCWEEGmapmmaZlmWNU3zxbZt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27bt/v379//+/XtjjOGMMcYYY0yapmmmappmOaZpmmmaCkIIjDFmGIY0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdM0TdMYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxpi/6CeEEEIIIYQQQgghhLgwt9lsrLV2MplM0zT9y7Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27Zt27ZtO4QQQgghhBBCCCGEEEIIIYQQQgghhBBCCCGEEEIIIYQQQgghhPgf/AUQjEN8pBmG+AAAAABJRU5ErkJggg=="
        import base64
        with open(default_admin_path, 'wb') as f:
            f.write(base64.b64decode(icon_base64))

    default_banner_path = 'static/img/banner-padrao.jpg'
    if not os.path.exists(default_banner_path):
        import shutil
        shutil.copy(default_admin_path, default_banner_path)

    if not os.path.exists(CONFIG_FILE):
        salvar_config({'banner_url': '/static/img/banner-padrao.jpg'})

init_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
