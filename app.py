from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string
import os
from openai import OpenAI

# 1. L'application Flask et sa clé secrète pour les sessions
app = Flask(__name__)
app.secret_key = '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"'

# 2. Le client OpenAI avec ta clé API
client = OpenAI(api_key="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")
# Le reste de ton code avec @app.route vient après...

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

def reponse_ia_automatique(question_parent, nom_eleve):
    """Génère une réponse intelligente via l'API OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # Si la clé n'est pas encore définie, on utilise un repli automatique propre
    if not api_key:
        return f"Bonjour ! J'ai bien transmis votre message concernant {nom_eleve} à l'équipe pédagogique. Un professeur vous répondra sous peu."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Tu es l'assistant virtuel de la plateforme Class Master IMI. Tu réponds de manière très courtoise, concise et rassurante aux parents de l'élève {nom_eleve}. Rappelle-leur si besoin qu'un enseignant ou l'administration reste également à disposition."
                },
                {"role": "user", "content": question_parent}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erreur OpenAI : {e}")
        return f"Bonjour ! Votre message concernant {nom_eleve} a bien été enregistré. L'équipe pédagogique vous répondra dans les plus brefs délais."

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

    conn.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auteur TEXT NOT NULL,
                    role TEXT NOT NULL,
                    contenu TEXT NOT NULL,
                    date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS config (
                    cle TEXT PRIMARY KEY,
                    valeur TEXT NOT NULL)''')
    
    code_admin_existe = conn.execute('SELECT * FROM config WHERE cle = ?', ('admin_code',)).fetchone()
    if not code_admin_existe:
        conn.execute('INSERT INTO config (cle, valeur) VALUES (?, ?)', ('admin_code', 'admin123'))
        conn.commit()
    
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
    if session.get('is_admin'):
        view = request.args.get('view', 'admin_space')
        message = ''
        success_message_admin = ''
        conn = get_db_connection()
        
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'admin_add_eleve':
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                classe_cible = request.form.get('classe_cible')
                code_saisi = request.form.get('code_secret_saisi', '').strip().upper()
                
                if nouveau_nom and classe_cible:
                    code_secret = code_saisi if code_saisi else generer_code_secret()
                    try:
                        conn.execute('INSERT INTO eleves (nom, classe, code_secret) VALUES (?, ?, ?)', (nouveau_nom, classe_cible, code_secret))
                        conn.commit()
                        success_message_admin = f"Élève {nouveau_nom} ajouté avec succès !"
                    except sqlite3.IntegrityError:
                        message = "Ce code secret existe déjà."

            elif action == 'admin_change_code':
                ancien_code = request.form.get('ancien_admin_code', '').strip()
                nouveau_code = request.form.get('nouveau_admin_code', '').strip()
                cfg = conn.execute('SELECT valeur FROM config WHERE cle = ?', ('admin_code',)).fetchone()
                code_actuel = cfg['valeur'] if cfg else 'admin123'

                if ancien_code == code_actuel:
                    if nouveau_code:
                        conn.execute('UPDATE config SET valeur = ? WHERE cle = ?', (nouveau_code, 'admin_code'))
                        conn.commit()
                        success_message_admin = "Code administrateur modifié avec succès !"
                    else:
                        message = "Le nouveau code ne peut pas être vide."
                else:
                    message = "L'ancien code administrateur est incorrect."
                view = 'admin_settings'
                
            elif action == 'envoyer_message_admin':
                contenu_msg = request.form.get('contenu_msg', '').strip()
                if contenu_msg:
                    conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                                 ("Administrateur", "admin", contenu_msg))
                    conn.commit()

        tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY classe ASC, nom ASC').fetchall()
        messages_recents = conn.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 15').fetchall()
        conn.close()
        return render_template('index.html', view=view, tous_eleves=tous_eleves, 
                               classes=CLASSES_OFFICIELLES, message=message, success_message_admin=success_message_admin,
                               messages_recents=messages_recents)

    if 'prof_id' in session:
        view = request.args.get('view', 'dashboard')
        message = ''
        success_message = ''
        
        conn = get_db_connection()
        prof_info = conn.execute('SELECT * FROM profs WHERE id = ?', (session['prof_id'],)).fetchone()
        
        matiere_selectionnee = request.args.get('matiere', MATIERES_OFFICIELLES[0])
        classe_selectionnee = request.args.get('classe', 'Terminale IMI 1')
        semestre_selectionne = request.args.get('semestre', SEMESTRES_OFFICIELS[0])
        
        if request.method == 'POST':
            action_prof = request.form.get('action_prof')
            if action_prof == 'save_all_notes':
                types_eval = ["Interrogation 1", "Interrogation 2", "Interrogation 3", "Devoir 1", "Devoir 2"]
                liste_eleves = conn.execute('SELECT nom FROM eleves WHERE classe = ?', (classe_selectionnee,)).fetchall()
                
                for e in liste_eleves:
                    nom_eleve = e['nom']
                    for t_eval in types_eval:
                        field_name = f"note_{nom_eleve}_{t_eval.replace(' ', '-')}"
                        valeur_saisie = request.form.get(field_name, '').strip()
                        
                        existante = conn.execute(
                            'SELECT id FROM notes WHERE nom_eleve = ? AND classe = ? AND matiere = ? AND semestre = ? AND type_eval = ?',
                            (nom_eleve, classe_selectionnee, matiere_selectionnee, semestre_selectionne, t_eval)
                        ).fetchone()
                        
                        if valeur_saisie != '':
                            try:
                                note_val = float(valeur_saisie)
                                if 0 <= note_val <= 20:
                                    if existante:
                                        conn.execute('UPDATE notes SET note = ? WHERE id = ?', (note_val, existante['id']))
                                    else:
                                        conn.execute(
                                            'INSERT INTO notes (nom_eleve, classe, matiere, semestre, type_eval, note) VALUES (?, ?, ?, ?, ?, ?)',
                                            (nom_eleve, classe_selectionnee, matiere_selectionnee, semestre_selectionne, t_eval, note_val)
                                        )
                            except ValueError:
                                pass
                        else:
                            if existante:
                                conn.execute('DELETE FROM notes WHERE id = ?', (existante['id'],))
                                
                conn.commit()
                success_message = "Notes mises à jour avec succès !"

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
                if prof_info and check_password_hash(prof_info['mot_de_passe'], ancien_mdp):
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
                
            elif action_prof == 'envoyer_message_prof':
                contenu_msg = request.form.get('contenu_msg', '').strip()
                nom_prof = session.get('prof_nom', 'Enseignant')
                if contenu_msg:
                    conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                                 (f"Prof. {nom_prof}", "prof", contenu_msg))
                    conn.commit()

        notes = conn.execute('SELECT * FROM notes WHERE matiere = ? AND classe = ? AND semestre = ?', 
                             (matiere_selectionnee, classe_selectionnee, semestre_selectionne)).fetchall()
        liste_eleves = conn.execute('SELECT * FROM eleves WHERE classe = ? ORDER BY nom ASC', (classe_selectionnee,)).fetchall()
        
        bilan_eleves = []
        for e in liste_eleves:
            notes_eleve = [n for n in notes if n['nom_eleve'] == e['nom']]
            notes_dict = {n['type_eval']: n['note'] for n in notes_eleve}
            
            i1 = notes_dict.get('Interrogation 1', '')
            i2 = notes_dict.get('Interrogation 2', '')
            i3 = notes_dict.get('Interrogation 3', '')
            d1 = notes_dict.get('Devoir 1', '')
            d2 = notes_dict.get('Devoir 2', '')
            
            n_interro = [n['note'] for n in notes_eleve if 'Interrogation' in n['type_eval']]
            n_devoir = [n['note'] for n in notes_eleve if 'Devoir' in n['type_eval']]
            
            m_interro = sum(n_interro) / len(n_interro) if n_interro else None
            m_devoir = sum(n_devoir) / len(n_devoir) if n_devoir else None
            
            toutes_notes = [n['note'] for n in notes_eleve]
            m_gen = sum(toutes_notes) / len(toutes_notes) if toutes_notes else None
                
            bilan_eleves.append({
                'nom': e['nom'],
                'notes': notes_eleve,
                'i1': i1, 'i2': i2, 'i3': i3, 'd1': d1, 'd2': d2,
                'moy_interro': round(m_interro, 2) if m_interro is not None else '-',
                'moy_devoir': round(m_devoir, 2) if m_devoir is not None else '-',
                'moy_gen': round(m_gen, 2) if m_gen is not None else '-'
            })
            
        notifications = conn.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 5').fetchall()
        messages_recents = conn.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 15').fetchall()
        conn.close()
        
        return render_template('index.html', view=view, prof_nom=session['prof_nom'], prof_info=prof_info,
                               matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES, semestres=SEMESTRES_OFFICIELS,
                               matiere_active=matiere_selectionnee, classe_active=classe_selectionnee, semestre_actif=semestre_selectionne,
                               bilan_eleves=bilan_eleves, liste_eleves=liste_eleves,
                               notifications=notifications, messages_recents=messages_recents, 
                               message=message, success_message=success_message)

    view = request.args.get('view', 'login')
    message = ''
    resultats_recherche = None
    recherche_effectuee = False
    eleve_trouve = ""
    messages_recents = []

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
                
                msg_notif = f"Le professeur {nom} a créé un compte."
                conn.execute('INSERT INTO notifications (message) VALUES (?)', (msg_notif,))
                conn.commit()
                conn.close()

                session['prof_id'] = prof_id
                session['prof_nom'] = nom
                return redirect(url_for('index'))

        elif action == 'admin_auth':
            admin_code = request.form.get('admin_code', '').strip()
            conn = get_db_connection()
            cfg = conn.execute('SELECT valeur FROM config WHERE cle = ?', ('admin_code',)).fetchone()
            code_actuel = cfg['valeur'] if cfg else 'admin123'
            conn.close()

            if admin_code == code_actuel:
                session['is_admin'] = True
                return redirect(url_for('index'))
            else:
                message = "Code administrateur incorrect."
                view = 'admin_login'

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
                messages_recents = conn.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 15').fetchall()
            else:
                message = "Code secret incorrect."
                resultats_recherche = []
            conn.close()

        elif action == 'envoyer_message_parent':
            view = 'parent_space'
            code_secret_saisi = request.form.get('code_secret', '').strip().upper()
            contenu_msg = request.form.get('contenu_msg', '').strip()
            conn = get_db_connection()
            eleve = conn.execute('SELECT * FROM eleves WHERE UPPER(code_secret) = ?', (code_secret_saisi,)).fetchone()
            
            if eleve and contenu_msg:
                eleve_trouve = f"{eleve['nom']} ({eleve['classe']})"
                
                # 1. Enregistrement du message du parent
                conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                             (f"Parent ({eleve['nom']})", "parent", contenu_msg))
                conn.commit()

                # 2. Génération et enregistrement automatique de la réponse de l'IA
                reponse_ia = reponse_ia_automatique(contenu_msg, eleve['nom'])
                conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                             ("🤖 Assistant IA", "bot", reponse_ia))
                conn.commit()

                resultats_recherche = conn.execute(
                    'SELECT semestre, matiere, type_eval, note FROM notes WHERE LOWER(nom_eleve) = LOWER(?) AND classe = ?',
                    (eleve['nom'], eleve['classe'])
                ).fetchall()
                messages_recents = conn.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 15').fetchall()
                recherche_effectuee = True
            else:
                message = "Erreur lors de l'envoi du message."
            conn.close()

    return render_template('index.html', view=view, message=message, 
                           matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES, semestres=SEMESTRES_OFFICIELS,
                           resultats=resultats_recherche, recherche_effectuee=recherche_effectuee,
                           eleve_trouve=eleve_trouve, messages_recents=messages_recents)

@app.route('/scanner_notes', methods=['POST'])
def scanner_notes():
    if 'prof_id' not in session:
        return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
    if 'photo_cahier' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier trouvé'})
        
    photo = request.files['photo_cahier']
    
    if photo.filename == '':
        return jsonify({'success': False, 'message': 'Nom de fichier vide'})
        
    extensions_autorisees = ['.jpg', '.jpeg', '.png', '.webp']
    extension = os.path.splitext(photo.filename)[1].lower()
    
    if extension not in extensions_autorisees:
        return jsonify({'success': False, 'message': 'Format invalide'})
        
    return jsonify({'success': True, 'message': 'Photo valide'})

@app.route('/admin_delete_eleve/<int:id>')
def admin_delete_eleve(id):
    if not session.get('is_admin'):
        return redirect(url_for('index', view='admin_login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM eleves WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', view='admin_space'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)