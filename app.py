from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_library_key"

# --- SECURITY & COOKIE CONFIGURATION ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DATA_FILE = 'data.json'

# --- DATA HELPER FUNCTIONS ---

def load_data():
    if not os.path.exists(DATA_FILE):
        initial_data = {"books": [], "members": [], "transactions": []}
        save_data(initial_data)
        return initial_data
    with open(DATA_FILE, 'r') as file:
        return json.load(file)

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# --- AUTHENTICATION ROUTES ---

ADMIN_USERNAME = "Halem"
ADMIN_PASSWORD_HASH = generate_password_hash("Halem123")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['is_admin'] = True
            flash("Successfully logged in as Admin!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash("You have logged out.", "info")
    return redirect(url_for('index'))

# --- API ENDPOINT FOR LIVE SEARCH ---

@app.route('/api/search-books')
def search_books_api():
    """Returns matching books and authors as JSON for live frontend suggestions."""
    q = request.args.get('q', '').strip().lower()
    data = load_data()
    
    if not q:
        return jsonify([])
        
    results = [
        {
            "id": b["id"],
            "title": b["title"],
            "author": b["author"],
            "available_copies": b["available_copies"]
        }
        for b in data['books']
        if q in b['title'].lower() or q in b['author'].lower() or q in b['id'].lower()
    ]
    return jsonify(results)

# --- CORE SYSTEM ROUTES ---

@app.route('/')
def index():
    data = load_data()
    search_query = request.args.get('search', '').lower()
    sort_by = request.args.get('sort', 'default')
    
    books = data['books']
    
    if search_query:
        books = [b for b in books if search_query in b['title'].lower() or search_query in b['author'].lower()]
        
    if sort_by == 'copies_desc':
        books = sorted(books, key=lambda x: x['available_copies'], reverse=True)
    elif sort_by == 'copies_asc':
        books = sorted(books, key=lambda x: x['available_copies'])
    elif sort_by == 'total_desc':
        books = sorted(books, key=lambda x: x['total_copies'], reverse=True)

    return render_template('index.html', books=books, search_query=search_query, current_sort=sort_by)

@app.route('/add-book', methods=['GET', 'POST'])
def add_book():
    if not session.get('is_admin'):
        flash("Admin login required to add books.", "danger")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        data = load_data()
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        category = request.form['category'].strip()
        copies = int(request.form['copies'])

        # 1. FEATURE: Check for Duplicate Title (Case-Insensitive)
        title_exists = any(b['title'].strip().lower() == title.lower() for b in data['books'])
        if title_exists:
            flash(f"Error: A book titled '{title}' already exists in the catalog.", "danger")
            return redirect(url_for('add_book'))

        # Generate unique ID and verify no ID collision
        new_id = str(uuid.uuid4())[:8]
        while any(b['id'] == new_id for b in data['books']):
            new_id = str(uuid.uuid4())[:8]

        new_book = {
            "id": new_id,
            "title": title,
            "author": author,
            "category": category,
            "total_copies": copies,
            "available_copies": copies
        }
        data['books'].append(new_book)
        save_data(data)
        flash("Book added to catalog successfully!", "success")
        return redirect(url_for('index'))
        
    return render_template('add_book.html')

@app.route('/delete-book/<book_id>', methods=['POST'])
def delete_book(book_id):
    if not session.get('is_admin'):
        flash("Admin login required to delete books.", "danger")
        return redirect(url_for('login'))
        
    data = load_data()
    data['books'] = [b for b in data['books'] if b['id'] != book_id]
    save_data(data)
    flash("Book deleted from catalog.", "warning")
    return redirect(url_for('index'))

@app.route('/members', methods=['GET', 'POST'])
def members():
    data = load_data()
    
    if request.method == 'POST':
        if not session.get('is_admin'):
            flash("Admin login required to register members.", "danger")
            return redirect(url_for('login'))

        member_id = request.form['member_id'].strip()
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()

        # Check for Duplicate University ID (Case-Insensitive)
        existing_member = any(m['id'].strip().lower() == member_id.lower() for m in data['members'])
        if existing_member:
            flash(f"Error: University ID '{member_id}' is already registered to another member.", "danger")
            return redirect(url_for('members'))

        new_member = {
            "id": member_id,  # Custom University ID provided in the form
            "name": name,
            "email": email,
            "phone": phone
        }
        data['members'].append(new_member)
        save_data(data)
        flash(f"Member '{name}' (ID: {member_id}) registered successfully!", "success")
        return redirect(url_for('members'))
        
    return render_template('members.html', members=data['members'])

@app.route('/delete-member/<member_id>', methods=['POST'])
def delete_member(member_id):
    if not session.get('is_admin'):
        flash("Admin login required to delete members.", "danger")
        return redirect(url_for('login'))
        
    data = load_data()
    data['members'] = [m for m in data['members'] if m['id'] != member_id]
    save_data(data)
    flash("Member removed from system.", "warning")
    return redirect(url_for('members'))

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    data = load_data()
    
    if request.method == 'POST':
        action = request.form['action']
        
        if action == 'borrow':
            member_id = request.form['member_id'].strip()
            book_id = request.form['book_id'].strip()
            
            book = next((b for b in data['books'] if b['id'] == book_id), None)
            member = next((m for m in data['members'] if m['id'] == member_id), None)
            
            if not book or not member:
                flash("Invalid Member ID or Book ID.", "danger")
            elif book['available_copies'] <= 0:
                flash("Book is out of stock.", "danger")
            else:
                # 3. FEATURE: Prevent borrowing the exact same book twice if loan is still active
                existing_active_loan = next(
                    (t for t in data['transactions'] 
                     if t['member_id'] == member_id and t['book_id'] == book_id and t['status'] == 'Active'), 
                    None
                )
                
                if existing_active_loan:
                    flash(f"Error: Member '{member['name']}' already has an active loan for '{book['title']}'. Return it first before borrowing again.", "danger")
                    return redirect(url_for('transactions'))
                
                book['available_copies'] -= 1
                borrow_date = datetime.now()
                due_date = borrow_date + timedelta(days=14)
                
                new_txn = {
                    "txn_id": str(uuid.uuid4())[:8],
                    "book_id": book_id,
                    "book_title": book['title'],
                    "member_id": member_id,
                    "member_name": member['name'],
                    "borrow_date": borrow_date.strftime('%Y-%m-%d'),
                    "due_date": due_date.strftime('%Y-%m-%d'),
                    "return_date": None,
                    "fine": 0.0,
                    "status": "Active"
                }
                data['transactions'].append(new_txn)
                save_data(data)
                flash(f"Book borrowed! Due on {new_txn['due_date']}.", "success")
                
        elif action == 'return':
            txn_id = request.form['txn_id']
            txn = next((t for t in data['transactions'] if t['txn_id'] == txn_id and t['status'] == 'Active'), None)
            
            if txn:
                return_date = datetime.now()
                due_date = datetime.strptime(txn['due_date'], '%Y-%m-%d')
                fine = 0.0
                if return_date > due_date:
                    fine = (return_date - due_date).days * 5.0
                
                txn['return_date'] = return_date.strftime('%Y-%m-%d')
                txn['status'] = "Returned"
                txn['fine'] = fine
                
                book = next((b for b in data['books'] if b['id'] == txn['book_id']), None)
                if book:
                    book['available_copies'] += 1
                    
                save_data(data)
                flash(f"Book returned! Fine: {fine} EGP", "warning" if fine > 0 else "success")
                    
        return redirect(url_for('transactions'))
        
    sorted_txns = sorted(data['transactions'], key=lambda x: x['status'])
    return render_template('transactions.html', transactions=sorted_txns, books=data['books'], members=data['members'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000,ssl_context='adhoc', debug=True)