from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string

app = Flask(__name__)
app.secret_key = 'super-secret-key-egan-app'

SEMESTRES_OFFICIELS = ["Semestre 1", "Semestre 2"]

def generer_code_secret():
    lettre = random.choice(string.ascii_uppercase)
    chiffres = "".join(random.choices(string.digits, k=3))
    return f"{lettre}{chiffres}"

def get_db_connection():
    conn = sqlite3.connect('egan_database.db')
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

    conn.execute('''CREATE TABLE IF NOT EXISTS classes_db (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_classe TEXT UNIQUE NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS matieres_classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_matiere TEXT NOT NULL,
                    classe TEXT NOT NULL,
                    UNIQUE(nom_matiere, classe))''')

    conn.execute('''CREATE TABLE IF NOT EXISTS prof_classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prof_id INTEGER NOT NULL,
                    classe TEXT NOT NULL,
                    UNIQUE(prof_id, classe))''')

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

    prof_existe = conn.execute('SELECT * FROM profs WHERE email = ?', ('prof@egan.bj',)).fetchone()
    if not prof_existe:
        mot_de_passe_chiffre = generate_password_hash('prof123')
        conn.execute('INSERT INTO profs (email, mot_de_passe, nom) VALUES (?, ?, ?)',
                     ('prof@egan.bj', mot_de_passe_chiffre, 'Jean Dupont'))
        conn.commit()

    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    classes_disponibles = [row['nom_classe'] for row in conn.execute('SELECT nom_classe FROM classes_db ORDER BY nom_classe ASC').fetchall()]
    conn.close()

    # ================= 1. ADMINISTRATEUR =================
    if session.get('is_admin'):
        view = request.args.get('view', 'admin_space')
        message = ''
        success_message_admin = ''
        conn = get_db_connection()
        
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'admin_add_classe':
                nom_nouvelle_classe = request.form.get('nom_nouvelle_classe', '').strip()
                if nom_nouvelle_classe:
                    try:
                        conn.execute('INSERT INTO classes_db (nom_classe) VALUES (?)', (nom_nouvelle_classe,))
                        conn.commit()
                        success_message_admin = f"Classe '{nom_nouvelle_classe}' créée avec succès !"
                    except sqlite3.IntegrityError:
                        message = "Cette classe existe déjà."

            elif action == 'admin_assign_classe_prof':
                prof_id_cible = request.form.get('prof_id')
                classe_cible = request.form.get('classe_cible')
                if prof_id_cible and classe_cible:
                    try:
                        conn.execute('INSERT INTO prof_classes (prof_id, classe) VALUES (?, ?)', (prof_id_cible, classe_cible))
                        conn.commit()
                        success_message_admin = f"Classe '{classe_cible}' assignée au professeur avec succès !"
                    except sqlite3.IntegrityError:
                        message = "Ce professeur enseigne déjà dans cette classe."

            elif action == 'admin_add_matiere':
                nom_matiere = request.form.get('nom_matiere', '').strip()
                classe_matiere = request.form.get('classe_matiere')
                if nom_matiere and classe_matiere:
                    try:
                        conn.execute('INSERT INTO matieres_classes (nom_matiere, classe) VALUES (?, ?)', (nom_matiere, classe_matiere))
                        conn.commit()
                        success_message_admin = f"Matière '{nom_matiere}' ajoutée !"
                    except sqlite3.IntegrityError:
                        message = "Cette matière existe déjà pour cette classe."

            elif action == 'admin_add_eleve':
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                classe_cible = request.form.get('classe_cible')
                code_saisi = request.form.get('code_secret_saisi', '').strip().upper()
                
                if nouveau_nom and classe_cible:
                    code_secret = code_saisi if code_saisi else generer_code_secret()
                    try:
                        conn.execute('INSERT INTO eleves (nom, classe, code_secret) VALUES (?, ?, ?)', (nouveau_nom, classe_cible, code_secret))
                        conn.commit()
                        success_message_admin = f"Élève {nouveau_nom} ajouté (Code : {code_secret}) !"
                    except sqlite3.IntegrityError:
                        message = "Ce code secret existe déjà."
                view = request.args.get('view', 'admin_space')
                if view == 'admin_classe_detail':
                    return redirect(url_for('index', view='admin_classe_detail', classe=classe_cible))

            elif action == 'admin_change_code':
                ancien_code = request.form.get('ancien_admin_code', '').strip()
                nouveau_code = request.form.get('nouveau_admin_code', '').strip()
                cfg = conn.execute('SELECT valeur FROM config WHERE cle = ?', ('admin_code',)).fetchone()
                code_actuel = cfg['valeur'] if cfg else 'admin123'

                if ancien_code == code_actuel:
                    if nouveau_code:
                        conn.execute('UPDATE config SET valeur = ? WHERE cle = ?', (nouveau_code, 'admin_code'))
                        conn.commit()
                        success_message_admin = "Code administrateur modifié !"
                    else:
                        message = "Le nouveau code ne peut pas être vide."
                else:
                    message = "L'ancien code est incorrect."
                view = 'admin_settings'

            elif action == 'envoyer_message_chat':
                contenu_msg = request.form.get('contenu_msg', '').strip()
                if contenu_msg:
                    conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                                 ("Administrateur", "admin", contenu_msg))
                    conn.commit()
                    return redirect(url_for('index', view='messenger'))

        tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY classe ASC, nom ASC').fetchall()
        toutes_matieres = conn.execute('SELECT * FROM matieres_classes ORDER BY classe ASC, nom_matiere ASC').fetchall()
        classes_actuelles = [row['nom_classe'] for row in conn.execute('SELECT nom_classe FROM classes_db ORDER BY nom_classe ASC').fetchall()]
        tous_profs = conn.execute('SELECT * FROM profs ORDER BY nom ASC').fetchall()
        attributions_profs = conn.execute('SELECT prof_classes.id, profs.nom as prof_nom, prof_classes.classe FROM prof_classes JOIN profs ON prof_classes.prof_id = profs.id ORDER BY profs.nom ASC').fetchall()
        messages_recents = conn.execute('SELECT * FROM messages ORDER BY id ASC').fetchall()
        
        classe_active_detail = request.args.get('classe', '')
        eleves_classe_active = []
        matieres_classe_active = []
        if view == 'admin_classe_detail' and classe_active_detail:
            eleves_classe_active = conn.execute('SELECT * FROM eleves WHERE classe = ? ORDER BY nom ASC', (classe_active_detail,)).fetchall()
            matieres_classe_active = conn.execute('SELECT * FROM matieres_classes WHERE classe = ? ORDER BY nom_matiere ASC', (classe_active_detail,)).fetchall()

        conn.close()
        
        return render_template('index.html', view=view, tous_eleves=tous_eleves, toutes_matieres=toutes_matieres,
                               classes=classes_actuelles, tous_profs=tous_profs, attributions_profs=attributions_profs,
                               message=message, success_message_admin=success_message_admin,
                               messages_recents=messages_recents, classe_active_detail=classe_active_detail,
                               eleves_classe_active=eleves_classe_active, matieres_classe_active=matieres_classe_active)

    # ================= 2. ENSEIGNANT =================
    if 'prof_id' in session:
        prof_id = session['prof_id']
        view = request.args.get('view', 'dashboard')
        message = ''
        success_message = ''
        
        conn = get_db_connection()
        prof_info = conn.execute('SELECT * FROM profs WHERE id = ?', (prof_id,)).fetchone()
        
        classes_du_prof = [row['classe'] for row in conn.execute('SELECT classe FROM prof_classes WHERE prof_id = ? ORDER BY classe ASC', (prof_id,)).fetchall()]
        
        classe_selectionnee = request.args.get('classe', classes_du_prof[0] if classes_du_prof else '')
        
        if classe_selectionnee and classe_selectionnee not in classes_du_prof and classes_du_prof:
            classe_selectionnee = classes_du_prof[0]

        matieres_classe = [row['nom_matiere'] for row in conn.execute('SELECT nom_matiere FROM matieres_classes WHERE classe = ? ORDER BY nom_matiere ASC', (classe_selectionnee,)).fetchall()] if classe_selectionnee else []
        matiere_selectionnee = request.args.get('matiere', matieres_classe[0] if matieres_classe else '')
        semestre_selectionne = request.args.get('semestre', SEMESTRES_OFFICIELS[0])
        
        if request.method == 'POST':
            action_prof = request.form.get('action_prof')
            action = request.form.get('action')
            
            if action_prof == 'save_all_notes':
                if classe_selectionnee not in classes_du_prof:
                    conn.close()
                    return "Accès refusé : Vous n'enseignez pas dans cette classe.", 403

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
                success_message = "Notes enregistrées avec succès !"

            elif action_prof == 'update_profile':
                nouveau_nom = request.form.get('nom', '').strip()
                nouvel_email = request.form.get('email', '').strip()
                if nouveau_nom and nouvel_email:
                    try:
                        conn.execute('UPDATE profs SET nom = ?, email = ? WHERE id = ?', (nouveau_nom, nouvel_email, prof_id))
                        conn.commit()
                        session['prof_nom'] = nouveau_nom
                        success_message = "Profil mis à jour avec succès !"
                    except sqlite3.IntegrityError:
                        message = "Cet e-mail est déjà utilisé par un autre compte."
                view = 'settings'

            elif action_prof == 'update_password':
                ancien_mdp = request.form.get('ancien_mdp', '').strip()
                nouveau_mdp = request.form.get('nouveau_mdp', '').strip()
                
                if check_password_hash(prof_info['mot_de_passe'], ancien_mdp):
                    if nouveau_mdp:
                        mdp_chiffre = generate_password_hash(nouveau_mdp)
                        conn.execute('UPDATE profs SET mot_de_passe = ? WHERE id = ?', (mdp_chiffre, prof_id))
                        conn.commit()
                        success_message = "Mot de passe modifié avec succès !"
                    else:
                        message = "Le nouveau mot de passe ne peut pas être vide."
                else:
                    message = "L'ancien mot de passe est incorrect."
                view = 'settings'

            elif action_prof == 'delete_account':
                conn.execute('DELETE FROM profs WHERE id = ?', (prof_id,))
                conn.execute('DELETE FROM prof_classes WHERE prof_id = ?', (prof_id,))
                conn.commit()
                conn.close()
                session.clear()
                return redirect(url_for('index'))

            elif action == 'envoyer_message_chat':
                contenu_msg = request.form.get('contenu_msg', '').strip()
                nom_prof = session.get('prof_nom', 'Enseignant')
                if contenu_msg:
                    conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                                 (f"Prof. {nom_prof}", "prof", contenu_msg))
                    conn.commit()
                    return redirect(url_for('index', view='messenger'))

        notes = conn.execute('SELECT * FROM notes WHERE matiere = ? AND classe = ? AND semestre = ?', 
                             (matiere_selectionnee, classe_selectionnee, semestre_selectionne)).fetchall() if classe_selectionnee else []
        liste_eleves = conn.execute('SELECT * FROM eleves WHERE classe = ? ORDER BY nom ASC', (classe_selectionnee,)).fetchall() if classe_selectionnee else []
        
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
            
        messages_recents = conn.execute('SELECT * FROM messages ORDER BY id ASC').fetchall()
        conn.close()
        
        return render_template('index.html', view=view, prof_nom=session['prof_nom'], prof_info=prof_info,
                               matieres=matieres_classe, classes=classes_du_prof, semestres=SEMESTRES_OFFICIELS,
                               matiere_active=matiere_selectionnee, classe_active=classe_selectionnee, semestre_actif=semestre_selectionne,
                               bilan_eleves=bilan_eleves, liste_eleves=liste_eleves, messages_recents=messages_recents,
                               message=message, success_message=success_message)

    # ================= 3. PARENTS / ACCUEIL =================
    view = request.args.get('view', 'login')
    message = ''
    resultats_recherche = None
    recherche_effectuee = False
    eleve_trouve = ""

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
                conn.close()
                return redirect(url_for('index'))
            else:
                if conn: conn.close()
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
                session['parent_eleve_nom'] = eleve['nom']
                session['parent_eleve_classe'] = eleve['classe']
                eleve_trouve = f"{eleve['nom']} ({eleve['classe']})"
                resultats_recherche = conn.execute(
                    'SELECT semestre, matiere, type_eval, note FROM notes WHERE LOWER(nom_eleve) = LOWER(?) AND classe = ?',
                    (eleve['nom'], eleve['classe'])
                ).fetchall()
            else:
                message = "Code secret incorrect."
                resultats_recherche = []
            conn.close()

        elif action == 'envoyer_message_chat':
            contenu_msg = request.form.get('contenu_msg', '').strip()
            conn = get_db_connection()
            nom_parent = session.get('parent_eleve_nom', 'Anonyme')
            classe_parent = session.get('parent_eleve_classe', '')
            
            if contenu_msg:
                auteur_formate = f"Parent ({nom_parent} - {classe_parent})" if session.get('parent_eleve_nom') else "Parent"
                conn.execute('INSERT INTO messages (auteur, role, contenu) VALUES (?, ?, ?)', 
                             (auteur_formate, "parent", contenu_msg))
                conn.commit()
            conn.close()
            return redirect(url_for('index', view='messenger'))

    conn = get_db_connection()
    messages_recents = conn.execute('SELECT * FROM messages ORDER BY id ASC').fetchall()
    conn.close()

    return render_template('index.html', view=view, message=message, 
                           classes=classes_disponibles, resultats=resultats_recherche, 
                           recherche_effectuee=recherche_effectuee, eleve_trouve=eleve_trouve,
                           messages_recents=messages_recents)

@app.route('/scanner_notes', methods=['POST'])
def scanner_notes():
    if 'prof_id' not in session:
        return jsonify({'success': False, 'message': 'Non autorisé'}), 403
    return jsonify({'success': True, 'message': 'Photo analysée avec succès'})

@app.route('/admin_delete_eleve/<int:id>')
def admin_delete_eleve(id):
    if not session.get('is_admin'):
        return redirect(url_for('index', view='admin_login'))
    
    conn = get_db_connection()
    eleve = conn.execute('SELECT classe FROM eleves WHERE id = ?', (id,)).fetchone()
    classe_nom = eleve['classe'] if eleve else ''
    
    conn.execute('DELETE FROM eleves WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    if classe_nom:
        return redirect(url_for('index', view='admin_classe_detail', classe=classe_nom))
    return redirect(url_for('index', view='admin_space'))

@app.route('/admin_delete_attribution/<int:id>')
def admin_delete_attribution(id):
    if not session.get('is_admin'):
        return redirect(url_for('index', view='admin_login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM prof_classes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', view='admin_space'))

@app.route('/admin_delete_prof/<int:id>')
def admin_delete_prof(id):
    if not session.get('is_admin'):
        return redirect(url_for('index', view='admin_login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM profs WHERE id = ?', (id,))
    conn.execute('DELETE FROM prof_classes WHERE prof_id = ?', (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index', view='admin_space'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)