from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string

app = Flask(__name__)
app.secret_key = 'cle_secrete_class_master_imi'

MATIERES_OFFICIELLES = [
    "RP (Réparation de poste)",
    "Anglais",
    "Mathématiques Général",
    "Français",
    "Programmation",
    "RI (Réseau informatique)",
    "Base de données",
    "EEB (Électricité et électronique de base)",
    "Législation (Droit)",
    "Mathématiques appliquées",
    "Assistance en ligne (AS/L)",
    "EPS",
    "Optimisation de poste (OPT)"
]

CLASSES_OFFICIELLES = ["Terminale IMI 1", "Terminale IMI 2"]
SEMESTRES_OFFICIELS = ["Semestre 1", "Semestre 2"]

def generer_code_secret():
    lettre = random.choice(string.ascii_uppercase)
    chiffres = "".join(random.choices(string.digits, k=3))
    return f"{lettre}{chiffres}"

def get_db_connection():
    conn = sqlite3.connect('educmaster_mini.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS profs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    mot_de_passe TEXT NOT NULL,
                    nom TEXT NOT NULL)''')
                    
    conn.execute('''CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_eleve TEXT NOT NULL,
                    classe TEXT NOT NULL,
                    matiere TEXT NOT NULL,
                    semestre TEXT NOT NULL,
                    type_eval TEXT NOT NULL,
                    note REAL NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS eleves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    classe TEXT NOT NULL,
                    code_secret TEXT UNIQUE)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    prof_existe = conn.execute('SELECT * FROM profs WHERE email = ?', ('prof@educmaster.bj',)).fetchone()
    if not prof_existe:
        mot_de_passe_chiffre = generate_password_hash('prof123')
        conn.execute('INSERT INTO profs (email, mot_de_passe, nom) VALUES (?, ?, ?)',
                     ('prof@educmaster.bj', mot_de_passe_chiffre, 'Jean Dupont'))
        conn.commit()

    eleves_imi1 = [
        "Abel", "Pascal", "Jude", "Nornen", "Chabel", 
        "Fresnel", "Fidel", "Enock", "Cephora", "Naomi", 
        "Consolas", "Anselme", "Richnel", "Constantin", "Jadel"
    ]
    
    for e in eleves_imi1:
        existe = conn.execute('SELECT * FROM eleves WHERE nom = ? AND classe = ?', (e, 'Terminale IMI 1')).fetchone()
        if not existe:
            code_secret = generer_code_secret()
            conn.execute('INSERT INTO eleves (nom, classe, code_secret) VALUES (?, ?, ?)', (e, 'Terminale IMI 1', code_secret))
            conn.commit()

    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'prof_id' in session:
        view = request.args.get('view', 'dashboard')
        message = ''
        success_message = ''
        
        conn = get_db_connection()
        matiere_selectionnee = request.args.get('matiere', MATIERES_OFFICIELLES[0])
        classe_selectionnee = request.args.get('classe', 'Terminale IMI 1')
        semestre_selectionne = request.args.get('semestre', SEMESTRES_OFFICIELS[0])
        
        if request.method == 'POST':
            action_prof = request.form.get('action_prof')
            
            if action_prof == 'add_note':
                eleve = request.form.get('eleve')
                classe = request.form.get('classe')
                matiere = request.form.get('matiere')
                semestre = request.form.get('semestre')
                type_eval = request.form.get('type_eval')
                note = request.form.get('note')
                
                if eleve and classe and matiere and semestre and type_eval and note:
                    conn.execute('INSERT INTO notes (nom_eleve, classe, matiere, semestre, type_eval, note) VALUES (?, ?, ?, ?, ?, ?)',
                                 (eleve, classe, matiere, semestre, type_eval, note))
                    conn.commit()
                    matiere_selectionnee = matiere
                    classe_selectionnee = classe
                    semestre_selectionne = semestre
            
            elif action_prof == 'add_eleve':
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                classe_cible = request.form.get('classe_cible')
                code_saisi = request.form.get('code_secret_saisi', '').strip().upper()
                
                if nouveau_nom and classe_cible:
                    code_secret = code_saisi if code_saisi else generer_code_secret()
                    conn.execute('INSERT INTO eleves (nom, classe, code_secret) VALUES (?, ?, ?)', (nouveau_nom, classe_cible, code_secret))
                    conn.commit()

            elif action_prof == 'edit_eleve':
                eleve_id = request.form.get('eleve_id')
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                nouveau_code = request.form.get('nouveau_code', '').strip().upper()
                
                if eleve_id and nouveau_nom:
                    if nouveau_code:
                        conn.execute('UPDATE eleves SET nom = ?, code_secret = ? WHERE id = ?', (nouveau_nom, nouveau_code, eleve_id))
                    else:
                        conn.execute('UPDATE eleves SET nom = ? WHERE id = ?', (nouveau_nom, eleve_id))
                    conn.commit()

            elif action_prof == 'update_profile':
                nouveau_nom = request.form.get('nom', '').strip()
                nouvel_email = request.form.get('email', '').strip()
                if nouveau_nom and nouvel_email:
                    conn.execute('UPDATE profs SET nom = ?, email = ? WHERE id = ?', (nouveau_nom, nouvel_email, session['prof_id']))
                    conn.commit()
                    session['prof_nom'] = nouveau_nom
                    success_message = "Profil mis à jour avec succès !"

            elif action_prof == 'update_password':
                ancien_mdp = request.form.get('ancien_password', '')
                nouveau_mdp = request.form.get('nouveau_password', '')
                prof = conn.execute('SELECT * FROM profs WHERE id = ?', (session['prof_id'],)).fetchone()
                
                if prof and check_password_hash(prof['mot_de_passe'], ancien_mdp):
                    hashed_mdp = generate_password_hash(nouveau_mdp)
                    conn.execute('UPDATE profs SET mot_de_passe = ? WHERE id = ?', (hashed_mdp, session['prof_id']))
                    conn.commit()
                    success_message = "Mot de passe modifié avec succès !"
                else:
                    message = "Ancien mot de passe incorrect."

            elif action_prof == 'delete_account':
                prof_nom = session.get('prof_nom', 'Un enseignant')
                prof_id = session.get('prof_id')
                
                conn.execute('DELETE FROM profs WHERE id = ?', (prof_id,))
                msg_notif = f"Le compte du professeur {prof_nom} a été supprimé."
                conn.execute('INSERT INTO notifications (message) VALUES (?)', (msg_notif,))
                conn.commit()
                conn.close()
                
                session.clear()
                return redirect(url_for('index'))

        notes = conn.execute('SELECT * FROM notes WHERE matiere = ? AND classe = ? AND semestre = ?', 
                             (matiere_selectionnee, classe_selectionnee, semestre_selectionne)).fetchall()
        liste_eleves = conn.execute('SELECT * FROM eleves WHERE classe = ? ORDER BY nom ASC', (classe_selectionnee,)).fetchall()
        tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY nom ASC').fetchall()
        
        bilan_eleves = []
        for e in liste_eleves:
            notes_eleve = [n for n in notes if n['nom_eleve'] == e['nom']]
            n_interro = [n['note'] for n in notes_eleve if 'Interrogation' in n['type_eval']]
            n_devoir = [n['note'] for n in notes_eleve if 'Devoir' in n['type_eval']]
            
            m_interro = sum(n_interro) / len(n_interro) if n_interro else None
            m_devoir = sum(n_devoir) / len(n_devoir) if n_devoir else None
            
            if m_interro is not None and m_devoir is not None:
                m_gen = (m_interro + (m_devoir * 2)) / 3
            elif m_devoir is not None:
                m_gen = m_devoir
            elif m_interro is not None:
                m_gen = m_interro
            else:
                m_gen = None
                
            bilan_eleves.append({
                'nom': e['nom'],
                'notes': notes_eleve,
                'moy_interro': round(m_interro, 2) if m_interro is not None else '-',
                'moy_devoir': round(m_devoir, 2) if m_devoir is not None else '-',
                'moy_gen': round(m_gen, 2) if m_gen is not None else '-'
            })
            
        notifications = conn.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 10').fetchall()
        prof_info = conn.execute('SELECT * FROM profs WHERE id = ?', (session['prof_id'],)).fetchone()
        conn.close()
        
        return render_template('index.html', view=view, prof_nom=session['prof_nom'], prof_info=prof_info,
                               matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES, semestres=SEMESTRES_OFFICIELS,
                               matiere_active=matiere_selectionnee, classe_active=classe_selectionnee, semestre_actif=semestre_selectionne,
                               bilan_eleves=bilan_eleves, liste_eleves=liste_eleves, tous_eleves=tous_eleves,
                               notifications=notifications, message=message, success_message=success_message)

    view = request.args.get('view', 'login')
    message = ''
    resultats_recherche = None
    recherche_effectuee = False
    eleve_trouve = ""

    conn = get_db_connection()
    tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY nom ASC').fetchall()
    conn.close()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            conn = get_db_connection()
            prof = conn.execute('SELECT * FROM profs WHERE email = ?', (email,)).fetchone()
            
            if prof and check_password_hash(prof['mot_de_passe'], password):
                session['prof_id'] = prof['id']
                session['prof_nom'] = prof['nom']
                session.permanent = True
                
                msg_notif = f"Le professeur {prof['nom']} s'est connecté."
                conn.execute('INSERT INTO notifications (message) VALUES (?)', (msg_notif,))
                conn.commit()
                conn.close()
                return redirect(url_for('index'))
            else:
                if conn:
                    conn.close()
                message = 'Identifiants incorrects'
                view = 'login'
                
        elif action == 'register':
            nom = request.form.get('nom', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            conn = get_db_connection()
            prof_existe = conn.execute('SELECT * FROM profs WHERE email = ?', (email,)).fetchone()
            
            if prof_existe:
                message = 'Cet e-mail est déjà utilisé.'
                view = 'register'
                conn.close()
            else:
                hashed_password = generate_password_hash(password)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO profs (email, mot_de_passe, nom) VALUES (?, ?, ?)',
                             (email, hashed_password, nom))
                conn.commit()
                prof_id = cursor.lastrowid
                
                msg_notif = f"Le professeur {nom} a créé un compte et s'est connecté."
                conn.execute('INSERT INTO notifications (message) VALUES (?)', (msg_notif,))
                conn.commit()
                conn.close()

                session['prof_id'] = prof_id
                session['prof_nom'] = nom
                return redirect(url_for('index'))

        elif action == 'search_by_code':
            view = 'parent_space'
            recherche_effectuee = True
            code_secret_saisi = request.form.get('code_secret', '').strip().upper()
            
            conn = get_db_connection()
            eleve = conn.execute('SELECT * FROM eleves WHERE UPPER(code_secret) = ?', (code_secret_saisi,)).fetchone()
            
            if eleve:
                eleve_trouve = f"{eleve['nom']} ({eleve['classe']})"
                resultats_recherche = conn.execute(
                    'SELECT semestre, matiere, type_eval, note FROM notes WHERE LOWER(nom_eleve) = LOWER(?) AND classe = ?',
                    (eleve['nom'], eleve['classe'])
                ).fetchall()
            else:
                message = "Code secret incorrect."
                resultats_recherche = []
            conn.close()

    return render_template('index.html', view=view, message=message, 
                           matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES, semestres=SEMESTRES_OFFICIELS, tous_eleves=tous_eleves,
                           resultats=resultats_recherche, recherche_effectuee=recherche_effectuee,
                           eleve_trouve=eleve_trouve)

@app.route('/delete/<int:id>')
def delete_note(id):
    if 'prof_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    conn.execute('DELETE FROM notes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_eleve/<int:id>')
def delete_eleve(id):
    if 'prof_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    conn.execute('DELETE FROM eleves WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export_csv')
def export_csv():
    if 'prof_id' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    notes = conn.execute('SELECT nom_eleve, classe, matiere, semestre, type_eval, note FROM notes ORDER BY classe, semestre, nom_eleve').fetchall()
    conn.close()
    
    def generate():
        yield "Eleve,Classe,Matiere,Semestre,Evaluation,Note\n"
        for n in notes:
            yield f"{n['nom_eleve']},{n['classe']},{n['matiere']},{n['semestre']},{n['type_eval']},{n['note']}\n"

    return Response(generate(), mimetype='text/csv', 
                    headers={"Content-Disposition": "attachment; filename=notes_class_master_imi.csv"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)