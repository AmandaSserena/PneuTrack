import traceback  # para mostrar stack trace em DEV
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from sqlalchemy import func, or_

# === App / Paths / DB (usa caminho absoluto) ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "pneutrack.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-pneutrack"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Uploads
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
app.config["ALLOWED_EXT"] = {"png", "jpg", "jpeg", "pdf"}

def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXT"]

# ============== MODELS ==============
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # gestor | borracheiro
    password = db.Column(db.String(128), nullable=False)  # demo only

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anexos = db.relationship("Anexo", backref="veiculo", cascade="all, delete-orphan")
    placa = db.Column(db.String(10), unique=True, nullable=False)
    motorista = db.Column(db.String(80), nullable=False)
    alerta_km_max = db.Column(db.Integer, default=50000)
    eixos = db.relationship("Eixo", backref="veiculo", cascade="all, delete-orphan")
    posicoes = db.relationship("PosicaoPneu", backref="veiculo", cascade="all, delete-orphan")
    historicos = db.relationship("Historico", backref="veiculo", cascade="all, delete-orphan")
    servicos = db.relationship("ServicoAutorizado", backref="veiculo", cascade="all, delete-orphan")

class Eixo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"), nullable=False)
    nome = db.Column(db.String(60), nullable=False)
    ordem = db.Column(db.Integer, default=0)

class Pneu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(64))
    numero_fogo = db.Column(db.String(20))
    numero_serie = db.Column(db.String(40))
    marca = db.Column(db.String(40))
    modelo = db.Column(db.String(40))
    medida = db.Column(db.String(40))
    status = db.Column(db.String(20), default="estoque")  # estoque, ativo, conserto, recapagem, vendido, sucateado, rodizio
    pressao = db.Column(db.Float, default=0)
    sulco = db.Column(db.Float, default=0)

class PosicaoPneu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"), nullable=False)
    eixo_id = db.Column(db.Integer, db.ForeignKey("eixo.id"))
    pos_label = db.Column(db.String(60), nullable=False)
    pneu_id = db.Column(db.Integer, db.ForeignKey("pneu.id"))
    pneu = db.relationship("Pneu")

class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"))
    pneu_id = db.Column(db.Integer, db.ForeignKey("pneu.id"))
    acao = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    detalhes = db.Column(db.String(200))

class ServicoAutorizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="autorizado")  # autorizado, concluido, cancelado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anexos = db.relationship("Anexo", backref="ordem", cascade="all, delete-orphan")
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="aberta")  # aberta, aprovada, concluida, cancelada
    custo_total = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship("ItemOS", backref="os", cascade="all, delete-orphan")

class ItemOS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"), nullable=False)
    descricao = db.Column(db.String(120), nullable=False)
    quantidade = db.Column(db.Float, default=1)
    valor_unit = db.Column(db.Float, default=0)
    @property
    def subtotal(self):
        return round((self.quantidade or 0) * (self.valor_unit or 0), 2)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120))
    action = db.Column(db.String(50))
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destino_role = db.Column(db.String(20))  # gestor ou borracheiro
    mensagem = db.Column(db.String(200))
    link = db.Column(db.String(120))
    lida = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Inspecao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"), nullable=False)
    status = db.Column(db.String(20), default="aberta")  # aberta, enviada, aprovada, reprovada
    observacoes = db.Column(db.String(300))

class InspecaoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspecao_id = db.Column(db.Integer, db.ForeignKey("inspecao.id"), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    ok = db.Column(db.Boolean, default=False)
    obs = db.Column(db.String(200))

class Anexo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"))
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculo.id"))
    filename = db.Column(db.String(200))
    original = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============== HELPERS ==============
def current_user():
    email = session.get("email")
    if not email:
        return None
    return User.query.filter_by(email=email).first()

def audit(action, entity, entity_id=None, details=""):
    u = current_user()
    db.session.add(
        AuditLog(
            user_email=(u.email if u else None),
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
        )
    )
    db.session.commit()

def login_required(role=None):
    def decorator(fn):
        def inner(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if role and user.role != role:
                flash("Acesso negado para este perfil.", "error")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return decorator

def notify(destino_role, mensagem, link="#"):
    db.session.add(Notificacao(destino_role=destino_role, mensagem=mensagem, link=link))
    db.session.commit()

# ---------- ERROR HANDLER (DEV) ----------
@app.errorhandler(Exception)
def handle_any_exception(e):
    # Mostra o stack trace no navegador para diagnosticar rápido em DEV.
    return f"<h2>Erro Interno</h2><pre>{traceback.format_exc()}</pre>", 500

# ============== SEED / INIT DB ==============
def seed_demo():
    if User.query.count() > 0:
        return
    db.session.add_all([
        User(email="gestor@empresa.com", name="Gestor", role="gestor", password="123456"),
        User(email="tecnico@empresa.com", name="Borracheiro", role="borracheiro", password="123456"),
    ])

    p1 = Pneu(numero_fogo="F123", numero_serie="S-0001", marca="Michelin", modelo="X Multi", medida="295/80 R22.5", status="ativo", pressao=100, sulco=12.5)
    p2 = Pneu(numero_fogo="F124", numero_serie="S-0002", marca="Michelin", modelo="X Multi", medida="295/80 R22.5", status="ativo", pressao=100, sulco=12.0)
    p3 = Pneu(numero_fogo="F221", numero_serie="S-0101", marca="Pirelli", modelo="FG:01", medida="275/80 R22.5", status="ativo", pressao=95, sulco=10.2)
    p4 = Pneu(numero_fogo="F222", numero_serie="S-0102", marca="Pirelli", modelo="FG:01", medida="275/80 R22.5", status="ativo", pressao=96, sulco=9.8)
    p5 = Pneu(numero_fogo="F223", numero_serie="S-0103", marca="Pirelli", modelo="FG:01", medida="275/80 R22.5", status="ativo", pressao=94, sulco=9.7)
    p6 = Pneu(numero_fogo="F224", numero_serie="S-0104", marca="Pirelli", modelo="FG:01", medida="275/80 R22.5", status="ativo", pressao=95, sulco=10.1)
    e1 = Pneu(numero_serie="S-1000", marca="Bridgestone", modelo="R268", medida="295/80 R22.5", status="estoque", pressao=0, sulco=0)
    db.session.add_all([p1,p2,p3,p4,p5,p6,e1])

    v1 = Veiculo(placa="ABC1D23", motorista="João Silva", alerta_km_max=50000)
    db.session.add(v1); db.session.flush()
    ex_d = Eixo(veiculo_id=v1.id, nome="Dianteiro", ordem=1)
    ex_t1 = Eixo(veiculo_id=v1.id, nome="Traseiro 1º Eixo", ordem=2)
    db.session.add_all([ex_d, ex_t1]); db.session.flush()
    db.session.add_all([
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_d.id, pos_label="Dianteiro Esquerdo", pneu=p1),
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_d.id, pos_label="Dianteiro Direito", pneu=p2),
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_t1.id, pos_label="Externo Esquerdo", pneu=p3),
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_t1.id, pos_label="Interno Esquerdo", pneu=p4),
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_t1.id, pos_label="Interno Direito", pneu=p5),
        PosicaoPneu(veiculo_id=v1.id, eixo_id=ex_t1.id, pos_label="Externo Direito", pneu=p6),
    ])

    v2 = Veiculo(placa="DEF4G56", motorista="Maria Souza", alerta_km_max=48000)
    db.session.add(v2); db.session.flush()
    ex2_d = Eixo(veiculo_id=v2.id, nome="Dianteiro", ordem=1)
    db.session.add(ex2_d); db.session.flush()
    db.session.add_all([
        PosicaoPneu(veiculo_id=v2.id, eixo_id=ex2_d.id, pos_label="Dianteiro Esquerdo"),
        PosicaoPneu(veiculo_id=v2.id, eixo_id=ex2_d.id, pos_label="Dianteiro Direito"),
    ])
    db.session.commit()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db.create_all()
    seed_demo()

# garante o banco ao importar
try:
    with app.app_context():
        init_db()
except Exception as e:
    app.logger.exception("Falha ao inicializar DB: %s", e)

# ============== ROUTES ==============
@app.route("/")
def home():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user.role == "gestor":
        return redirect(url_for("gestor_dashboard"))
    return redirect(url_for("borracheiro_dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        senha = request.form.get("senha","")
        user = User.query.filter_by(email=email).first()
        if user and user.password == senha:
            session["email"] = email
            return redirect(url_for("home"))
        flash("Credenciais inválidas.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---- Gestor ----
@app.route("/gestor")
@login_required(role="gestor")
def gestor_dashboard():
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    estoque = Pneu.query.filter_by(status="estoque").all()
    servicos = ServicoAutorizado.query.order_by(ServicoAutorizado.created_at.desc()).all()
    return render_template("gestor_dashboard.html", veiculos=veiculos, estoque=estoque, servicos=servicos)

@app.route("/gestor/autorizar", methods=["POST"])
@login_required(role="gestor")
def gestor_autorizar():
    veiculo_id = int(request.form["veiculo_id"])
    descricao = request.form["descricao"]
    s = ServicoAutorizado(veiculo_id=veiculo_id, descricao=descricao, status="autorizado")
    db.session.add(s); db.session.commit()
    v = Veiculo.query.get(veiculo_id)
    notify("borracheiro", f"Serviço autorizado para o veículo {v.placa}", url_for("servicos_autorizados"))
    flash("Serviço autorizado e enviado ao borracheiro.", "ok")
    return redirect(url_for("gestor_dashboard"))

@app.route("/servicos-autorizados")
@login_required()
def servicos_autorizados():
    itens = ServicoAutorizado.query.order_by(ServicoAutorizado.created_at.desc()).all()
    return render_template("servicos_autorizados.html", servicos=itens)

# ---- RFID/Código de barras ----
@app.route("/barcode", methods=["GET","POST"])
@login_required(role="gestor")
def barcode_tool():
    result = None
    if request.method == "POST":
        codebar = request.form.get("codigo_barras","").strip()
        result = Pneu.query.filter_by(codigo_barras=codebar).first()
        if not result:
            flash("Nenhum pneu com esse código.", "error")
    return render_template("barcode.html", result=result)

@app.route("/pneus/<int:pid>/definir-barcode", methods=["POST"])
@login_required(role="gestor")
def pneus_set_barcode(pid):
    p = Pneu.query.get_or_404(pid)
    p.codigo_barras = request.form.get("codigo_barras","").strip() or None
    db.session.commit()
    audit("editar","Pneu", p.id, "definir codigo_barras")
    flash("Código de barras definido.", "ok")
    return redirect(url_for("pneus_editar", pid=p.id))

# ---- CRUD Pneus ----
@app.route("/pneus")
@login_required()
def pneus_list():
    q = request.args.get("q","").strip()
    base = Pneu.query
    if q:
        like = f"%{q}%"
        base = base.filter(or_(
            Pneu.numero_serie.like(like),
            Pneu.marca.like(like),
            Pneu.modelo.like(like),
            Pneu.medida.like(like)
        ))
    pneus = base.order_by(Pneu.id.desc()).all()
    return render_template("pneus_list.html", pneus=pneus, q=q)

@app.route("/pneus/novo", methods=["GET","POST"])
@login_required(role="gestor")
def pneus_novo():
    if request.method == "POST":
        p = Pneu(
            numero_fogo=request.form.get("numero_fogo"),
            numero_serie=request.form["numero_serie"],
            marca=request.form.get("marca"),
            modelo=request.form.get("modelo"),
            medida=request.form.get("medida"),
            status=request.form.get("status","estoque"),
            pressao=float(request.form.get("pressao") or 0),
            sulco=float(request.form.get("sulco") or 0),
        )
        db.session.add(p); db.session.commit()
        audit("criar","Pneu"); flash("Pneu cadastrado.", "ok")
        return redirect(url_for("pneus_list"))
    return render_template("pneus_form.html", pneu=None)

@app.route("/pneus/<int:pid>/editar", methods=["GET","POST"])
@login_required(role="gestor")
def pneus_editar(pid):
    p = Pneu.query.get_or_404(pid)
    if request.method == "POST":
        for f in ["numero_fogo","numero_serie","marca","modelo","medida","status"]:
            setattr(p, f, request.form.get(f) or getattr(p,f))
        p.pressao = float(request.form.get("pressao") or 0)
        p.sulco = float(request.form.get("sulco") or 0)
        db.session.commit()
        audit("editar","Pneu", p.id); flash("Pneu atualizado.", "ok")
        return redirect(url_for("pneus_list"))
    return render_template("pneus_form.html", pneu=p)

@app.route("/pneus/<int:pid>/excluir", methods=["POST"])
@login_required(role="gestor")
def pneus_excluir(pid):
    p = Pneu.query.get_or_404(pid)
    db.session.delete(p); db.session.commit()
    audit("excluir","Pneu", p.id); flash("Pneu excluído.", "ok")
    return redirect(url_for("pneus_list"))

# ---- CRUD Veículos + Eixos ----
@app.route("/veiculos")
@login_required()
def veiculos_list():
    vs = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("veiculos_list.html", veiculos=vs)

@app.route("/veiculos/novo", methods=["GET","POST"])
@login_required(role="gestor")
def veiculos_novo():
    if request.method == "POST":
        v = Veiculo(placa=request.form["placa"], motorista=request.form["motorista"], alerta_km_max=int(request.form.get("alerta_km_max") or 50000))
        db.session.add(v); db.session.commit()
        audit("criar","Veiculo"); flash("Veículo cadastrado.", "ok")
        return redirect(url_for("veiculos_list"))
    return render_template("veiculos_form.html", v=None)

@app.route("/veiculos/<int:vid>/editar", methods=["GET","POST"])
@login_required(role="gestor")
def veiculos_editar(vid):
    v = Veiculo.query.get_or_404(vid)
    if request.method == "POST":
        v.placa = request.form["placa"]
        v.motorista = request.form["motorista"]
        v.alerta_km_max = int(request.form.get("alerta_km_max") or v.alerta_km_max)
        db.session.commit()
        audit("editar","Veiculo", v.id); flash("Veículo atualizado.", "ok")
        return redirect(url_for("veiculos_list"))
    return render_template("veiculos_form.html", v=v)

@app.route("/veiculos/<int:vid>/excluir", methods=["POST"])
@login_required(role="gestor")
def veiculos_excluir(vid):
    v = Veiculo.query.get_or_404(vid)
    db.session.delete(v); db.session.commit()
    audit("excluir","Veiculo", v.id); flash("Veículo excluído.", "ok")
    return redirect(url_for("veiculos_list"))

@app.route("/veiculo/<int:vid>")
@login_required()
def veiculo_detail(vid):
    v = Veiculo.query.get_or_404(vid)
    eixos = Eixo.query.filter_by(veiculo_id=v.id).order_by(Eixo.ordem).all()
    posicoes = PosicaoPneu.query.filter_by(veiculo_id=v.id).all()
    grouped = {}
    for p in posicoes:
        grouped.setdefault(p.eixo_id, []).append(p)
    return render_template("veiculo_detail.html", v=v, eixos=eixos, grouped=grouped)

# Eixos
@app.route("/veiculos/<int:vid>/eixos/novo", methods=["POST"])
@login_required(role="gestor")
def eixo_novo(vid):
    v = Veiculo.query.get_or_404(vid)
    e = Eixo(veiculo_id=v.id, nome=request.form["nome"], ordem=int(request.form.get("ordem") or 0))
    db.session.add(e); db.session.commit()
    audit("criar","Eixo", e.id, f"vid={v.id}"); flash("Eixo adicionado.", "ok")
    return redirect(url_for("veiculo_detail", vid=v.id))

@app.route("/eixos/<int:eid>/excluir", methods=["POST"])
@login_required(role="gestor")
def eixo_excluir(eid):
    e = Eixo.query.get_or_404(eid)
    vid = e.veiculo_id
    db.session.delete(e); db.session.commit()
    audit("excluir","Eixo", e.id); flash("Eixo removido.", "ok")
    return redirect(url_for("veiculo_detail", vid=vid))

# Instalar/Desinstalar Pneu
@app.route("/veiculo/<int:vid>/posicao/<int:pid>/instalar", methods=["GET","POST"])
@login_required(role="gestor")
def instalar_pneu(vid, pid):
    v = Veiculo.query.get_or_404(vid)
    pos = PosicaoPneu.query.get_or_404(pid)
    estoque = Pneu.query.filter_by(status="estoque").order_by(Pneu.marca).all()
    if request.method == "POST":
        pneu_id = int(request.form["pneu_id"])
        pneu = Pneu.query.get_or_404(pneu_id)
        pos.pneu_id = pneu.id
        pneu.status = "ativo"
        db.session.commit()
        audit("instalar","Pneu", pneu.id, f"vid={v.id} pos={pos.pos_label}")
        flash("Pneu instalado na posição.", "ok")
        return redirect(url_for("veiculo_detail", vid=v.id))
    return render_template("instalar_pneu.html", v=v, pos=pos, estoque=estoque)

@app.route("/veiculo/<int:vid>/posicao/<int:pid>/desinstalar", methods=["POST"])
@login_required(role="gestor")
def desinstalar_pneu(vid, pid):
    v = Veiculo.query.get_or_404(vid)
    pos = PosicaoPneu.query.get_or_404(pid)
    if pos.pneu:
        pneu_id = pos.pneu.id
        pos.pneu.status = "estoque"
        pos.pneu_id = None
        db.session.commit()
        audit("desinstalar","Pneu", pneu_id, f"vid={v.id} pos={pos.pos_label}")
        flash("Pneu desinstalado e enviado ao estoque.", "ok")
    return redirect(url_for("veiculo_detail", vid=v.id))

# ---- OS ----
@app.route("/os")
@login_required()
def os_list():
    os_list = OrdemServico.query.order_by(OrdemServico.created_at.desc()).all()
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("os_list.html", os_list=os_list, veiculos=veiculos)

@app.route("/os/nova", methods=["POST"])
@login_required(role="gestor")
def os_nova():
    veiculo_id = int(request.form["veiculo_id"])
    descricao = request.form["descricao"]
    osr = OrdemServico(veiculo_id=veiculo_id, descricao=descricao, status="aberta", custo_total=0)
    db.session.add(osr); db.session.commit()
    audit("criar","OS", osr.id)
    notify("gestor", f"OS criada para veículo ID {veiculo_id}", url_for("os_detalhe", os_id=osr.id))
    flash("OS criada.", "ok")
    return redirect(url_for("os_detalhe", os_id=osr.id))

@app.route("/os/<int:os_id>")
@login_required()
def os_detalhe(os_id):
    osr = OrdemServico.query.get_or_404(os_id)
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("os_detail.html", os=osr, veiculos=veiculos)

@app.route("/os/<int:os_id>/item", methods=["POST"])
@login_required(role="gestor")
def os_add_item(os_id):
    osr = OrdemServico.query.get_or_404(os_id)
    it = ItemOS(
        os_id=osr.id,
        descricao=request.form["descricao"],
        quantidade=float(request.form.get("quantidade") or 1),
        valor_unit=float(request.form.get("valor_unit") or 0),
    )
    db.session.add(it); db.session.flush()
    osr.custo_total = sum(i.subtotal for i in osr.itens)
    db.session.commit()
    audit("criar","ItemOS", it.id, f"os={osr.id}")
    flash("Item adicionado.", "ok")
    return redirect(url_for("os_detalhe", os_id=osr.id))

@app.route("/os/item/<int:item_id>/excluir", methods=["POST"])
@login_required(role="gestor")
def os_del_item(item_id):
    it = ItemOS.query.get_or_404(item_id)
    os_id = it.os_id
    db.session.delete(it); db.session.commit()
    osr = OrdemServico.query.get(os_id)
    osr.custo_total = sum(i.subtotal for i in osr.itens)
    db.session.commit()
    audit("excluir","ItemOS", it.id, f"os={os_id}")
    flash("Item removido.", "ok")
    return redirect(url_for("os_detalhe", os_id=os_id))

@app.route("/os/<int:os_id>/status", methods=["POST"])
@login_required(role="gestor")
def os_status(os_id):
    osr = OrdemServico.query.get_or_404(os_id)
    osr.status = request.form["status"]
    db.session.commit()
    audit("alterar_status","OS", osr.id, f"novo={osr.status}")
    notify("borracheiro", f"Status da OS #{osr.id} atualizado para {osr.status}", url_for("os_detalhe", os_id=osr.id))
    flash("Status da OS atualizado.", "ok")
    return redirect(url_for("os_detalhe", os_id=os_id))

# ---- Borracheiro ----
@app.route("/borracheiro")
@login_required(role="borracheiro")
def borracheiro_dashboard():
    return render_template("borracheiro_dashboard.html")

@app.route("/fila")
@login_required(role="borracheiro")
def fila():
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("fila.html", veiculos=veiculos)

# ---- Notificações ----
@app.route("/notificacoes")
@login_required()
def notificacoes():
    u = current_user()
    notes = Notificacao.query.filter_by(destino_role=u.role).order_by(Notificacao.created_at.desc()).all()
    return render_template("notificacoes.html", notes=notes)

@app.route("/notificacoes/<int:nid>/lida", methods=["POST"])
@login_required()
def notificacao_lida(nid):
    n = Notificacao.query.get_or_404(nid)
    n.lida = True
    db.session.commit()
    return redirect(url_for("notificacoes"))

# ---- Inspeção / Checklist ----
CHECKLIST_DEFAULT = [
    "Calibragem verificada",
    "Vazamento de ar",
    "Danos visuais (cortes/bolhas)",
    "Desgaste irregular",
    "Torque porca de roda verificado",
]

@app.route("/veiculo/<int:vid>/inspecao/nova", methods=["POST"])
@login_required(role="borracheiro")
def inspecao_nova(vid):
    v = Veiculo.query.get_or_404(vid)
    ins = Inspecao(veiculo_id=v.id, status="aberta")
    db.session.add(ins); db.session.flush()
    for t in CHECKLIST_DEFAULT:
        db.session.add(InspecaoItem(inspecao_id=ins.id, titulo=t, ok=False))
    db.session.commit()
    audit("criar","Inspecao", ins.id)
    return redirect(url_for("inspecao_editar", iid=ins.id))

@app.route("/inspecao/<int:iid>", methods=["GET","POST"])
@login_required()
def inspecao_editar(iid):
    ins = Inspecao.query.get_or_404(iid)
    itens = InspecaoItem.query.filter_by(inspecao_id=ins.id).all()
    if request.method == "POST":
        for it in itens:
            it.ok = True if request.form.get(f"ok_{it.id}") == "on" else False
            it.obs = request.form.get(f"obs_{it.id}")
        ins.observacoes = request.form.get("observacoes")
        db.session.commit()
        audit("editar","Inspecao", ins.id)
        flash("Checklist salvo.", "ok")
        return redirect(url_for("inspecao_editar", iid=ins.id))
    v = Veiculo.query.get(ins.veiculo_id)
    return render_template("inspecao.html", ins=ins, itens=itens, v=v)

@app.route("/inspecao/<int:iid>/enviar", methods=["POST"])
@login_required(role="borracheiro")
def inspecao_enviar(iid):
    ins = Inspecao.query.get_or_404(iid)
    ins.status = "enviada"
    db.session.commit()
    v = Veiculo.query.get(ins.veiculo_id)
    notify("gestor", f"Checklist enviado para o veículo {v.placa}", url_for("inspecao_editar", iid=ins.id))
    audit("enviar","Inspecao", ins.id)
    flash("Inspeção enviada para aprovação do gestor.", "ok")
    return redirect(url_for("borracheiro_dashboard"))

@app.route("/inspecao/<int:iid>/status", methods=["POST"])
@login_required(role="gestor")
def inspecao_status(iid):
    ins = Inspecao.query.get_or_404(iid)
    ins.status = request.form["status"]
    db.session.commit()
    v = Veiculo.query.get(ins.veiculo_id)
    notify("borracheiro", f"Inspeção do veículo {v.placa} foi {ins.status}", url_for("inspecao_editar", iid=ins.id))
    audit("alterar_status","Inspecao", ins.id, f"novo={ins.status}")
    flash("Status da inspeção atualizado.", "ok")
    return redirect(url_for("gestor_dashboard"))

# ---- Uploads ----
@app.route("/upload/os/<int:os_id>", methods=["POST"])
@login_required()
def upload_os(os_id):
    f = request.files.get("arquivo")
    if not f or not allowed_file(f.filename):
        flash("Arquivo inválido (png, jpg, jpeg, pdf).", "error")
        return redirect(url_for("os_detalhe", os_id=os_id))
    name = secure_filename(f.filename)
    save_as = f"{int(datetime.utcnow().timestamp())}_{name}"
    f.save(os.path.join(app.config["UPLOAD_FOLDER"], save_as))
    db.session.add(Anexo(os_id=os_id, filename=save_as, original=name))
    db.session.commit()
    flash("Anexo enviado.", "ok")
    return redirect(url_for("os_detalhe", os_id=os_id))

@app.route("/upload/veiculo/<int:vid>", methods=["POST"])
@login_required()
def upload_veiculo(vid):
    f = request.files.get("arquivo")
    if not f or not allowed_file(f.filename):
        flash("Arquivo inválido (png, jpg, jpeg, pdf).", "error")
        return redirect(url_for("veiculo_detail", vid=vid))
    name = secure_filename(f.filename)
    save_as = f"{int(datetime.utcnow().timestamp())}_{name}"
    f.save(os.path.join(app.config["UPLOAD_FOLDER"], save_as))
    db.session.add(Anexo(veiculo_id=vid, filename=save_as, original=name))
    db.session.commit()
    flash("Anexo enviado.", "ok")
    return redirect(url_for("veiculo_detail", vid=vid))

@app.route("/anexos/<path:filename>")
@login_required()
def serve_anexo(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

# ---- CLI ----
@app.cli.command("init-db")
def init_db_cli():
    db.drop_all()
    db.create_all()
    seed_demo()
    print("Banco inicializado com dados de exemplo.")

# ---- MAIN ----
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
