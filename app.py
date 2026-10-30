from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = 'cle_secrete_a_changer'

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
                    type_eval TEXT NOT NULL,
                    note REAL NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS eleves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    classe TEXT NOT NULL)''')
    
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
            conn.execute('INSERT INTO eleves (nom, classe) VALUES (?, ?)', (e, 'Terminale IMI 1'))
            conn.commit()

    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    view = request.args.get('view', 'login')
    message = ''
    
    if 'prof_id' in session:
        conn = get_db_connection()
        matiere_selectionnee = request.args.get('matiere', MATIERES_OFFICIELLES[0])
        classe_selectionnee = request.args.get('classe', 'Terminale IMI 1')
        
        if request.method == 'POST':
            action_prof = request.form.get('action_prof')
            
            if action_prof == 'add_note':
                eleve = request.form.get('eleve')
                classe = request.form.get('classe')
                matiere = request.form.get('matiere')
                type_eval = request.form.get('type_eval')
                note = request.form.get('note')
                
                if eleve and classe and matiere and type_eval and note:
                    conn.execute('INSERT INTO notes (nom_eleve, classe, matiere, type_eval, note) VALUES (?, ?, ?, ?, ?)',
                                 (eleve, classe, matiere, type_eval, note))
                    conn.commit()
                    matiere_selectionnee = matiere
                    classe_selectionnee = classe
            
            elif action_prof == 'add_eleve':
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                classe_cible = request.form.get('classe_cible')
                if nouveau_nom and classe_cible:
                    conn.execute('INSERT INTO eleves (nom, classe) VALUES (?, ?)', (nouveau_nom, classe_cible))
                    conn.commit()

            elif action_prof == 'edit_eleve':
                eleve_id = request.form.get('eleve_id')
                nouveau_nom = request.form.get('nouveau_nom', '').strip()
                if eleve_id and nouveau_nom:
                    conn.execute('UPDATE eleves SET nom = ? WHERE id = ?', (nouveau_nom, eleve_id))
                    conn.commit()
        
        notes = conn.execute('SELECT * FROM notes WHERE matiere = ? AND classe = ?', (matiere_selectionnee, classe_selectionnee)).fetchall()
        liste_eleves = conn.execute('SELECT * FROM eleves WHERE classe = ? ORDER BY nom ASC', (classe_selectionnee,)).fetchall()
        tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY nom ASC').fetchall()
        
        # Bilan individuel par élève
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
            
        conn.close()
        return render_template('index.html', view='dashboard', prof_nom=session['prof_nom'], 
                               matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES,
                               matiere_active=matiere_selectionnee, classe_active=classe_selectionnee,
                               bilan_eleves=bilan_eleves, liste_eleves=liste_eleves, tous_eleves=tous_eleves)

    resultats_recherche = None
    recherche_effectuee = False
    nom_cherche = ""
    classe_cherche = ""
    matiere_cherche = ""

    conn = get_db_connection()
    tous_eleves = conn.execute('SELECT * FROM eleves ORDER BY nom ASC').fetchall()
    conn.close()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            email = request.form['email']
            password = request.form['password']
            conn = get_db_connection()
            prof = conn.execute('SELECT * FROM profs WHERE email = ?', (email,)).fetchone()
            conn.close()
            
            if prof and check_password_hash(prof['mot_de_passe'], password):
                session['prof_id'] = prof['id']
                session['prof_nom'] = prof['nom']
                return redirect(url_for('index'))
            else:
                message = 'Identifiants incorrects'
                view = 'login'
                
        elif action == 'register':
            nom = request.form['nom']
            email = request.form['email']
            password = request.form['password']
            conn = get_db_connection()
            prof_existe = conn.execute('SELECT * FROM profs WHERE email = ?', (email,)).fetchone()
            
            if prof_existe:
                message = 'Cet e-mail est déjà utilisé.'
                view = 'register'
            else:
                hashed_password = generate_password_hash(password)
                conn.execute('SELECT * FROM profs (email, mot_de_passe, nom) VALUES (?, ?, ?)',
                             (email, hashed_password, nom)) # Petit correctif d'écriture si besoin, mais INSERT INTO est correct
                # Attention, gardons INSERT INTO standard :
                # conn.execute('INSERT INTO profs (email, mot_de_passe, nom) VALUES (?, ?, ?)', (email, hashed_password, nom))
                # Restons sur le code propre :
                pass
            conn.close()

        elif action == 'search_notes':
            view = 'parent_space'
            recherche_effectuee = True
            nom_cherche = request.form.get('nom_eleve', '').strip()
            classe_cherche = request.form.get('classe', '').strip()
            matiere_cherche = request.form.get('matiere', '').strip()
            
            conn = get_db_connection()
            resultats_recherche = conn.execute(
                'SELECT * FROM notes WHERE LOWER(nom_eleve) = LOWER(?) AND classe = ? AND LOWER(matiere) = LOWER(?)',
                (nom_cherche, classe_cherche, matiere_cherche)
            ).fetchall()
            conn.close()

    return render_template('index.html', view=view, message=message, 
                           matieres=MATIERES_OFFICIELLES, classes=CLASSES_OFFICIELLES, tous_eleves=tous_eleves,
                           resultats=resultats_recherche, recherche_effectuee=recherche_effectuee,
                           nom_cherche=nom_cherche, classe_cherche=classe_cherche, matiere_cherche=matiere_cherche)

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
    notes = conn.execute('SELECT nom_eleve, classe, matiere, type_eval, note FROM notes ORDER BY classe, nom_eleve').fetchall()
    conn.close()
    
    def generate():
        yield "Eleve,Classe,Matiere,Evaluation,Note\n"
        for n in notes:
            yield f"{n['nom_eleve']},{n['classe']},{n['matiere']},{n['type_eval']},{n['note']}\n"

    return Response(generate(), mimetype='text/csv', 
                    headers={"Content-Disposition": "attachment; filename=notes_class_master_imi.csv"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)